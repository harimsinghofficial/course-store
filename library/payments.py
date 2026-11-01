"""Razorpay integration: order creation + signature verification (REST API, no SDK needed).

Flow
  1. server creates a Razorpay order for an amount IT computed          -> create_razorpay_order
  2. browser opens Razorpay Checkout with that order id
  3. browser sends back order_id + payment_id + signature                -> verify_payment_signature
  4. Razorpay also calls our webhook as a safety net                     -> verify_webhook_signature
Signatures are HMAC-SHA256 and are compared in constant time.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any, Dict

import httpx

from library.config import env, load_config, razorpay_credentials
from library.retry import retry

_CFG = load_config()["razorpay"]


class PaymentGatewayError(RuntimeError):
    """The gateway refused or failed. Message is safe to log; not shown verbatim to buyers."""


class _Retryable(PaymentGatewayError):
    pass


@retry(times=_CFG["retry_times"], exceptions=(_Retryable,), delay=_CFG["retry_delay_s"])
def create_razorpay_order(amount_paise: int, receipt: str, notes: Dict[str, str]) -> Dict[str, Any]:
    creds = razorpay_credentials()
    if creds is None:
        raise PaymentGatewayError("Razorpay keys are not configured")
    try:
        with httpx.Client(timeout=_CFG["timeout_s"], auth=creds) as client:
            resp = client.post(
                f"{_CFG['api_base']}/orders",
                json={"amount": amount_paise, "currency": "INR", "receipt": receipt[:40], "notes": notes},
            )
    except httpx.TransportError as exc:
        raise _Retryable(f"network error talking to Razorpay: {exc.__class__.__name__}") from exc
    if resp.status_code >= 500 or resp.status_code == 429:
        raise _Retryable(f"Razorpay returned {resp.status_code}")
    if resp.status_code != 200:
        raise PaymentGatewayError(f"Razorpay rejected the order ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    if data.get("amount") != amount_paise or not str(data.get("id", "")).startswith("order_"):
        raise PaymentGatewayError("Razorpay returned an unexpected order payload")
    return data


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_payment_signature(rz_order_id: str, rz_payment_id: str, signature: str) -> bool:
    secret = env("RAZORPAY_KEY_SECRET")
    if not secret or not signature:
        return False
    expected = _hmac_hex(secret, f"{rz_order_id}|{rz_payment_id}".encode())
    return hmac.compare_digest(expected, signature.strip().lower())


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    secret = env("RAZORPAY_WEBHOOK_SECRET")
    if not secret or not signature:
        return False
    return hmac.compare_digest(_hmac_hex(secret, raw_body), signature.strip().lower())


# ------------------------------------------------------------------ demo mode
def new_demo_order_id() -> str:
    return "demo_order_" + secrets.token_hex(8)


def new_demo_payment_id() -> str:
    return "demo_pay_" + secrets.token_hex(8)
