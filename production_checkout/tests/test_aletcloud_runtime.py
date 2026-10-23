"""AletCloud-sized runtime safety checks using synthetic disposable SQLite."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from production_checkout.app import Base, build_app


def test_health_readiness_closed_order_gate_and_bounded_pool(tmp_path):
    app = build_app(
        database_url="sqlite:///" + str(tmp_path / "alet-runtime.db"),
        token_secret="SYNTHETIC-ONLY-" + "x" * 40,
        allowed_origins=["http://localhost:8765"],
        allow_sqlite_for_tests=True,
        intake_enabled=False,
        payment_accounts={
            "telebirr": {"name": "QA only", "number": "QA-TEL", "holder": "Synthetic"},
            "bank": {"name": "QA only", "number": "QA-CBE", "holder": "Synthetic"},
        },
        db_pool_size=2,
        db_pool_timeout=3,
    )
    Base.metadata.create_all(app.state.engine)
    try:
        assert app.state.engine.pool.size() == 2
        assert app.state.engine.pool._max_overflow == 0
        with TestClient(app) as client:
            health = client.get("/healthz")
            assert health.status_code == 200
            assert health.json()["status"] == "alive"
            assert health.json()["order_intake_enabled"] is False
            assert health.json()["payment_verification_enabled"] is False
            assert client.get("/livez").status_code == 200
            assert client.get("/readyz").json() == {"status": "ready", "database": "ready"}
            assert client.post("/api/v1/orders", json={
                "customer_name": "Synthetic Parent", "mobile": "0912345678",
                "payment_method": "bank",
            }, headers={"Idempotency-Key": "A" * 43}).status_code == 503
    finally:
        Base.metadata.drop_all(app.state.engine)
        app.state.engine.dispose()


@pytest.mark.parametrize("pool_size,pool_timeout", [(0, 5), (5, 5), (2, 0), (2, 31)])
def test_unsafe_pool_configuration_is_rejected(tmp_path, pool_size, pool_timeout):
    with pytest.raises(RuntimeError, match="Database pool settings"):
        build_app(
            database_url="sqlite:///" + str(tmp_path / "unused.db"),
            token_secret="SYNTHETIC-ONLY-" + "x" * 40,
            allowed_origins=["http://localhost:8765"], allow_sqlite_for_tests=True,
            payment_accounts={
                "telebirr": {"name": "QA", "number": "QA-TEL", "holder": "Synthetic"},
                "bank": {"name": "QA", "number": "QA-CBE", "holder": "Synthetic"},
            }, db_pool_size=pool_size, db_pool_timeout=pool_timeout,
        )
