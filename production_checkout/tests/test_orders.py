"""Acceptance tests for the isolated, non-payment ParentWise production order intake.

TEST_DATABASE_URL is exclusively a disposable CI database. Tests intentionally
drop and create only the dedicated production_orders table in that database.
"""
from __future__ import annotations

import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from production_checkout.app import Base, Order, build_app, from_environment

SECRET = "DISPOSABLE-CI-NOT-A-REAL-TOKEN-" + "a" * 40
NAME = "አባት አለሙ"


@pytest.fixture
def intake(tmp_path, monkeypatch):
    url = __import__("os").environ.get("TEST_DATABASE_URL")
    is_pg = bool(url)
    if not url:
        url = "sqlite:///" + str(tmp_path / "production_orders.db")
    app = build_app(
        database_url=url,
        token_secret=SECRET,
        allowed_origins=["http://localhost:3000"] if not is_pg else ["https://parentwise.example"],
        allow_sqlite_for_tests=not is_pg,
        intake_enabled=True,
    )
    Base.metadata.create_all(app.state.engine)
    if is_pg:
        # The separately migrated payment-state tables reference production_orders.
        # Keep the schema and clear only rows in this disposable database.
        with app.state.engine.begin() as conn:
            conn.execute(text("TRUNCATE production_orders CASCADE"))
    with TestClient(app) as client:
        yield (client, app, is_pg, url)
    if is_pg:
        with app.state.engine.begin() as conn:
            conn.execute(text("TRUNCATE production_orders CASCADE"))
    else:
        Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


def post(client, *, key=None, **extra):
    return client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": key or secrets.token_urlsafe(32)},
        json={"customer_name": NAME, "mobile": "0912345678", "payment_method": "telebirr", **extra},
    )


def test_create_persists_server_price_and_payment_instructions(intake):
    client, app, pg, url = intake
    r = post(client)
    assert r.status_code == 201, r.text
    response = r.json()
    order, access = response["order"], response["access_token"]
    assert order["amount_etb"] == 1500
    assert order["currency"] == "ETB"
    assert order["status"] == "AWAITING_PAYMENT"
    assert order["payment_instructions"] == {
        "name": "Telebirr", "number": "NOT-CONFIGURED", "holder": "NOT-CONFIGURED",
        "amount_etb": 1500, "currency": "ETB",
    }
    assert order["order_id"].startswith("PW-") and not order["order_id"].startswith("PW-QA-")
    assert "mobile" not in r.text and NAME not in r.text
    assert len(access) == 43
    assert "no-store" in r.headers["cache-control"]
    with app.state.sessions() as db:
        row = db.scalar(select(Order).where(Order.code == order["order_id"]))
        assert row.mobile_e164 == "+251912345678"
        assert row.customer_name == NAME
        assert access != row.access_hash



def test_recipient_configuration_is_injected_per_method_without_enabling_verification(tmp_path):
    """Synthetic account configuration maps to the correct method; it never approves payment."""
    from production_checkout.app import PRICE_ETB

    sample_accounts = {
        "telebirr": {"name": "Telebirr", "number": "QA-MOBILE-NUMBER", "holder": "QA-HOLDER"},
        "bank": {"name": "Commercial Bank of Ethiopia", "number": "QA-BANK-ACCOUNT", "holder": "QA-HOLDER"},
    }
    app = build_app(
        database_url="sqlite:///" + str(tmp_path / "recipient_mapping.db"),
        token_secret=SECRET,
        allowed_origins=["http://localhost:3000"],
        allow_sqlite_for_tests=True,
        intake_enabled=True,
        payment_accounts=sample_accounts,
    )
    Base.metadata.create_all(app.state.engine)
    try:
        with TestClient(app) as client:
            for method in ("telebirr", "bank"):
                response = post(client, payment_method=method)
                assert response.status_code == 201, response.text
                details = response.json()["order"]["payment_instructions"]
                assert details == {**sample_accounts[method], "amount_etb": PRICE_ETB, "currency": "ETB"}
                assert details["number"] != sample_accounts["bank" if method == "telebirr" else "telebirr"]["number"]
            assert client.get("/healthz").json()["payment_verification_enabled"] is False
            assert client.post("/api/v1/payments/verify").status_code == 404
    finally:
        Base.metadata.drop_all(app.state.engine)
        app.state.engine.dispose()

def test_bank_and_normalization(intake):
    client, app, *_ = intake
    r = post(client, payment_method="bank", mobile="+251712345678")
    assert r.status_code == 201, r.text
    assert r.json()["order"]["payment_instructions"]["number"] == "NOT-CONFIGURED"
    with app.state.sessions() as db:
        assert db.scalar(select(Order).where(Order.code == r.json()["order"]["order_id"])).mobile_e164 == "+251712345678"


