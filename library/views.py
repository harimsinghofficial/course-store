"""JSON shapes the React app consumes.

Rule of thumb: anything here is PUBLIC. Delivery file names and the private access link are never included
for anonymous visitors; they are only returned by order_payload() for a verified, paid order.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from library import db, delivery, mailer, pricing
from library.catalog import IST, Product, catalog
from library.config import analytics_ids, load_config, payment_mode


def site_payload() -> Dict[str, Any]:
    cfg = load_config()
    site = cfg["site"]
    items = []
    for p in catalog.products():
        items.append({
            "slug": p.slug, "name": p.name, "tagline": p.tagline, "status": p.status,
            "color": p.theme["hero_bg"], "price_paise": pricing.base_price_paise(p)[0],
            "guarantee_days": p.guarantee["days"],
        })
    return {
        "site": {k: site.get(k, "") for k in ("name", "tagline", "home_product", "support_email", "legal_name",
                                              "address", "support_phone", "price_note")},
        "payment_mode": payment_mode(),
        "mail_on": mailer.enabled(),
        "razorpay_script": cfg["razorpay"]["checkout_script"],
        "analytics": analytics_ids(),
        "catalog": items,
    }


def product_payload(p: Product) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    base, early = pricing.base_price_paise(p, now)
    left = pricing.seats_left(p)
    sold_out = left == 0
    can_buy = p.purchasable and not sold_out and payment_mode() != "disabled"
    ends = p.pricing.early_access_ends if early else None
    return {
        "slug": p.slug, "type": p.type, "name": p.name, "tagline": p.tagline, "headline": p.headline,
        "subhead": p.subhead, "hero_word": p.hero_word, "cta_label": p.cta_label, "theme": p.theme,
        "stats": p.stats, "outcomes": p.outcomes, "problem": p.problem, "modules": p.modules,
        "includes": p.includes, "audience": p.audience, "instructor": p.instructor,
        "testimonials": p.testimonials, "faq": p.faq, "guarantee": p.guarantee, "seo": p.seo,
        "delivery": {"type": p.delivery.type, "instructions": p.delivery.instructions},   # no files, no link
        "pstatus": p.effective_status(now),
        "base_paise": base, "list_paise": p.pricing.list_price * 100, "early": early,
        "launch_price_paise": (p.pricing.early_access_price or p.pricing.list_price) * 100,
        "ends_iso": ends.isoformat() if ends else "",
        "ends_text": f"{ends.astimezone(IST).day} {ends.astimezone(IST):%B %Y}" if ends else "",
        "seats_left": left, "seats_total": p.pricing.seats_total,
        "sold_out": sold_out, "can_buy": can_buy,
    }


def order_payload(order: db.Order, p: Optional[Product]) -> Dict[str, Any]:
    """Order page data. Delivery details appear only once the order is paid."""
    out: Dict[str, Any] = {
        "public_id": order.public_id, "status": order.status, "paid": order.paid, "mode": order.mode,
        "first_name": order.name.split(" ")[0], "email": order.email, "amount_paise": order.amount_paise,
        "value": f"{order.amount_paise / 100:.2f}" if order.mode == "razorpay" else "0",
        "product": None, "links": [], "access_url": "",
    }
    if p is not None:
        out["product"] = {"slug": p.slug, "name": p.name, "theme": p.theme, "delivery_type": p.delivery.type,
                          "instructions": p.delivery.instructions}
        if order.paid:
            if p.delivery.type in ("files", "both"):
                out["links"] = delivery.download_links(order.public_id, p)
            if p.delivery.type in ("link", "both"):
                out["access_url"] = p.delivery.access_url
    return out
