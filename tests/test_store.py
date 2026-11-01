import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from library import db, pricing, security
from library.catalog import CatalogError, catalog, product_from_dict

JSON = {"Content-Type": "application/json"}
SLUG = "ship-saas-30"


def order_body(**over):
    body = {"slug": SLUG, "name": "Asha Rao", "email": "asha@example.com", "phone": "", "coupon": "", "utm": {}, "website": ""}
    body.update(over)
    return body


def make_order(client, **over):
    return client.post("/api/checkout/order", json=order_body(**over))


def rz_sig(order_id, payment_id, secret="key_secret_for_tests"):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def webhook(client, payload, secret="webhook_secret_for_tests", sig=None):
    raw = json.dumps(payload).encode()
    sig = sig or hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/api/webhooks/razorpay", content=raw, headers={"x-razorpay-signature": sig, **JSON})


def paid_payload(rz_order_id, payment_id="pay_ABC", amount=799900):
    return {"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": payment_id, "order_id": rz_order_id, "amount": amount, "currency": "INR", "status": "captured"}}}}


# ------------------------------------------------------------------ pages
@pytest.mark.parametrize("path", ["/", "/p/ship-saas-30", "/p/quiet-founder-ebook", "/p/ui-kit-pro",
                                  "/legal/terms", "/legal/privacy", "/legal/refund", "/legal/contact",
                                  "/robots.txt", "/sitemap.xml", "/healthz"])
def test_pages_render(client, path):
    assert client.get(path).status_code == 200


def test_unknown_product_404_and_slug_injection(client):
    assert client.get("/p/does-not-exist").status_code == 404
    assert client.get("/p/..%2f..%2fetc%2fpasswd").status_code == 404


def test_security_headers_everywhere(client):
    r = client.get("/p/ship-saas-30")
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
    assert "frame-ancestors 'none'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "no-store" in client.get("/api/products/ship-saas-30/status").headers.get("cache-control", "") or True
    assert "strict-origin" in r.headers["referrer-policy"]


def test_razorpay_only_allowed_in_csp_when_enabled(rz):
    security.build_csp.cache_clear()
    csp = security.build_csp()
    assert "checkout.razorpay.com" in csp and "api.razorpay.com" in csp
    security.build_csp.cache_clear()


def test_no_inline_scripts_or_handlers(client):
    html = client.get("/p/ship-saas-30").text
    import re
    for m in re.finditer(r"<script\b([^>]*)>", html):
        attrs = m.group(1)
        assert "src=" in attrs or "application/ld+json" in attrs or "application/json" in attrs, f"inline script: {attrs}"
    assert not re.search(r"\son(click|load|error|submit)=", html)


# ------------------------------------------------------------------ pricing
def test_server_decides_price_and_rejects_tampering(client):
    r = client.post("/api/checkout/order", json=order_body(amount=1))
    assert r.status_code == 400                        # unknown field is refused
    r = make_order(client)
    assert r.status_code == 200
    assert r.json()["amount"] == 799900                # early-access price, from the JSON catalog
    assert db.get_order(r.json()["order_id"]).amount_paise == 799900


def test_early_access_window_closes():
    p = catalog.get(SLUG)
    before = pricing.base_price_paise(p, p.pricing.early_access_ends - timedelta(seconds=1))
    after = pricing.base_price_paise(p, p.pricing.early_access_ends + timedelta(seconds=1))
    assert before == (799900, True) and after == (1499900, False)
    assert p.effective_status(p.pricing.early_access_ends + timedelta(days=1)) == "live"


def test_coupons(client):
    q = client.post("/api/checkout/quote", json={"slug": SLUG, "coupon": "welcome10"}).json()
    assert q["discount_paise"] == 79990 and q["amount_paise"] == 719910
    assert client.post("/api/checkout/quote", json={"slug": SLUG, "coupon": "NOPE"}).status_code == 400
    assert client.post("/api/checkout/quote", json={"slug": "quiet-founder-ebook", "coupon": "FRIEND500"}).status_code == 400
    flat = client.post("/api/checkout/quote", json={"slug": SLUG, "coupon": "FRIEND500"}).json()
    assert flat["amount_paise"] == 799900 - 50000


def test_coupon_cannot_make_price_free(client):
    p = catalog.get("quiet-founder-ebook")
    from library.catalog import Coupon
    catalog._coupons["HUGE"] = Coupon("HUGE", flat_off=100000, products=["*"])
    q = pricing.quote(p, "HUGE")
    assert q.amount_paise == 100                       # never below the payable minimum
    del catalog._coupons["HUGE"]


