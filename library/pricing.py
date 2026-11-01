"""Server-side price calculation. The browser never decides what a product costs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from library import db
from library.catalog import Coupon, Product, catalog
from library.config import load_config


class PricingError(ValueError):
    """Raised with a message that is safe to show to the buyer."""


@dataclass
class Quote:
    product_slug: str
    list_paise: int
    base_paise: int            # after early-access price, before coupon
    discount_paise: int
    amount_paise: int          # what the buyer pays
    early_access: bool
    coupon: str                # normalised code or ""
    coupon_label: str

    def to_dict(self) -> dict:
        return {
            "list_paise": self.list_paise, "base_paise": self.base_paise,
            "discount_paise": self.discount_paise, "amount_paise": self.amount_paise,
            "early_access": self.early_access, "coupon": self.coupon, "coupon_label": self.coupon_label,
        }


def base_price_paise(product: Product, now: Optional[datetime] = None) -> tuple[int, bool]:
    now = now or datetime.now(timezone.utc)
    p = product.pricing
    if (p.early_access_price is not None and p.early_access_ends is not None and now < p.early_access_ends):
        return p.early_access_price * 100, True
    return p.list_price * 100, False


def seats_left(product: Product) -> Optional[int]:
    if product.pricing.seats_total is None:
        return None
    return max(0, product.pricing.seats_total - db.count_paid_including_demo(product.slug))


def _check_coupon(coupon: Coupon, product: Product, now: datetime) -> None:
    if not coupon.active:
        raise PricingError("That code is no longer active.")
    if coupon.expires is not None and now >= coupon.expires:
        raise PricingError("That code has expired.")
    if "*" not in coupon.products and product.slug not in coupon.products:
        raise PricingError("That code doesn't apply to this product.")
    if coupon.max_uses is not None and db.coupon_uses(coupon.code) >= coupon.max_uses:
        raise PricingError("That code has been fully redeemed.")


def quote(product: Product, coupon_code: str = "", now: Optional[datetime] = None) -> Quote:
    now = now or datetime.now(timezone.utc)
    min_amount = load_config()["pricing"]["min_amount_paise"]
    if not product.purchasable:
        raise PricingError("This product isn't open for purchase yet.")
    base, early = base_price_paise(product, now)
    discount, applied, label = 0, "", ""
    code = (coupon_code or "").strip().upper()
    if code:
        coupon = catalog.coupon(code)
        if coupon is None:
            raise PricingError("That code isn't valid.")
        _check_coupon(coupon, product, now)
        discount = base * coupon.percent // 100 + coupon.flat_off * 100
        discount = min(discount, max(0, base - min_amount))     # never go below the payable minimum
        applied = coupon.code
        label = f"{coupon.percent}% off" if coupon.percent else f"₹{coupon.flat_off} off"
    return Quote(product.slug, product.pricing.list_price * 100, base, discount, base - discount,
                 early, applied, label)
