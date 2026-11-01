"""Security toolkit: signed tokens, password hashing, validation, rate limiting, ASGI middleware.

CLI helper:  python -m library.security hash "my admin password"
"""
from __future__ import annotations

import base64
import functools
import hashlib
import hmac
import re
import secrets
import sys
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple
from urllib.parse import urlsplit

from library.config import (allowed_hosts, analytics_ids, base_url, is_production, load_config,
                            payment_mode, secret_key)

_SEC = load_config()["security"]


# ------------------------------------------------------------------ signed tokens
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(purpose: str, payload: str) -> bytes:
    return hmac.new(secret_key(), f"{purpose}|{payload}".encode(), hashlib.sha256).digest()


def sign(purpose: str, payload: str) -> str:
    return f"{_b64(payload.encode())}.{_b64(_mac(purpose, payload))}"


def unsign(purpose: str, token: str) -> Optional[str]:
    try:
        body, sig = token.split(".", 1)
        payload = _unb64(body).decode()
        if hmac.compare_digest(_unb64(sig), _mac(purpose, payload)):
            return payload
    except (ValueError, UnicodeDecodeError):
        pass
    return None


def access_token(public_id: str) -> str:
    """Stable per-order token: lets the buyer (or the confirmation email) reopen their order page."""
    return _b64(_mac("access", public_id))[:32]


def verify_access(public_id: str, token: str) -> bool:
    return bool(token) and hmac.compare_digest(access_token(public_id), token)


def download_token(public_id: str, file_id: str) -> str:
    exp = int(time.time()) + int(_SEC["download_token_ttl_s"])
    return sign("download", f"{public_id}|{file_id}|{exp}")


def parse_download_token(token: str) -> Optional[Tuple[str, str]]:
    payload = unsign("download", token)
    if not payload:
        return None
    try:
        public_id, file_id, exp = payload.split("|")
        if int(exp) < time.time():
            return None
    except ValueError:
        return None
    return public_id, file_id


def new_admin_session() -> str:
    return sign("admin", str(int(time.time()) + int(_SEC["session_ttl_s"])))


def valid_admin_session(token: Optional[str]) -> bool:
    if not token:
        return False
    payload = unsign("admin", token)
    return bool(payload and payload.isdigit() and int(payload) > time.time())


def hash_ip(ip: str) -> str:
    return hashlib.sha256(secret_key() + ip.encode()).hexdigest()[:20]


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, _unb64(digest))
    except (ValueError, TypeError):
        return False


def check_admin_password(password: str) -> bool:
    from library.config import env
    stored = env("ADMIN_PASSWORD_HASH")
    if stored:
        return verify_password(password, stored)
    plain = env("ADMIN_PASSWORD")
    if plain and not is_production():
        return hmac.compare_digest(plain.encode(), password.encode())
    return False


# ------------------------------------------------------------------ validation
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
PHONE_RE = re.compile(r"^\+?[0-9]{8,15}$")
_CTRL = re.compile(r"[\x00-\x1f\x7f<>]")
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid", "fbclid", "ref")


def clean_email(value: str) -> Optional[str]:
    v = (value or "").strip().lower()
    return v if len(v) <= 254 and EMAIL_RE.match(v) else None


def clean_name(value: str) -> Optional[str]:
    if re.search(r"[<>]", value or ""):
        return None
    v = re.sub(r"\s+", " ", _CTRL.sub("", value or "")).strip()
    return v if 2 <= len(v) <= 80 else None


def clean_phone(value: str) -> Optional[str]:
    v = re.sub(r"[\s-]", "", value or "")
    if not v:
        return ""
    return v if PHONE_RE.match(v) else None


