"""SEO helpers: JSON-LD, sitemap.xml, robots.txt."""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Dict, List

from library.catalog import Product
from library.config import base_url, load_config
from library.pricing import base_price_paise


def product_jsonld(product: Product, site_name: str) -> Dict[str, Any]:
    price_paise, _ = base_price_paise(product)
    availability = ("https://schema.org/InStock" if product.purchasable
                    else "https://schema.org/PreOrder")
    ld: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Course" if product.type == "course" else "Product",
        "name": product.name,
        "description": product.seo["description"],
        "url": f"{base_url()}/p/{product.slug}",
        "provider" if product.type == "course" else "brand": {"@type": "Organization", "name": site_name},
        "offers": {
            "@type": "Offer",
            "price": f"{price_paise / 100:.2f}",
            "priceCurrency": "INR",
            "availability": availability,
            "url": f"{base_url()}/p/{product.slug}",
        },
    }
    if product.faq:
        ld = {"@context": "https://schema.org", "@graph": [
            {k: v for k, v in ld.items() if k != "@context"},
            {"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in product.faq]},
        ]}
    return ld


def sitemap_xml(products: List[Product]) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    urls = [f"{base_url()}/"] + [f"{base_url()}/p/{p.slug}" for p in products]
    urls += [f"{base_url()}/legal/{page}" for page in ("terms", "privacy", "refund", "contact")]
    rows = "".join(f"<url><loc>{html.escape(u)}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'


def robots_txt() -> str:
    return (
        "User-agent: *\n"
        "Disallow: /admin\nDisallow: /api/\nDisallow: /thanks/\nDisallow: /download/\n"
        f"Sitemap: {base_url()}/sitemap.xml\n"
    )
