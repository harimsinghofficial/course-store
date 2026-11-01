import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"
os.environ["APP_ENV"] = "development"
for k in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET", "ADMIN_PASSWORD_HASH",
          "ADMIN_PASSWORD", "GA4_ID", "META_PIXEL_ID", "SMTP_HOST"):
    os.environ[k] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from library import security  # noqa: E402
from library.config import load_config  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    cfg = load_config()
    monkeypatch.setitem(cfg["database"], "path", str(tmp_path / "test.db"))
    monkeypatch.setitem(cfg["logs"], "timing_file", str(tmp_path / "timing.jsonl"))
    monkeypatch.setitem(cfg["logs"], "error_file", str(tmp_path / "errors.jsonl"))
    security.limiter.reset()
    security.build_csp.cache_clear()
    import main
    with TestClient(main.app) as c:
        yield c
    security.limiter.reset()
    security.build_csp.cache_clear()


@pytest.fixture()
def rz(monkeypatch):
    """Switch the app to Razorpay mode with fake keys and a stubbed gateway (no network)."""
    from library import payments
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_abc123")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "key_secret_for_tests")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "webhook_secret_for_tests")
    security.build_csp.cache_clear()
    counter = {"n": 0}

    def fake_create(amount_paise, receipt, notes):
        counter["n"] += 1
        return {"id": f"order_TEST{counter['n']:04d}", "amount": amount_paise, "currency": "INR"}

    monkeypatch.setattr(payments, "create_razorpay_order", fake_create)
    return counter
