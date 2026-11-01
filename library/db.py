"""SQLite storage (WAL mode). All queries are parameterised - never string-built."""
from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from library.config import load_config, resolve

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    product_slug TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    amount_paise INTEGER NOT NULL,
    list_paise INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    coupon TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'created',
    mode TEXT NOT NULL DEFAULT 'razorpay',
    rz_order_id TEXT UNIQUE,
    rz_payment_id TEXT UNIQUE,
    utm TEXT NOT NULL DEFAULT '{}',
    ip_hash TEXT NOT NULL DEFAULT '',
    downloads INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    paid_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_product_status ON orders(product_slug, status);
CREATE INDEX IF NOT EXISTS idx_orders_email ON orders(email);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    product_slug TEXT NOT NULL,
    utm TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(email, product_slug)
);
"""


@dataclass
class Order:
    id: int
    public_id: str
    product_slug: str
    name: str
    email: str
    phone: str
    amount_paise: int
    list_paise: int
    currency: str
    coupon: str
    status: str
    mode: str
    rz_order_id: Optional[str]
    rz_payment_id: Optional[str]
    utm: Dict[str, str]
    downloads: int
    created_at: str
    paid_at: Optional[str]

    @property
    def paid(self) -> bool:
        return self.status == "paid"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    cfg = load_config()["database"]
    path = resolve(cfg["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=cfg["busy_timeout_ms"] / 1000, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(f"PRAGMA busy_timeout={int(cfg['busy_timeout_ms'])}")
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def _order(row: Optional[sqlite3.Row]) -> Optional[Order]:
    if row is None:
        return None
    d = dict(row)
    d.pop("ip_hash", None)
    d["utm"] = json.loads(d.get("utm") or "{}")
    return Order(**d)


def new_public_id() -> str:
    return "ord_" + secrets.token_urlsafe(12)


# ------------------------------------------------------------------- orders
def create_order(*, product_slug: str, name: str, email: str, phone: str, amount_paise: int,
                 list_paise: int, coupon: str, mode: str, utm: Dict[str, str], ip_hash: str) -> Order:
    public_id = new_public_id()
    with connect() as conn:
        conn.execute(
            """INSERT INTO orders (public_id, product_slug, name, email, phone, amount_paise,
               list_paise, coupon, mode, utm, ip_hash, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (public_id, product_slug, name, email, phone, amount_paise, list_paise, coupon,
             mode, json.dumps(utm), ip_hash, _now()),
        )
        row = conn.execute("SELECT * FROM orders WHERE public_id=?", (public_id,)).fetchone()
    return _order(row)  # type: ignore[return-value]


def attach_rz_order(public_id: str, rz_order_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE orders SET rz_order_id=? WHERE public_id=? AND status='created'",
                     (rz_order_id, public_id))


def get_order(public_id: str) -> Optional[Order]:
    with connect() as conn:
        return _order(conn.execute("SELECT * FROM orders WHERE public_id=?", (public_id,)).fetchone())


def get_order_by_rz(rz_order_id: str) -> Optional[Order]:
    with connect() as conn:
        return _order(conn.execute("SELECT * FROM orders WHERE rz_order_id=?", (rz_order_id,)).fetchone())


def mark_paid(order_id: int, rz_payment_id: str) -> bool:
    """Idempotent. Returns True only for the call that actually flipped the order to paid."""
    with connect() as conn:
        try:
            cur = conn.execute(
                "UPDATE orders SET status='paid', rz_payment_id=?, paid_at=? WHERE id=? AND status!='paid'",
                (rz_payment_id, _now(), order_id),
            )
        except sqlite3.IntegrityError:        # this payment id is already attached to another order
            return False
        return cur.rowcount == 1


def mark_failed(order_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE orders SET status='failed' WHERE id=? AND status='created'", (order_id,))


def count_paid(product_slug: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE product_slug=? AND status='paid' AND mode='razorpay'",
            (product_slug,),
        ).fetchone()
    return int(row["n"])


def count_paid_including_demo(product_slug: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE product_slug=? AND status='paid'", (product_slug,)
        ).fetchone()
    return int(row["n"])


def coupon_uses(code: str) -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM orders WHERE coupon=? AND status='paid'", (code,)).fetchone()
    return int(row["n"])


def has_paid_order(email: str, product_slug: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM orders WHERE email=? AND product_slug=? AND status='paid' LIMIT 1",
            (email, product_slug),
        ).fetchone()
    return row is not None


def bump_download(public_id: str, max_downloads: int) -> bool:
    """Atomically count a download. False when the order is over its limit."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE orders SET downloads=downloads+1 WHERE public_id=? AND status='paid' AND downloads<?",
            (public_id, max_downloads),
        )
        return cur.rowcount == 1


# -------------------------------------------------------------------- leads
def add_lead(email: str, product_slug: str, utm: Dict[str, str]) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO leads (email, product_slug, utm, created_at) VALUES (?,?,?,?)",
            (email, product_slug, json.dumps(utm), _now()),
        )
        return cur.rowcount == 1


# -------------------------------------------------------------------- admin
def recent_orders(limit: int = 100) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT public_id, product_slug, name, email, amount_paise, coupon, status, mode, utm, created_at, paid_at "
            "FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def all_orders() -> List[Dict[str, Any]]:
    return recent_orders(limit=1_000_000)


def all_leads() -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT email, product_slug, utm, created_at FROM leads ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def stats() -> Dict[str, Any]:
    with connect() as conn:
        paid = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(amount_paise),0) AS rev FROM orders WHERE status='paid' AND mode='razorpay'"
        ).fetchone()
        created = conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()
        leads = conn.execute("SELECT COUNT(*) AS n FROM leads").fetchone()
        per_product = conn.execute(
            "SELECT product_slug, COUNT(*) AS n, COALESCE(SUM(amount_paise),0) AS rev FROM orders "
            "WHERE status='paid' AND mode='razorpay' GROUP BY product_slug ORDER BY rev DESC"
        ).fetchall()
        sources: Dict[str, int] = {}
        for r in conn.execute("SELECT utm FROM orders WHERE status='paid' AND mode='razorpay'"):
            src = (json.loads(r["utm"] or "{}").get("utm_source") or "direct")
            sources[src] = sources.get(src, 0) + 1
    return {
        "paid_orders": paid["n"], "revenue_paise": paid["rev"], "all_orders": created["n"],
        "leads": leads["n"], "per_product": [dict(r) for r in per_product],
        "sources": sorted(sources.items(), key=lambda kv: -kv[1]),
    }
