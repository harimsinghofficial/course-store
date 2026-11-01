"""Product delivery: safe file lookup and signed, expiring download links."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from library import security
from library.catalog import DeliveryFile, Product
from library.config import load_config, resolve


def _slug_dir(slug: str) -> Path:
    return (resolve(load_config()["delivery"]["deliverables_dir"]) / slug).resolve()


def find_file(product: Product, file_id: str) -> Optional[tuple[DeliveryFile, Path]]:
    """Return the file only when it is declared in the product JSON AND lives inside deliverables/<slug>/."""
    for f in product.delivery.files:
        if f.id != file_id:
            continue
        root = _slug_dir(product.slug)
        candidate = (root / f.filename).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            return f, candidate
    return None


def missing_files(product: Product) -> List[str]:
    return [f.filename for f in product.delivery.files if find_file(product, f.id) is None]


def download_links(public_id: str, product: Product) -> List[Dict[str, str]]:
    if product.delivery.type == "link":
        return []
    return [{"label": f.label or f.filename, "url": f"/download/{security.download_token(public_id, f.id)}"}
            for f in product.delivery.files]
