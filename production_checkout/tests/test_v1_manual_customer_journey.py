"""V1 manual Telegram checkout: isolated synthetic order-persistence release gate.

These tests do not activate production, send Telegram messages or process payments.
"""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient
from production_checkout.app import Base, build_app


QA_ACCOUNTS = {
    "telebirr": {"name": "Telebirr", "number": "QA-TELEBIRR-ONLY", "holder": "QA-ONLY"},
    "bank": {"name": "CBE Bank", "number": "QA-CBE-ONLY", "holder": "QA-ONLY"},
}


def _build(tmp_path, *, intake_enabled: bool):
    app = build_app(
        database_url="sqlite:///" + str(tmp_path / ("v1-active.db" if intake_enabled else "v1-closed.db")),
        token_secret="QA-ONLY-INTEGRATION-KEY-" + ("a" * 40),
        allowed_origins=["http://localhost:8765"],
        allow_sqlite_for_tests=True,
        intake_enabled=intake_enabled,
        payment_accounts=QA_ACCOUNTS,
    )
    Base.metadata.create_all(app.state.engine)
    return app


def test_manual_v1_pending_order_created_once_and_not_verified(tmp_path):
    app = _build(tmp_path, intake_enabled=True)
    try:
        with TestClient(app) as client:
            customer = {"customer_name": "QA Parent", "mobile": "0912345678", "payment_method": "bank"}
            key = secrets.token_urlsafe(32)
            first = client.post("/api/v1/orders", json=customer, headers={"Idempotency-Key": key})
            assert first.status_code == 201, first.text
            body = first.json()
            order = body["order"]
            assert order["amount_etb"] == 1500
            assert order["currency"] == "ETB"
            assert order["status"] == "AWAITING_PAYMENT"
            assert order["payment_method"] == "bank"
            assert order["payment_instructions"]["number"] == "QA-CBE-ONLY"
            assert order["payment_instructions"]["holder"] == "QA-ONLY"
            assert "QA Parent" not in first.text
            assert "0912345678" not in first.text
            assert "no-store" in first.headers["cache-control"]

            # The same form retry must not create another payable order.
            second = client.post("/api/v1/orders", json=customer, headers={"Idempotency-Key": key})
            assert second.status_code == 201
            assert second.json() == body

            # The private token is kept internal; the buyer need not manage an order code.
            ref = order["order_id"]
            assert client.get(f"/api/v1/orders/{ref}").status_code == 404
            saved = client.get(f"/api/v1/orders/{ref}", headers={"Authorization": "Bearer " + body["access_token"]})
            assert saved.status_code == 200
            assert saved.json()["order"]["status"] == "AWAITING_PAYMENT"
            assert saved.json()["order"]["payment_instructions"]["number"] == "QA-CBE-ONLY"
            assert saved.json()["order"]["payment_instructions"]["holder"] == "QA-ONLY"
            assert client.post("/api/v1/payments/verify").status_code == 404
            assert client.post(f"/api/v1/orders/{ref}/payment-claims").status_code == 404
    finally:
        Base.metadata.drop_all(app.state.engine)
        app.state.engine.dispose()


def test_v1_order_intake_stays_closed_without_explicit_test_enable(tmp_path):
    app = _build(tmp_path, intake_enabled=False)
    try:
        with TestClient(app) as client:
            status = client.get("/healthz")
            assert status.status_code == 200
            assert status.json()["order_intake_enabled"] is False
            assert status.json()["payment_verification_enabled"] is False
            request = client.post(
                "/api/v1/orders",
                json={"customer_name": "QA Parent", "mobile": "0912345678", "payment_method": "telebirr"},
                headers={"Idempotency-Key": secrets.token_urlsafe(32)},
            )
            assert request.status_code == 503
    finally:
        Base.metadata.drop_all(app.state.engine)
        app.state.engine.dispose()
