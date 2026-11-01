"""Course store - FastAPI backend for the React frontend.

All business logic lives in library/*; this file wires routes and middleware.
  * JSON APIs under /api/...
  * The React app (frontend/dist) is served for every page route with SEO tags injected (library/spa.py)
Run (dev):   uvicorn main:app --reload        (build the frontend first: cd frontend && npm run build)
Run (prod):  ./start.sh
"""
from __future__ import annotations

import csv
import functools
import io
import json
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from library import db, delivery, error, mailer, payments, pricing, security, seo, spa, timing, views
from library.catalog import SLUG_RE, Product, catalog
from library.config import (BASE_DIR, app_env, base_url, env, is_production, load_config, payment_mode,
                            razorpay_credentials, secret_key)

CFG = load_config()
SITE: Dict[str, Any] = CFG["site"]
LEGAL_PAGES = {"terms": "Terms of service", "privacy": "Privacy policy",
               "refund": "Refund and cancellation policy", "contact": "Contact us"}


# ------------------------------------------------------------------ startup
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    secret_key()                                   # fail fast if production is misconfigured
    db.init_db()
    problems = catalog.load()
    for p in problems:
        print(f"[catalog] SKIPPED {p}", file=sys.stderr)
    mode = payment_mode()
    print(f"[store] env={app_env()} payments={mode} products={len(catalog.products(True))}", file=sys.stderr)
    if not spa.INDEX.is_file():
        print("[store] WARNING: frontend not built. Run: cd frontend && npm install && npm run build",
              file=sys.stderr)
    if mode == "demo":
        print("[store] DEMO CHECKOUT is on (no Razorpay keys). Real payments are disabled.", file=sys.stderr)
    if mode == "disabled":
        print("[store] PRODUCTION without Razorpay keys: checkout is disabled.", file=sys.stderr)
    if mode == "razorpay" and not env("RAZORPAY_WEBHOOK_SECRET"):
        print("[store] WARNING: RAZORPAY_WEBHOOK_SECRET missing - paid-but-closed-tab orders won't auto-confirm.",
              file=sys.stderr)
    yield


app = FastAPI(
    title="Course Store",
    lifespan=lifespan,
    docs_url=None if is_production() else "/docs",
    redoc_url=None,
    openapi_url=None if is_production() else "/openapi.json",
)
# Middleware: last added = outermost.
app.add_middleware(GZipMiddleware, minimum_size=600)
app.add_middleware(security.RequestGuardMiddleware)
app.add_middleware(security.SecurityHeadersMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=security.trusted_hosts())


class CachedStatic(StaticFiles):
    """Vite fingerprints everything under /static/assets/ (hash in the file name), so cache it for a year."""

    def file_response(self, full_path: Any, stat_result: Any, scope: Any, status_code: int = 200) -> Response:
        resp = super().file_response(full_path, stat_result, scope, status_code)
        cfg = CFG["static"]
        if scope.get("path", "").startswith("/static/assets/"):
            resp.headers["Cache-Control"] = f"public, max-age={cfg['immutable_max_age_s']}, immutable"
        else:
            resp.headers["Cache-Control"] = f"public, max-age={cfg['default_max_age_s']}"
        return resp


# check_dir=False lets the API start (and tests run) before the frontend has been built.
app.mount("/static", CachedStatic(directory=str(BASE_DIR / "frontend" / "dist"), check_dir=False), name="static")