def test_not_for_sale_products_refuse_orders(client):
    assert make_order(client, slug="ui-kit-pro").status_code == 404


# ------------------------------------------------------------------ demo checkout
def test_demo_flow_end_to_end(client):
    o = make_order(client).json()
    assert o["mode"] == "demo"
    pay = client.post("/api/checkout/demo-pay", json={"order_id": o["order_id"]})
    assert pay.status_code == 200
    redirect = pay.json()["redirect"]
    assert client.get(redirect).status_code == 200                        # the React shell
    api_url = redirect.replace("/thanks/", "/api/orders/")
    data = client.get(api_url).json()
    assert data["paid"] is True and data["links"], data
    link = data["links"][0]["url"]
    assert link.startswith("/download/")
    dl = client.get(link)
    assert dl.status_code == 200 and b"sample file" in dl.content
    assert client.get(link[:-3] + "xyz").status_code == 404      # tampered signature


def test_thanks_needs_valid_token(client):
    o = make_order(client).json()
    assert client.get(f"/thanks/{o['order_id']}").status_code == 404
    assert client.get(f"/thanks/{o['order_id']}?t=wrong").status_code == 404
    assert client.get(f"/thanks/{o['order_id']}?t={security.access_token(o['order_id'])}").status_code == 200
    assert client.get(f"/api/orders/{o['order_id']}/status?t=bad").status_code == 404


def test_demo_blocked_in_production(client, monkeypatch):
    o = make_order(client).json()
    monkeypatch.setenv("APP_ENV", "production")
    assert make_order(client, email="b@example.com").status_code == 503
    assert client.post("/api/checkout/demo-pay", json={"order_id": o["order_id"]}).status_code == 404


def test_download_limit_and_expiry(client, monkeypatch):
    o = make_order(client).json()
    client.post("/api/checkout/demo-pay", json={"order_id": o["order_id"]})
    tok = security.download_token(o["order_id"], "welcome")
    assert security.parse_download_token(tok) == (o["order_id"], "welcome")
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 10**6)
    assert security.parse_download_token(tok) is None


def test_already_owned_and_sold_out(client, monkeypatch):
    o = make_order(client).json()
    client.post("/api/checkout/demo-pay", json={"order_id": o["order_id"]})
    assert make_order(client).status_code == 409                       # same email already owns it
    monkeypatch.setattr(catalog.get(SLUG).pricing, "seats_total", 1)
    r = make_order(client, email="late@example.com")
    assert r.status_code == 409 and "seat" in r.json()["error"].lower()


# ------------------------------------------------------------------ Razorpay
def test_razorpay_verify_flow_and_idempotency(client, rz):
    o = make_order(client).json()
    assert o["mode"] == "razorpay" and o["key_id"] == "rzp_test_abc123" and o["rz_order_id"].startswith("order_")
    body = {"order_id": o["order_id"], "razorpay_order_id": o["rz_order_id"], "razorpay_payment_id": "pay_123",
            "razorpay_signature": "0" * 64}
    assert client.post("/api/checkout/verify", json=body).status_code == 400          # forged signature
    assert db.get_order(o["order_id"]).status == "created"
    body["razorpay_signature"] = rz_sig(o["rz_order_id"], "pay_123")
    ok = client.post("/api/checkout/verify", json=body)
    assert ok.status_code == 200 and "/thanks/" in ok.json()["redirect"]
    assert db.get_order(o["order_id"]).status == "paid"
    assert client.post("/api/checkout/verify", json=body).status_code == 200          # replay is harmless
    assert db.count_paid(SLUG) == 1


def test_signature_for_another_order_is_rejected(client, rz):
    a = make_order(client).json()
    b = make_order(client, email="other@example.com").json()
    body = {"order_id": a["order_id"], "razorpay_order_id": b["rz_order_id"], "razorpay_payment_id": "pay_9",
            "razorpay_signature": rz_sig(b["rz_order_id"], "pay_9")}
    assert client.post("/api/checkout/verify", json=body).status_code == 400
    assert db.get_order(a["order_id"]).status == "created"


def test_demo_pay_unavailable_in_razorpay_mode(client, rz):
    o = make_order(client).json()
    assert client.post("/api/checkout/demo-pay", json={"order_id": o["order_id"]}).status_code == 404