def clean_utm(raw: Optional[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k in UTM_KEYS:
        v = (raw or {}).get(k)
        if isinstance(v, str) and v:
            out[k] = _CTRL.sub("", v)[:100]
    return out


def csv_safe(value: Any) -> str:
    """Neutralise spreadsheet formula injection when exporting user-supplied text."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


# ------------------------------------------------------------------ rate limiting
class RateLimiter:
    """In-memory sliding window. Per process: with N workers the effective limit is up to N times higher.
    For a hard global limit put nginx / Cloudflare rate limiting in front (see README)."""

    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    def allow(self, key: str, limit: int, window_s: int) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last_prune > 120:
                self._prune(now)
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def _prune(self, now: float) -> None:
        self._last_prune = now
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] > 3600]:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def rate_ok(bucket: str, ip: str) -> bool:
    cfg = _SEC["rate_limits"][bucket]
    return limiter.allow(f"{bucket}:{ip}", cfg["limit"], cfg["window_s"])


# ------------------------------------------------------------------ headers / CSP
@functools.cache
def build_csp() -> str:
    mode, ids = payment_mode(), analytics_ids()
    script = ["'self'"]
    connect = ["'self'"]
    img = ["'self'", "data:"]
    frame = ["'none'"]
    form = ["'self'"]
    if mode == "razorpay":
        script.append("https://checkout.razorpay.com")
        connect += ["https://lumberjack.razorpay.com", "https://api.razorpay.com"]
        img.append("https://*.razorpay.com")
        frame = ["https://api.razorpay.com", "https://checkout.razorpay.com"]
        form.append("https://api.razorpay.com")
    if ids["ga4"]:
        script.append("https://www.googletagmanager.com")
        connect += ["https://www.google-analytics.com", "https://*.google-analytics.com",
                    "https://*.analytics.google.com", "https://www.googletagmanager.com"]
        img += ["https://www.google-analytics.com", "https://www.googletagmanager.com"]
    if ids["meta_pixel"]:
        script.append("https://connect.facebook.net")
        connect += ["https://www.facebook.com", "https://connect.facebook.net"]
        img.append("https://www.facebook.com")
    parts = [
        "default-src 'self'",
        f"script-src {' '.join(script)}",
        "style-src 'self' 'unsafe-inline'",
        f"img-src {' '.join(img)}",
        "font-src 'self'",
        f"connect-src {' '.join(connect)}",
        f"frame-src {' '.join(frame)}",
        "object-src 'none'",
        "base-uri 'none'",
        f"form-action {' '.join(form)}",
        "frame-ancestors 'none'",
    ]
    if is_production():
        parts.append("upgrade-insecure-requests")
    return "; ".join(parts)


def security_headers() -> list[tuple[bytes, bytes]]:
    h = {
        "content-security-policy": build_csp(),
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": 'camera=(), microphone=(), geolocation=(), '
                              'payment=(self "https://api.razorpay.com" "https://checkout.razorpay.com")',
        "cross-origin-opener-policy": "same-origin-allow-popups",
        "cross-origin-resource-policy": "same-origin",
        "x-permitted-cross-domain-policies": "none",
    }
    if is_production():
        h["strict-transport-security"] = f"max-age={int(_SEC['hsts_max_age_s'])}; includeSubDomains"
    return [(k.encode(), v.encode()) for k, v in h.items()]


_NO_STORE_PREFIXES = ("/api/", "/admin", "/thanks", "/download")


class SecurityHeadersMiddleware:
    """Pure-ASGI (fast) middleware adding security headers and no-store on sensitive paths."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self._headers = security_headers()

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")

        async def send_wrapper(message: Dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {k.lower() for k, _ in headers}
                headers += [(k, v) for k, v in self._headers if k not in names]
                if b"cache-control" not in names and path.startswith(_NO_STORE_PREFIXES):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


async def _plain(send: Any, status: int, text: str) -> None:
    body = text.encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                            (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


class RequestGuardMiddleware:
    """Cheap, early rejection of: oversized/unsized bodies, cross-site state-changing requests,
    and clients hammering the site. Webhooks are exempt from the Origin check (they use signatures)."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}

        if not path.startswith("/static/"):
            ip = (scope.get("client") or ("unknown", 0))[0]
            if not rate_ok("global", ip):
                await _plain(send, 429, "Too many requests. Please slow down.")
                return

        if method in ("POST", "PUT", "PATCH", "DELETE"):
            length = headers.get("content-length")
            if length is None:
                await _plain(send, 411, "Length required")
                return
            if not length.isdigit() or int(length) > int(_SEC["max_body_bytes"]):
                await _plain(send, 413, "Request too large")
                return
            if not path.startswith("/api/webhooks/") and not _same_origin(headers):
                await _plain(send, 403, "Cross-site request blocked")
                return
        await self.app(scope, receive, send)


def _same_origin(headers: Dict[str, str]) -> bool:
    fetch_site = headers.get("sec-fetch-site")
    if fetch_site and fetch_site not in ("same-origin", "none"):
        return False
    origin = headers.get("origin")
    if not origin:
        return True            # non-browser client (curl, server-to-server); browsers always send Origin on POST
    try:
        host = urlsplit(origin).netloc.lower()
    except ValueError:
        return False
    if host == headers.get("host", "").lower():
        return True
    return host == urlsplit(base_url()).netloc.lower()


def trusted_hosts() -> list[str]:
    return allowed_hosts()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "hash":
        print(hash_password(sys.argv[2]))
    else:
        print('usage: python -m library.security hash "your password"')
        sys.exit(2)
