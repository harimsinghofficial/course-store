"""Configuration: tunables from config.json, secrets from environment / .env.

config.json holds every non-secret tunable. Secrets (API keys, SECRET_KEY, SMTP
password) are NEVER stored in config.json - they come from environment variables,
optionally loaded from a local `.env` file.
"""
from __future__ import annotations

import functools
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR: Path = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (KEY=VALUE, # comments, optional quotes). Real env wins."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


@functools.cache
def load_config() -> Dict[str, Any]:
    with open(BASE_DIR / "config.json", encoding="utf-8") as fh:
        return json.load(fh)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def app_env() -> str:
    return env("APP_ENV", "development").lower()


def is_production() -> bool:
    return app_env() == "production"


def base_url() -> str:
    return env("BASE_URL", "http://localhost:8000").rstrip("/")


def allowed_hosts() -> list[str]:
    raw = env("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    hosts = [h.strip() for h in raw.split(",") if h.strip()]
    return hosts or ["localhost"]


def razorpay_credentials() -> Optional[tuple[str, str]]:
    key_id, key_secret = env("RAZORPAY_KEY_ID"), env("RAZORPAY_KEY_SECRET")
    if key_id and key_secret:
        return key_id, key_secret
    return None


def payment_mode() -> str:
    """'razorpay' when keys are present, 'demo' in development without keys, else 'disabled'."""
    if razorpay_credentials():
        return "razorpay"
    return "disabled" if is_production() else "demo"


def analytics_ids() -> Dict[str, str]:
    return {"ga4": env("GA4_ID"), "meta_pixel": env("META_PIXEL_ID")}


@functools.cache
def secret_key() -> bytes:
    """Signing key for tokens/cookies. Required in production; auto-created in dev."""
    value = env("SECRET_KEY")
    if value:
        if len(value) < 32 and is_production():
            raise RuntimeError("SECRET_KEY must be at least 32 characters in production.")
        return value.encode()
    if is_production():
        raise RuntimeError("SECRET_KEY is required when APP_ENV=production.")
    dev_file = BASE_DIR / "data" / ".dev_secret"
    dev_file.parent.mkdir(parents=True, exist_ok=True)
    if not dev_file.exists():
        dev_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        try:
            dev_file.chmod(0o600)
        except OSError:
            pass
    return dev_file.read_text(encoding="utf-8").strip().encode()


def resolve(relative: str) -> Path:
    """Resolve a config path relative to the project folder."""
    p = Path(relative)
    return p if p.is_absolute() else BASE_DIR / p