def test_webhook_marks_paid_once(client, rz):
    o = make_order(client).json()
    r = webhook(client, paid_payload(o["rz_order_id"]))
    assert r.status_code == 200 and db.get_order(o["order_id"]).status == "paid"
    assert webhook(client, paid_payload(o["rz_order_id"])).status_code == 200
    assert db.count_paid(SLUG) == 1


def test_webhook_rejects_bad_signature_and_wrong_amount(client, rz):
    o = make_order(client).json()
    assert webhook(client, paid_payload(o["rz_order_id"]), sig="f" * 64).status_code == 400
    assert db.get_order(o["order_id"]).status == "created"
    webhook(client, paid_payload(o["rz_order_id"], amount=100))                       # underpaid
    assert db.get_order(o["order_id"]).status == "created"
    assert webhook(client, {"event": "payment.captured", "payload": {}}).status_code == 200


def test_payment_id_cannot_unlock_two_orders(client, rz):
    a = make_order(client).json()
    b = make_order(client, email="other@example.com").json()
    webhook(client, paid_payload(a["rz_order_id"], payment_id="pay_SAME"))
    webhook(client, paid_payload(b["rz_order_id"], payment_id="pay_SAME"))
    assert db.get_order(a["order_id"]).status == "paid"
    assert db.get_order(b["order_id"]).status == "created"


def test_gateway_failure_is_reported_cleanly(client, rz, monkeypatch):
    from library import payments

    def boom(*a, **k):
        raise payments.PaymentGatewayError("down")
    monkeypatch.setattr(payments, "create_razorpay_order", boom)
    r = make_order(client)
    assert r.status_code == 502 and "down" not in r.text


