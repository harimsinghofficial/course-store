"""Product catalog: loads, validates and caches products/*.json and utility/coupons.json.

Adding a product = dropping a new JSON file into products/. No code changes.
Invalid files are skipped (and reported) so one typo can never take the store down.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from library.config import load_config, resolve

IST = timezone(timedelta(hours=5, minutes=30))
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,120}$")
ID_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
STATUSES = {"live", "early_access", "coming_soon", "archived"}
THEME_KEYS = ("hero_bg", "hero_ink", "accent", "accent_ink", "paper", "ink", "muted")
DEFAULT_THEME: Dict[str, str] = {
    "hero_bg": "#2B2BFF",
    "hero_ink": "#FFFFFF",
    "accent": "#FFD60A",
    "accent_ink": "#12123A",
    "paper": "#F4F3FF",
    "ink": "#12123A",
    "muted": "#54547A",
}


class CatalogError(ValueError):
    def __init__(self, problems: List[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class Pricing:
    currency: str
    list_price: int                      # whole rupees
    early_access_price: Optional[int] = None
    early_access_ends: Optional[datetime] = None
    seats_total: Optional[int] = None


@dataclass
class DeliveryFile:
    id: str
    label: str
    filename: str


@dataclass
class Delivery:
    type: str = "files"                  # files | link | both
    files: List[DeliveryFile] = field(default_factory=list)
    access_url: str = ""
    instructions: str = ""


@dataclass
class Product:
    slug: str
    status: str
    type: str
    name: str
    tagline: str
    headline: str
    subhead: str
    hero_word: str
    cta_label: str
    theme: Dict[str, str]
    pricing: Pricing
    stats: List[Dict[str, Any]]
    outcomes: List[str]
    problem: Dict[str, str]
    modules: List[Dict[str, Any]]
    includes: List[Dict[str, str]]
    audience: Dict[str, List[str]]
    instructor: Dict[str, str]
    testimonials: List[Dict[str, str]]
    faq: List[Dict[str, str]]
    guarantee: Dict[str, Any]
    delivery: Delivery
    seo: Dict[str, str]
    source_file: str = ""

    def effective_status(self, now: Optional[datetime] = None) -> str:
        """An early-access product whose window has closed behaves as 'live'."""
        now = now or datetime.now(timezone.utc)
        if self.status == "early_access":
            ends = self.pricing.early_access_ends
            if ends is not None and now >= ends:
                return "live"
        return self.status

    @property
    def purchasable(self) -> bool:
        return self.status in {"live", "early_access"}


@dataclass
class Coupon:
    code: str
    percent: int = 0
    flat_off: int = 0                    # whole rupees
    products: List[str] = field(default_factory=lambda: ["*"])
    max_uses: Optional[int] = None
    expires: Optional[datetime] = None
    active: bool = True


# ----------------------------------------------------------------- parsing helpers
def _parse_dt(value: Any, where: str, problems: List[str]) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        problems.append(f"{where}: '{value}' is not an ISO date-time (e.g. 2026-12-15T23:59:00+05:30)")
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)


def _str(d: Dict[str, Any], key: str, default: str = "", max_len: int = 600) -> str:
    v = d.get(key, default)
    return str(v).strip()[:max_len] if v is not None else default


def _list_of_dicts(raw: Any, keys: Tuple[str, ...], where: str, problems: List[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for i, item in enumerate(raw or []):
        if not isinstance(item, dict):
            problems.append(f"{where}[{i}] must be an object")
            continue
        out.append({k: str(item.get(k, "")).strip() for k in keys})
    return out


def product_from_dict(raw: Dict[str, Any], source: str = "") -> Product:
    problems: List[str] = []

    def need(key: str) -> Any:
        if key not in raw or raw[key] in (None, ""):
            problems.append(f"missing required field '{key}'")
        return raw.get(key)

    slug = str(need("slug") or "")
    if slug and not SLUG_RE.match(slug):
        problems.append("slug must be lowercase letters, digits and hyphens (2-63 chars)")
    status = str(raw.get("status", "live"))
    if status not in STATUSES:
        problems.append(f"status must be one of {sorted(STATUSES)}")
    name = str(need("name") or "")
    headline = str(need("headline") or "")
    subhead = str(need("subhead") or "")

    # ---- pricing
    praw = raw.get("pricing")
    pricing: Optional[Pricing] = None
    if not isinstance(praw, dict):
        problems.append("missing required object 'pricing'")
    else:
        lp = praw.get("list_price")
        ep = praw.get("early_access_price")
        if not isinstance(lp, int) or isinstance(lp, bool) or lp < 1:
            problems.append("pricing.list_price must be a whole number of rupees (>= 1)")
        if ep is not None and (not isinstance(ep, int) or isinstance(ep, bool) or ep < 1):
            problems.append("pricing.early_access_price must be a whole number of rupees (>= 1)")
        if isinstance(lp, int) and isinstance(ep, int) and ep > lp:
            problems.append("pricing.early_access_price must not exceed list_price")
        seats = praw.get("seats_total")
        if seats is not None and (not isinstance(seats, int) or seats < 1):
            problems.append("pricing.seats_total must be a positive integer")
        if str(praw.get("currency", "INR")).upper() != "INR":
            problems.append("only currency 'INR' is supported")
        ends = _parse_dt(praw.get("early_access_ends"), "pricing.early_access_ends", problems)
        if ep is not None and ends is None:
            problems.append("pricing.early_access_ends is required when early_access_price is set")
        if not problems:
            pricing = Pricing("INR", lp, ep, ends, seats)

    # ---- theme (hex only: it is written into CSS)
    theme = dict(DEFAULT_THEME)
    for k, v in (raw.get("theme") or {}).items():
        if k not in THEME_KEYS:
            problems.append(f"theme.{k} is not a known colour (use {', '.join(THEME_KEYS)})")
        elif not HEX_RE.match(str(v)):
            problems.append(f"theme.{k} must be a 6-digit hex colour like #12AB34")
        else:
            theme[k] = str(v)

    # ---- delivery
    draw = raw.get("delivery") or {}
    files: List[DeliveryFile] = []
    for i, f in enumerate(draw.get("files") or []):
        fid, label, fname = str(f.get("id", "")), str(f.get("label", "")), str(f.get("filename", ""))
        if not ID_RE.match(fid):
            problems.append(f"delivery.files[{i}].id must match [a-z0-9_-]")
        if not FILENAME_RE.match(fname) or ".." in fname:
            problems.append(f"delivery.files[{i}].filename has unsafe characters")
        files.append(DeliveryFile(fid, label[:120], fname))
    dtype = str(draw.get("type", "files"))
    if dtype not in {"files", "link", "both"}:
        problems.append("delivery.type must be files, link or both")
    access_url = str(draw.get("access_url", "")).strip()
    if access_url and not access_url.startswith("https://"):
        problems.append("delivery.access_url must start with https://")

    includes = _list_of_dicts(raw.get("includes"), ("title", "detail"), "includes", problems)
    testimonials = _list_of_dicts(raw.get("testimonials"), ("quote", "name", "role"), "testimonials", problems)
    faq = _list_of_dicts(raw.get("faq"), ("q", "a"), "faq", problems)

    if problems:
        raise CatalogError(problems)
    assert pricing is not None

    stats = []
    for s in raw.get("stats") or []:
        if isinstance(s, dict) and isinstance(s.get("value"), (int, float)) and not isinstance(s.get("value"), bool):
            stats.append({"value": s["value"], "suffix": str(s.get("suffix", "")), "label": str(s.get("label", ""))})

    modules = []
    for m in raw.get("modules") or []:
        if isinstance(m, dict):
            modules.append({
                "title": str(m.get("title", "")),
                "summary": str(m.get("summary", "")),
                "duration": str(m.get("duration", "")),
                "lessons": [str(x) for x in (m.get("lessons") or [])],
            })

    aud = raw.get("audience") or {}
    return Product(
        slug=slug,
        status=status,
        type=_str(raw, "type", "course", 30),
        name=name[:120],
        tagline=_str(raw, "tagline", "", 200),
        headline=headline[:200],
        subhead=subhead[:500],
        hero_word=_str(raw, "hero_word", name.split(" ")[0] if name else "NEW", 14).upper(),
        cta_label=_str(raw, "cta_label", "Enroll now", 40),
        theme=theme,
        pricing=pricing,
        stats=stats,
        outcomes=[str(x) for x in (raw.get("outcomes") or [])][:20],
        problem={"title": str((raw.get("problem") or {}).get("title", "")),
                 "body": str((raw.get("problem") or {}).get("body", ""))},
        modules=modules,
        includes=includes,
        audience={"for": [str(x) for x in aud.get("for", [])], "not_for": [str(x) for x in aud.get("not_for", [])]},
        instructor={k: str((raw.get("instructor") or {}).get(k, "")) for k in ("name", "role", "bio", "initials")},
        testimonials=testimonials,
        faq=faq,
        guarantee={"days": int((raw.get("guarantee") or {}).get("days", 0) or 0),
                   "text": str((raw.get("guarantee") or {}).get("text", ""))},
        delivery=Delivery(dtype, files, access_url, str(draw.get("instructions", ""))[:1000]),
        seo={"title": _str(raw.get("seo") or {}, "title", name, 70),
             "description": _str(raw.get("seo") or {}, "description", subhead, 170)},
        source_file=source,
    )


def coupon_from_dict(raw: Dict[str, Any]) -> Coupon:
    cfg = load_config()["pricing"]
    code = str(raw.get("code", "")).strip().upper()
    if not re.match(r"^[A-Z0-9_-]{3,32}$", code):
        raise CatalogError([f"coupon code '{code}' must be 3-32 chars of A-Z, 0-9, _ or -"])
    percent, flat = int(raw.get("percent", 0) or 0), int(raw.get("flat_off", 0) or 0)
    if not (0 <= percent <= cfg["max_coupon_percent"]):
        raise CatalogError([f"coupon {code}: percent must be 0-{cfg['max_coupon_percent']}"])
    if percent == 0 and flat <= 0:
        raise CatalogError([f"coupon {code}: set percent or flat_off"])
    problems: List[str] = []
    expires = _parse_dt(raw.get("expires"), f"coupon {code}.expires", problems)
    if problems:
        raise CatalogError(problems)
    return Coupon(code, percent, flat, [str(p) for p in raw.get("products", ["*"])],
                  raw.get("max_uses"), expires, bool(raw.get("active", True)))


# ----------------------------------------------------------------- catalog store
class Catalog:
    """Thread-safe in-memory catalog that notices file changes (cheap mtime check)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._products: Dict[str, Product] = {}
        self._coupons: Dict[str, Coupon] = {}
        self._errors: List[str] = []
        self._stamp: Tuple[float, ...] = ()
        self._checked_at = 0.0

    @staticmethod
    def _files() -> List[Path]:
        cfg = load_config()["catalog"]
        pdir = resolve(cfg["products_dir"])
        files = sorted(p for p in pdir.glob("*.json") if not p.name.startswith("_")) if pdir.is_dir() else []
        cfile = resolve(cfg["coupons_file"])
        if cfile.is_file():
            files.append(cfile)
        return files

    def _current_stamp(self) -> Tuple[float, ...]:
        return tuple(sorted((hash(str(p)) % 10**9) + p.stat().st_mtime for p in self._files()))

    def load(self) -> List[str]:
        cfg = load_config()["catalog"]
        products: Dict[str, Product] = {}
        coupons: Dict[str, Coupon] = {}
        errors: List[str] = []
        for path in self._files():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if path.name == Path(cfg["coupons_file"]).name:
                    for c in data if isinstance(data, list) else []:
                        coupon = coupon_from_dict(c)
                        coupons[coupon.code] = coupon
                else:
                    p = product_from_dict(data, path.name)
                    if p.slug in products:
                        raise CatalogError([f"duplicate slug '{p.slug}'"])
                    products[p.slug] = p
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"{path.name}: cannot read ({exc})")
            except CatalogError as exc:
                errors.append(f"{path.name}: " + "; ".join(exc.problems))
        with self._lock:
            self._products, self._coupons, self._errors = products, coupons, errors
            self._stamp = self._current_stamp()
            self._checked_at = time.monotonic()
        return errors

    def _maybe_reload(self) -> None:
        interval = load_config()["catalog"]["reload_check_s"]
        if time.monotonic() - self._checked_at < interval:
            return
        self._checked_at = time.monotonic()
        try:
            if self._current_stamp() != self._stamp:
                self.load()
        except OSError:
            pass

    @property
    def errors(self) -> List[str]:
        return list(self._errors)

    def products(self, include_hidden: bool = False) -> List[Product]:
        self._maybe_reload()
        items = list(self._products.values())
        return items if include_hidden else [p for p in items if p.status != "archived"]

    def get(self, slug: str) -> Optional[Product]:
        self._maybe_reload()
        p = self._products.get(slug)
        return p

    def coupon(self, code: str) -> Optional[Coupon]:
        self._maybe_reload()
        return self._coupons.get(code.strip().upper())


catalog = Catalog()