def test_idempotent_retry_and_conflicting_key(intake):
    client, app, *_ = intake
    key = secrets.token_urlsafe(32)
    first = post(client, key=key)
    retry = post(client, key=key, mobile="+251912345678")
    # Phone normalization means semantically identical request.
    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    assert post(client, key=key, payment_method="bank").status_code == 409
    with app.state.sessions() as db:
        assert len(db.scalars(select(Order)).all()) == 1


@pytest.mark.parametrize("bad", [
    {"amount_etb": 1},
    {"currency": "USD"},
    {"status": "VERIFIED_PAID"},
    {"payment_instructions": {"number": "000"}},
    {"payment_method": "cash"},
    {"customer_name": " "},
    {"customer_name": "00000"},
    {"mobile": "0812345678"},
    {"mobile": "+251812345678"},
    {"mobile": "09123"},
])
def test_malformed_or_manipulated_requests_rejected(intake, bad):
    client, *_ = intake
    r = post(client, **bad)
    assert r.status_code == 422, (bad, r.status_code, r.text[:200])


def test_key_validation(intake):
    client, *_ = intake
    assert client.post("/api/v1/orders", headers={"Idempotency-Key": "bad"}, json={
        "customer_name": NAME, "mobile": "0912345678", "payment_method": "telebirr"
    }).status_code == 400


def test_customer_token_is_required_and_not_shared(intake):
    client, app, *_ = intake
    a = post(client).json()
    b = post(client).json()
    code = a["order"]["order_id"]
    assert client.get("/api/v1/orders/" + code).status_code == 404
    assert client.get("/api/v1/orders/" + code, headers={"Authorization": "Bearer " + b["access_token"]}).status_code == 404
    assert client.get("/api/v1/orders/PW-INVALID", headers={"Authorization": "Bearer " + a["access_token"]}).status_code == 404
    r = client.get("/api/v1/orders/" + code, headers={"Authorization": "Bearer " + a["access_token"]})
    assert r.status_code == 200
    assert r.json()["order"] == a["order"]
    assert NAME not in r.text


def test_database_blocks_fake_verified_payments(intake):
    client, app, *_ = intake
    oid = post(client).json()["order"]["order_id"]
    with app.state.engine.begin() as conn:
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            conn.execute(text("UPDATE production_orders SET status='VERIFIED_PAID' WHERE code=:code"), {"code": oid})
    assert client.post("/api/v1/payments/verify").status_code == 404
    assert client.post("/api/v1/orders/" + oid + "/proof").status_code == 404


def test_readiness_and_cors(intake):
    client, app, pg, *_ = intake
    assert client.get("/healthz").json()["payment_verification_enabled"] is False
    assert client.get("/readyz").status_code == 200
    preflight = client.options(
        "/api/v1/orders",
        headers={
            "Origin": "https://parentwise.example" if pg else "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "idempotency-key,content-type",
        },
    )
    assert preflight.status_code == 200
    assert client.options("/api/v1/orders", headers={
        "Origin": "https://malicious.example", "Access-Control-Request-Method": "POST"
    }).status_code == 400


def test_fail_closed_environment_and_no_open_intake(intake, monkeypatch):
    client, app, pg, url = intake
    safe = build_app(
        database_url=url,
        token_secret=SECRET,
        allowed_origins=["https://parentwise.example"],
        allow_sqlite_for_tests=not pg,
    )
    with TestClient(safe) as closed:
        assert closed.post("/api/v1/orders", json={
            "customer_name": NAME, "mobile": "0912345678", "payment_method": "bank"
        }, headers={"Idempotency-Key": secrets.token_urlsafe(32)}).status_code == 503
    safe.state.engine.dispose()
    monkeypatch.setenv("APP_MODE", "qa")
    with pytest.raises(RuntimeError):
        from_environment()
    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    with pytest.raises(RuntimeError, match="Payment verification"):
        from_environment()


def test_persistence_with_new_app_instance(intake):
    client, app, pg, url = intake
    record = post(client).json()
    another = build_app(database_url=url, token_secret=SECRET,
                        allowed_origins=["https://parentwise.example"],
                        allow_sqlite_for_tests=not pg, intake_enabled=False)
    with TestClient(another) as reopened:
        r = reopened.get("/api/v1/orders/" + record["order"]["order_id"],
                         headers={"Authorization": "Bearer " + record["access_token"]})
        assert r.status_code == 200
        assert r.json()["order"] == record["order"]
    another.state.engine.dispose()


def test_concurrent_key_same_order_postgres(intake):
    client, app, pg, *_ = intake
    if not pg:
        pytest.skip("PostgreSQL transaction-scoped advisory lock only")
    key = secrets.token_urlsafe(32)
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: post(client, key=key), range(5)))
    assert [r.status_code for r in results] == [201] * 5, [(r.status_code, r.text[:160]) for r in results]
    assert len({r.json()["order"]["order_id"] for r in results}) == 1
