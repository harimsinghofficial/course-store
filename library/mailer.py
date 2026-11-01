"""Optional transactional email via SMTP. Silently does nothing when SMTP_HOST is not set."""
from __future__ import annotations

import html
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from typing import Any

from library import error
from library.config import env, load_config
from library.db import Order
from library.retry import retry

_CFG = load_config()["mailer"]


def enabled() -> bool:
    return bool(env("SMTP_HOST"))


@retry(times=_CFG["retry_times"], exceptions=(OSError, smtplib.SMTPException), delay=_CFG["retry_delay_s"])
def _send(msg: EmailMessage) -> None:
    host, port = env("SMTP_HOST"), int(env("SMTP_PORT", "587") or 587)
    ctx = ssl.create_default_context()
    if port == 465:
        server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=_CFG["timeout_s"], context=ctx)
    else:
        server = smtplib.SMTP(host, port, timeout=_CFG["timeout_s"])
    with server:
        if port != 465:
            server.starttls(context=ctx)
        if env("SMTP_USER"):
            server.login(env("SMTP_USER"), env("SMTP_PASSWORD"))
        server.send_message(msg)


def send_order_email(order: Order, product_name: str, access_url: str, site_name: str, support: str) -> None:
    """Called from a background task; never raises."""
    if not enabled():
        return
    first = order.name.split(" ")[0]
    text = (f"Hi {first},\n\nThanks for buying {product_name}. Your payment is confirmed.\n\n"
            f"Open your order page for access and downloads:\n{access_url}\n\n"
            f"Order reference: {order.public_id}\nQuestions? Reply to this email or write to {support}.\n\n{site_name}\n")
    body: Any = (
        f"<p>Hi {html.escape(first)},</p><p>Thanks for buying <strong>{html.escape(product_name)}</strong>. "
        f"Your payment is confirmed.</p><p><a href=\"{html.escape(access_url, quote=True)}\">Open your order page</a> "
        f"for access and downloads.</p><p>Order reference: {html.escape(order.public_id)}<br>"
        f"Questions? Write to {html.escape(support)}.</p><p>{html.escape(site_name)}</p>"
    )
    msg = EmailMessage()
    msg["Subject"] = f"Your access to {product_name}".replace("\r", " ").replace("\n", " ")[:150]
    msg["From"] = env("SMTP_FROM") or env("SMTP_USER")
    msg["To"] = order.email
    msg["Message-ID"] = f"<{uuid.uuid4()}@{(env('SMTP_HOST') or 'localhost')}>"
    msg.set_content(text)
    msg.add_alternative(f"<html><body>{body}</body></html>", subtype="html")
    try:
        _send(msg)
    except Exception as exc:            # email must never break the payment flow
        error.write(order.public_id, "order_email", "mailer.send", exc)