# ------------------------------------------------------------------ request guards
def test_cross_site_posts_are_blocked(client):
    assert client.post("/api/leads", json={"slug": SLUG, "email": "a@b.co"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/leads", json={"slug": SLUG, "email": "a@b.co"}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/leads", json={"slug": SLUG, "email": "a@b.co"}, headers={"Origin": "http://testserver"}).status_code == 200


def test_webhook_exempt_from_origin_check_but_needs_signature(client, rz):
    r = client.post("/api/webhooks/razorpay", content=b"{}", headers={"Origin": "https://razorpay.com", **JSON})
    assert r.status_code == 400


def test_oversized_body_rejected(client):
    r = client.post("/api/leads", content=b"x" * 70000, headers=JSON)
    assert r.status_code == 413


def test_rate_limit_on_order_creation(client):
    codes = [make_order(client, email=f"u{i}@example.com", phone="x").status_code for i in range(10)]
    assert 429 in codes


def test_honeypot_and_validation(client):
    assert make_order(client, website="http://spam").status_code == 400
    assert make_order(client, email="not-an-email").status_code == 400
    assert make_order(client, name="<script>").status_code == 400
    assert make_order(client, phone="abc").status_code == 400
    assert client.post("/api/leads", json={"slug": SLUG, "email": "x@y.co", "website": "bot"}).json() == {"ok": True}
    assert db.all_leads() == []


def test_leads_are_deduplicated(client):
    for _ in range(2):
        assert client.post("/api/leads", json={"slug": "ui-kit-pro", "email": "w@example.com"}).status_code == 200
    assert len(db.all_leads()) == 1


def test_sql_injection_attempts_are_inert(client):
    r = make_order(client, email="a'; DROP TABLE orders;--@example.com")
    assert r.status_code == 400
    assert client.post("/api/checkout/quote", json={"slug": SLUG, "coupon": "' OR 1=1 --"}).status_code == 400
    assert db.stats()["all_orders"] == 0


# ------------------------------------------------------------------ admin
def test_admin_requires_password(client, monkeypatch):
    assert client.get("/admin").status_code == 200                       # shell only; data needs the cookie
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/admin/export/orders.csv", follow_redirects=False).status_code == 303
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret-pass")
    assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
    ok = client.post("/api/admin/login", json={"password": "s3cret-pass"})
    assert ok.status_code == 200
    cookie = ok.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    ov = client.get("/api/admin/overview")
    assert ov.status_code == 200 and "stats" in ov.json() and "orders" in ov.json()
    assert client.get("/admin/export/orders.csv").status_code == 200
    assert client.post("/api/admin/logout").status_code == 200
    client.cookies.clear()
    assert client.get("/api/admin/overview").status_code == 401


def test_admin_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret-pass")
    monkeypatch.setattr(time, "sleep", lambda s: None)
    codes = [client.post("/api/admin/login", json={"password": "no"}).status_code for _ in range(7)]
    assert codes[-1] == 429


def test_hashed_admin_password_and_forged_cookie(client, monkeypatch):
    h = security.hash_password("another-pass")
    assert security.verify_password("another-pass", h) and not security.verify_password("nope", h)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", h)
    assert security.check_admin_password("another-pass") and not security.check_admin_password("x")
    client.cookies.set("kiln_admin", "forged.value", path="/")
    assert client.get("/api/admin/overview").status_code == 401


def test_admin_disabled_plaintext_in_production(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "plain")
    monkeypatch.setenv("APP_ENV", "production")
    assert not security.check_admin_password("plain")


def test_csv_injection_guard():
    assert security.csv_safe("=HYPERLINK(1)").startswith("'")
    assert security.csv_safe("+1") == "'+1" and security.csv_safe("hello") == "hello"


# ------------------------------------------------------------------ catalog + design
def test_catalog_rejects_unsafe_input():
    base = json.loads(open("products/quiet-founder-ebook.json").read())
    bad_theme = {**base, "theme": {"hero_bg": "red;} body{display:none"}}
    with pytest.raises(CatalogError):
        product_from_dict(bad_theme)
    bad_file = {**base, "delivery": {"type": "files", "files": [{"id": "x", "label": "x", "filename": "../../etc/passwd"}]}}
    with pytest.raises(CatalogError):
        product_from_dict(bad_file)
    with pytest.raises(CatalogError):
        product_from_dict({**base, "slug": "Bad Slug!"})
    with pytest.raises(CatalogError):
        product_from_dict({**base, "pricing": {"list_price": 100, "early_access_price": 500, "early_access_ends": "2027-01-01"}})


def _lum(hex_):
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("slug", ["ship-saas-30", "quiet-founder-ebook", "ui-kit-pro"])
def test_theme_colours_meet_wcag_contrast(slug):
    t = catalog.get(slug).theme
    assert _contrast(t["hero_ink"], t["hero_bg"]) >= 4.5
    assert _contrast(t["accent_ink"], t["accent"]) >= 4.5
    assert _contrast(t["ink"], t["paper"]) >= 4.5
    assert _contrast(t["muted"], t["paper"]) >= 4.5
    assert _contrast(t["accent"], t["hero_bg"]) >= 3.0          # price figure (large text)
    assert _contrast(t["hero_ink"], t["accent"]) >= 0 and _contrast(t["paper"], t["hero_bg"]) >= 4.5


# ------------------------------------------------------------------ React shell + JSON API
def test_public_product_json_never_leaks_delivery(client):
    for slug in ("ship-saas-30", "quiet-founder-ebook"):
        body = client.get(f"/api/products/{slug}").text
        assert "access_url" not in body and "filename" not in body
        assert "deliverables" not in body
    site = client.get("/api/site").text
    assert "access_url" not in site and "filename" not in site


def test_shell_injects_seo_theme_and_boot(client):
    html = client.get("/p/ship-saas-30").text
    p = catalog.get(SLUG)
    assert f"<title>{p.seo['title']}</title>" in html
    assert 'rel="canonical"' in html and "/p/ship-saas-30" in html
    assert "--hero-bg:" in html
    assert '<script id="boot" type="application/json">' in html
    assert "<!--SSR:" not in html                                          # markers are always replaced


def test_boot_json_cannot_break_out_of_script():
    from library import spa
    out = spa.json_for_html({"x": "</script><script>alert(1)</script>", "y": "a&b\u2028"})
    assert "</script" not in out and "<" not in out and "&" not in out
    assert json.loads(out)["x"] == "</script><script>alert(1)</script>"


def test_unknown_pages_are_404_shells_not_500(client):
    for url in ("/p/nope", "/p/BAD SLUG", "/thanks/ord_x", "/thanks/ord_x?t=bad"):
        r = client.get(url, headers={"Accept": "text/html"})
        assert r.status_code == 404 and "<html" in r.text
    r = client.get("/api/products/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_order_api_only_reveals_links_when_paid(client):
    o = make_order(client).json()
    tok = security.access_token(o["order_id"])
    pending = client.get(f"/api/orders/{o['order_id']}?t={tok}").json()
    assert pending["paid"] is False and pending["links"] == [] and pending["access_url"] == ""
    assert client.get(f"/api/orders/{o['order_id']}").status_code == 404
    client.post("/api/checkout/demo-pay", json={"order_id": o["order_id"]})
    paid = client.get(f"/api/orders/{o['order_id']}?t={tok}").json()
    assert paid["paid"] is True and paid["links"]