# ------------------------------------------------------------------ helpers
def inr(paise: int) -> str:
    """Indian digit grouping, e.g. 1499900 -> ₹14,999."""
    rupees, rem = divmod(int(paise), 100)
    s = str(rupees)
    if len(s) > 3:
        head, tail, parts = s[:-3], s[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"₹{s}" + (f".{rem:02d}" if rem else "")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def fail(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _timed(steps: Dict[str, float], key: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t = time.perf_counter()
            result = fn(*args, **kwargs)
            steps[key] = round(time.perf_counter() - t, 3)
            return result
        return wrapper
    return decorator


def page(path: str, title: str, description: str = "", *, status: int = 200, robots: str = "index,follow",
         product: Optional[Product] = None, boot_extra: Optional[Dict[str, Any]] = None,
         h1: str = "", blurb: str = "") -> HTMLResponse:
    """Serve the React app for `path` with SEO tags, theme and boot data injected."""
    boot = views.site_payload()
    if product is not None:
        boot["product"] = views.product_payload(product)
    boot.update(boot_extra or {})
    body = spa.render_page(
        title=title, description=description or SITE["tagline"], path=path, robots=robots,
        theme=product.theme if product else None, boot=boot, h1=h1, blurb=blurb,
        jsonld=seo.product_jsonld(product, SITE["name"]) if product else None)
    return HTMLResponse(body, status_code=status)


def product_page(p: Product) -> HTMLResponse:
    return page(f"/p/{p.slug}", p.seo["title"], p.seo["description"], product=p, h1=p.headline, blurb=p.subhead)


def error_page(code: int, message: str) -> HTMLResponse:
    return page("/", f"{code} | {SITE['name']}", message, status=code, robots="noindex,nofollow",
                boot_extra={"error": {"code": code, "message": message}})


# ------------------------------------------------------------------ pages (React app shells)
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home() -> HTMLResponse:
    home_slug = SITE.get("home_product") or ""
    p = catalog.get(home_slug) if home_slug else None
    if p and p.status != "archived":
        return product_page(p)
    return page("/", f"{SITE['name']}: {SITE['tagline']}", SITE["tagline"], h1=SITE["name"], blurb=SITE["tagline"])


@app.api_route("/p/{slug}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def product(slug: str) -> HTMLResponse:
    p = catalog.get(slug) if SLUG_RE.match(slug) else None
    if p is None or p.status == "archived":
        return error_page(404, "That page doesn't exist.")
    return product_page(p)


@app.api_route("/legal/{pagename}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def legal(pagename: str) -> HTMLResponse:
    if pagename not in LEGAL_PAGES:
        return error_page(404, "That page doesn't exist.")
    return page(f"/legal/{pagename}", f"{LEGAL_PAGES[pagename]} | {SITE['name']}",
                f"{LEGAL_PAGES[pagename]} for {SITE['name']}.")


@app.api_route("/thanks/{public_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def thanks(public_id: str, t: str = "") -> HTMLResponse:
    order = db.get_order(public_id)
    if order is None or not security.verify_access(public_id, t):
        return error_page(404, "We couldn't find that order.")
    return page(f"/thanks/{public_id}", f"Your order | {SITE['name']}", robots="noindex,nofollow",
                product=None)


@app.api_route("/admin", methods=["GET", "HEAD"], response_class=HTMLResponse)
def admin_shell() -> HTMLResponse:
    return page("/admin", f"Admin | {SITE['name']}", robots="noindex,nofollow")


@app.api_route("/healthz", methods=["GET", "HEAD"])
def healthz() -> Dict[str, Any]:
    return {"status": "ok", "payments": payment_mode()}


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    return seo.robots_txt()


@app.get("/sitemap.xml")
def sitemap() -> Response:
    return Response(seo.sitemap_xml(catalog.products()), media_type="application/xml")


@app.get("/favicon.svg")
def favicon() -> Response:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" '
           'fill="#2B2BFF"/><path d="M20 14h8v15l14-15h10L36 31l17 19H42L28 34v16h-8z" fill="#FFD60A"/></svg>')
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


# ------------------------------------------------------------------ API models
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuoteIn(_Strict):
    slug: str = Field(max_length=63)
    coupon: str = Field("", max_length=32)


class OrderIn(_Strict):
    slug: str = Field(max_length=63)
    name: str = Field(max_length=120)
    email: str = Field(max_length=254)
    phone: str = Field("", max_length=20)
    coupon: str = Field("", max_length=32)
    utm: Dict[str, str] = Field(default_factory=dict, max_length=12)
    website: str = Field("", max_length=200)          # honeypot: real users never fill this


class VerifyIn(_Strict):
    order_id: str = Field(max_length=40)
    razorpay_order_id: str = Field(max_length=60)
    razorpay_payment_id: str = Field(max_length=60)
    razorpay_signature: str = Field(max_length=200)


class DemoPayIn(_Strict):
    order_id: str = Field(max_length=40)


class LeadIn(_Strict):
    slug: str = Field(max_length=63)
    email: str = Field(max_length=254)
    utm: Dict[str, str] = Field(default_factory=dict, max_length=12)
    website: str = Field("", max_length=200)


class LoginIn(_Strict):
    password: str = Field(max_length=200)


def _product_or_none(slug: str) -> Optional[Product]:
    return catalog.get(slug) if SLUG_RE.match(slug) else None


def _access_url(public_id: str) -> str:
    return f"{base_url()}/thanks/{public_id}?t={security.access_token(public_id)}"


def _fulfil(public_id: str) -> None:
    """Runs once per paid order (background): send the access email."""
    order = db.get_order(public_id)
    p = catalog.get(order.product_slug) if order else None
    if order and p:
        mailer.send_order_email(order, p.name, _access_url(public_id), SITE["name"], SITE["support_email"])


# ------------------------------------------------------------------ public read APIs
@app.get("/api/site")
def api_site() -> JSONResponse:
    return JSONResponse(views.site_payload())


@app.get("/api/products/{slug}")
def api_product(slug: str) -> JSONResponse:
    p = _product_or_none(slug)
    if p is None or p.status == "archived":
        return fail("Unknown product.", 404)
    return JSONResponse(views.product_payload(p))


@app.get("/api/products/{slug}/status")
def api_product_status(slug: str) -> JSONResponse:
    p = _product_or_none(slug)
    if p is None:
        return fail("Unknown product.", 404)
    ctx = views.product_payload(p)
    return JSONResponse({"seats_left": ctx["seats_left"], "seats_total": ctx["seats_total"],
                         "price_text": inr(ctx["base_paise"]), "early": ctx["early"], "can_buy": ctx["can_buy"]},
                        headers={"Cache-Control": "public, max-age=5"})


# ------------------------------------------------------------------ checkout API
@app.post("/api/checkout/quote")
def api_quote(body: QuoteIn, request: Request) -> JSONResponse:
    if not security.rate_ok("checkout_quote", client_ip(request)):
        return fail("Too many attempts. Please wait a minute.", 429)
    p = _product_or_none(body.slug)
    if p is None:
        return fail("Unknown product.", 404)
    try:
        q = pricing.quote(p, body.coupon)
    except pricing.PricingError as exc:
        return fail(str(exc), 400)
    return JSONResponse({**q.to_dict(), "amount_text": inr(q.amount_paise), "discount_text": inr(q.discount_paise)})


@app.post("/api/checkout/order")
def api_create_order(body: OrderIn, request: Request) -> JSONResponse:
    ip = client_ip(request)
    if not security.rate_ok("checkout_order", ip):
        return fail("Too many attempts. Please wait a minute and try again.", 429)
    if body.website:                                           # bot filled the honeypot
        return fail("Something went wrong. Please refresh and try again.", 400)
    task_id, steps, t0 = str(uuid.uuid4()), {}, time.perf_counter()
    mode = payment_mode()
    if mode == "disabled":
        return fail("Checkout is temporarily unavailable. Please try again soon.", 503)
    p = _product_or_none(body.slug)
    if p is None or not p.purchasable:
        return fail("This product isn't available.", 404)
    name, email = security.clean_name(body.name), security.clean_email(body.email)
    phone = security.clean_phone(body.phone)
    if not name:
        return fail("Please enter your full name.")
    if not email:
        return fail("Please enter a valid email address.")
    if phone is None:
        return fail("Phone number looks wrong. Use digits only, with optional +country code.")
    left = pricing.seats_left(p)
    if left == 0:
        return fail("Sorry, every seat has been taken. Join the waitlist instead.", 409)
    if db.has_paid_order(email, p.slug):
        return fail("This email already has access. Check your inbox for your order link.", 409)
    order: Optional[db.Order] = None
    try:
        q = _timed(steps, "quote_s")(pricing.quote)(p, body.coupon)
        order = _timed(steps, "db_s")(db.create_order)(
            product_slug=p.slug, name=name, email=email, phone=phone, amount_paise=q.amount_paise,
            list_paise=q.list_paise, coupon=q.coupon, mode=mode, utm=security.clean_utm(body.utm),
            ip_hash=security.hash_ip(ip))
        if mode == "razorpay":
            rz = _timed(steps, "razorpay_s")(payments.create_razorpay_order)(
                q.amount_paise, order.public_id, {"order": order.public_id, "product": p.slug})
            rz_order_id = rz["id"]
        else:
            rz_order_id = payments.new_demo_order_id()
        db.attach_rz_order(order.public_id, rz_order_id)
    except pricing.PricingError as exc:
        return fail(str(exc), 400)
    except Exception as exc:
        error.write(task_id, body.slug, "create_order", exc)
        if order is not None:
            try:
                db.mark_failed(order.id)
            except Exception:
                pass
        return fail("We couldn't start the payment. Please try again in a moment.", 502)
    timing.write(task_id, f"order:{order.public_id}", steps, round(time.perf_counter() - t0, 3))
    creds = razorpay_credentials()
    return JSONResponse({
        "order_id": order.public_id, "rz_order_id": rz_order_id, "mode": mode,
        "key_id": creds[0] if creds else "", "amount": q.amount_paise, "currency": "INR",
        "amount_text": inr(q.amount_paise), "business": SITE["name"], "description": p.name,
        "prefill": {"name": name, "email": email, "contact": phone}, "theme_color": p.theme["hero_bg"],
    })


@app.post("/api/checkout/verify")
def api_verify(body: VerifyIn, request: Request, background: BackgroundTasks) -> JSONResponse:
    if not security.rate_ok("checkout_verify", client_ip(request)):
        return fail("Too many attempts.", 429)
    order = db.get_order(body.order_id)
    if order is None or order.mode != "razorpay" or order.rz_order_id != body.razorpay_order_id:
        return fail("Payment could not be verified.", 400)
    if not payments.verify_payment_signature(body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature):
        error.write(order.public_id, order.product_slug, "verify.bad_signature", ValueError("bad payment signature"))
        return fail("Payment could not be verified.", 400)
    if db.mark_paid(order.id, body.razorpay_payment_id):
        background.add_task(_fulfil, order.public_id)
    return JSONResponse({"redirect": f"/thanks/{order.public_id}?t={security.access_token(order.public_id)}"})


@app.post("/api/checkout/demo-pay")
def api_demo_pay(body: DemoPayIn, request: Request, background: BackgroundTasks) -> JSONResponse:
    if payment_mode() != "demo":
        return fail("Not found.", 404)
    if not security.rate_ok("checkout_verify", client_ip(request)):
        return fail("Too many attempts.", 429)
    order = db.get_order(body.order_id)
    if order is None or order.mode != "demo":
        return fail("Not found.", 404)
    if db.mark_paid(order.id, payments.new_demo_payment_id()):
        background.add_task(_fulfil, order.public_id)
    return JSONResponse({"redirect": f"/thanks/{order.public_id}?t={security.access_token(order.public_id)}"})


@app.post("/api/webhooks/razorpay")
async def api_webhook(request: Request, background: BackgroundTasks) -> JSONResponse:
    raw = await request.body()
    sig = request.headers.get("x-razorpay-signature", "")
    if not payments.verify_webhook_signature(raw, sig):
        return fail("Invalid signature.", 400)
    try:
        event = json.loads(raw)
        etype = event.get("event", "")
        entity = event["payload"]["payment"]["entity"]
        rz_order_id, rz_payment_id = str(entity["order_id"]), str(entity["id"])
        amount, currency = int(entity["amount"]), str(entity.get("currency", "INR"))
    except (KeyError, TypeError, ValueError):
        return JSONResponse({"ok": True, "ignored": "unhandled payload"})
    if etype not in ("payment.captured", "order.paid"):
        return JSONResponse({"ok": True, "ignored": etype})
    order = db.get_order_by_rz(rz_order_id)
    if order is None:
        return JSONResponse({"ok": True, "ignored": "unknown order"})
    if amount != order.amount_paise or currency != order.currency:
        error.write(order.public_id, order.product_slug, "webhook.amount_mismatch",
                    ValueError(f"expected {order.amount_paise} {order.currency}, got {amount} {currency}"))
        return JSONResponse({"ok": True, "ignored": "amount mismatch"})
    if db.mark_paid(order.id, rz_payment_id):
        background.add_task(_fulfil, order.public_id)
    return JSONResponse({"ok": True})


@app.post("/api/leads")
def api_lead(body: LeadIn, request: Request) -> JSONResponse:
    if not security.rate_ok("lead", client_ip(request)):
        return fail("Too many attempts. Please wait a minute.", 429)
    if body.website:                                             # honeypot: pretend success
        return JSONResponse({"ok": True})
    email = security.clean_email(body.email)
    if not email:
        return fail("Please enter a valid email address.")
    p = _product_or_none(body.slug)
    if p is None:
        return fail("Unknown product.", 404)
    db.add_lead(email, p.slug, security.clean_utm(body.utm))
    return JSONResponse({"ok": True, "message": "You're on the list. We'll email you the moment doors open."})


# ------------------------------------------------------------------ order page data + downloads
def _order_for(public_id: str, token: str) -> Optional[db.Order]:
    order = db.get_order(public_id)
    return order if order is not None and security.verify_access(public_id, token) else None


@app.get("/api/orders/{public_id}")
def api_order(public_id: str, request: Request, t: str = "") -> JSONResponse:
    if not security.rate_ok("order_status", client_ip(request)):
        return fail("Too many requests.", 429)
    order = _order_for(public_id, t)
    if order is None:
        return fail("Not found.", 404)
    return JSONResponse(views.order_payload(order, catalog.get(order.product_slug)))


@app.get("/api/orders/{public_id}/status")
def api_order_status(public_id: str, request: Request, t: str = "") -> JSONResponse:
    if not security.rate_ok("order_status", client_ip(request)):
        return fail("Too many requests.", 429)
    order = _order_for(public_id, t)
    if order is None:
        return fail("Not found.", 404)
    return JSONResponse({"status": order.status})


@app.get("/download/{token}")
def download(request: Request, token: str) -> Response:
    if not security.rate_ok("download", client_ip(request)):
        raise StarletteHTTPException(429, "Too many downloads. Please wait a minute.")
    parsed = security.parse_download_token(token)
    if parsed is None:
        raise StarletteHTTPException(404, "This download link has expired. Open your order page for a fresh one.")
    public_id, file_id = parsed
    order = db.get_order(public_id)
    p = catalog.get(order.product_slug) if order else None
    found = delivery.find_file(p, file_id) if (p and order and order.paid) else None
    if found is None:
        raise StarletteHTTPException(404, "File not found.")
    if not db.bump_download(public_id, int(CFG["security"]["max_downloads_per_order"])):
        raise StarletteHTTPException(429, "Download limit reached for this order. Contact support and we'll sort it.")
    meta, path = found
    return FileResponse(path, filename=meta.filename, media_type="application/octet-stream",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


# ------------------------------------------------------------------ admin API (the page itself is React)
def _is_admin(request: Request) -> bool:
    return security.valid_admin_session(request.cookies.get("kiln_admin"))


@app.post("/api/admin/login")
def admin_login(body: LoginIn, request: Request) -> JSONResponse:
    if not security.rate_ok("admin_login", client_ip(request)):
        return fail("Too many attempts. Wait a few minutes.", 429)
    if not security.check_admin_password(body.password):
        time.sleep(0.4)                                    # slow down guessing
        return fail("Wrong password.", 401)
    resp = JSONResponse({"ok": True})
    resp.set_cookie("kiln_admin", security.new_admin_session(), max_age=int(CFG["security"]["session_ttl_s"]),
                    httponly=True, secure=is_production(), samesite="strict", path="/")
    return resp


@app.post("/api/admin/logout")
def admin_logout() -> JSONResponse:
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("kiln_admin", path="/")
    return resp


@app.get("/api/admin/overview")
def admin_overview(request: Request) -> JSONResponse:
    if not _is_admin(request):
        return fail("Sign in required.", 401)
    products = catalog.products(True)
    warnings = []
    if payment_mode() == "demo":
        warnings.append("Demo checkout is active: no real money moves. Add Razorpay keys to .env to go live.")
    if payment_mode() == "razorpay" and not env("RAZORPAY_WEBHOOK_SECRET"):
        warnings.append("RAZORPAY_WEBHOOK_SECRET is missing: buyers who close the tab after paying won't be auto-confirmed.")
    if not mailer.enabled():
        warnings.append("SMTP is not configured: buyers won't get the access email (they still see it on screen).")
    for pr in products:
        if pr.purchasable and pr.delivery.type != "link":
            for fn in delivery.missing_files(pr):
                warnings.append(f"{pr.name}: file '{fn}' is missing from deliverables/{pr.slug}/")
    warnings += [f"Catalog: {e}" for e in catalog.errors]
    return JSONResponse({"stats": db.stats(), "orders": db.recent_orders(100), "warnings": warnings,
                         "names": {x.slug: x.name for x in products}})


@app.post("/api/admin/reload")
def admin_reload(request: Request) -> JSONResponse:
    if not _is_admin(request):
        return fail("Sign in required.", 401)
    return JSONResponse({"problems": len(catalog.load())})


@app.get("/admin/export/{what}.csv")
def admin_export(request: Request, what: str) -> Response:
    if not _is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    if what not in ("orders", "leads"):
        raise StarletteHTTPException(404, "Not found.")
    rows = db.all_orders() if what == "orders" else db.all_leads()
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow({k: security.csv_safe(v) for k, v in r.items()})
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{what}.csv"', "Cache-Control": "no-store"})


# ------------------------------------------------------------------ errors
def _wants_json(request: Request) -> bool:
    return request.url.path.startswith(("/api/", "/static/")) or "text/html" not in request.headers.get("accept", "")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return fail("Please check the details you entered and try again.", 400)


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException) -> Response:
    if _wants_json(request):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    return error_page(exc.status_code, str(exc.detail))


@app.exception_handler(Exception)
async def crash_handler(request: Request, exc: Exception) -> Response:
    error.write(str(uuid.uuid4()), request.url.path, "unhandled", exc)
    if request.url.path.startswith("/api/"):
        return fail("Something went wrong on our side. Please try again.", 500)
    return error_page(500, "Something went wrong on our side.")
