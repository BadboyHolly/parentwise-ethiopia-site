"""Isolated full staging journey on a disposable PostgreSQL database."""
import os, secrets, time
from argon2 import PasswordHasher
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from staging_checkout.app import build_staging_app
from staging_checkout.security import totp_code

ORIGIN = "https://staging.example.invalid"
PASSWORD = os.environ["STAGING_FOUNDER_PASSWORD"]
TOTP_SECRET = os.environ["STAGING_FOUNDER_TOTP_SECRET"]

@pytest.fixture
def env():
    app = build_staging_app(
        database_url=os.environ["STAGING_DATABASE_URL"],
        order_token_secret=os.environ["STAGING_ORDER_TOKEN_KEY"],
        founder_username=os.environ["STAGING_FOUNDER_USERNAME"],
        founder_password_hash=os.environ["STAGING_FOUNDER_PASSWORD_HASH"],
        founder_totp_secret=TOTP_SECRET,
        allowed_origins=[ORIGIN],
        order_intake_enabled=True,
        customer_rate_limit=int(os.getenv("TEST_CUSTOMER_RATE_LIMIT", "30")),
    )
    with app.state.engine.begin() as conn:
        conn.execute(text("""TRUNCATE staging_audit_events, staging_download_grants,
            staging_simulated_settlements, staging_payment_claims, staging_order_states,
            staging_founder_sessions, staging_rate_windows, production_orders CASCADE"""))
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, app
    app.state.engine.dispose()

def order(client, method="telebirr"):
    result = client.post("/api/v1/orders",
        headers={"Idempotency-Key":secrets.token_urlsafe(32),"Origin":ORIGIN},
        json={"customer_name":"QA Parent Example","mobile":"0900000000","payment_method":method})
    assert result.status_code == 201, result.text
    item = result.json()
    assert item["order"]["payment_instructions"]["number"] in {"QA-TELEBIRR-ONLY","QA-CBE-ONLY"}
    assert item["order"]["payment_instructions"]["number"] not in {"0912910693","10002230019327"}
    return item["order"]["order_id"], item["access_token"], item["order"]

def customer(token):
    return {"Authorization":"Bearer "+token,"Origin":ORIGIN}

def claim(client, code, token, reference, amount=1500):
    return client.post(f"/api/v1/orders/{code}/payment-claims",headers=customer(token),
        json={"test_reference":reference,"reported_amount_etb":amount,"currency":"ETB"})

def founder(client):
    login=client.post("/founder/session",headers={"Origin":ORIGIN},
        json={"username":os.environ["STAGING_FOUNDER_USERNAME"],"password":PASSWORD,
              "totp":totp_code(TOTP_SECRET)})
    assert login.status_code == 200, login.text
    csrf=login.json()["csrf_token"]
    return {"Origin":ORIGIN,"X-CSRF-Token":csrf}

def settlement(client, headers, reference, method="telebirr", amount=1500,
               payer="+251900000000", recipient="QA-TELEBIRR-ONLY"):
    return client.post("/founder/api/simulated-settlements",headers=headers,
        json={"test_reference":reference,"payment_method":method,"amount_etb":amount,
              "currency":"ETB","recipient_code":recipient,"payer_mobile":payer})

def test_complete_order_claim_independent_review_private_download_recovery_and_revocation(env):
    client,_=env
    code,token,created=order(client)
    assert created["status"] == "AWAITING_PAYMENT"
    assert created["payment_instructions"]["number"] == "QA-TELEBIRR-ONLY"
    status=client.get(f"/api/v1/orders/{code}/checkout-status",headers=customer(token))
    assert status.status_code == 200 and status.json()["status"] == "Awaiting Payment"
    ref="SIM-"+secrets.token_hex(8).upper()
    submitted=claim(client,code,token,ref)
    assert submitted.status_code == 201 and submitted.json()["claim_is_payment_confirmation"] is False
    assert client.get(f"/api/v1/orders/{code}/downloads/part-1",headers=customer(token)).status_code == 403
    status=client.get(f"/api/v1/orders/{code}/checkout-status",headers=customer(token)).json()
    assert status["status"] == "Under Review" and status["downloads_ready"] is False

    admin=founder(client)
    assert settlement(client,admin,ref).status_code == 201
    checked=client.post(f"/founder/api/orders/{code}/verify",headers=admin)
    assert checked.status_code == 200 and checked.json()["matched"] is True
    assert client.get(f"/api/v1/orders/{code}/downloads/part-1",headers=customer(token)).status_code == 403
    approved=client.post(f"/founder/api/orders/{code}/approve",headers=admin,json={"reason":"QA independent match"})
    assert approved.status_code == 200 and approved.json()["downloads_ready"] is True
    recovered=client.get(f"/api/v1/orders/{code}",headers=customer(token))
    assert recovered.status_code == 200 and recovered.json()["order"]["status"] == "AWAITING_PAYMENT"
    assert client.get(f"/api/v1/orders/{code}/checkout-status",headers=customer(token)).json()["status"] == "Ready to Download"
    for part in range(1,6):
        response=client.get(f"/api/v1/orders/{code}/downloads/part-{part}",headers=customer(token))
        assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-1.4") and b"QA DEMO ONLY" in response.content
        assert b"NOT A PAID PARENTWISE PRODUCT" in response.content
        assert "no-store" in response.headers["cache-control"]
    assert client.get(f"/api/v1/orders/{code}/downloads/part-6",headers=customer(token)).status_code == 404
    assert client.get(f"/api/v1/orders/{code}/checkout-status",
        headers={"Authorization":"Bearer "+"Z"*43,"Origin":ORIGIN}).status_code == 404
    assert client.get(f"/api/v1/orders/{code}/downloads/part-1",
        headers={"Authorization":"Bearer "+"Z"*43,"Origin":ORIGIN}).status_code == 404

    revoked=client.post(f"/founder/api/orders/{code}/downloads/revoke",headers=admin,json={"reason":"QA revocation"})
    assert revoked.status_code == 200 and revoked.json()["revoked"] is True
    for part in range(1,6):
        assert client.get(f"/api/v1/orders/{code}/downloads/part-{part}",headers=customer(token)).status_code == 403
    final=client.get(f"/api/v1/orders/{code}/checkout-status",headers=customer(token)).json()
    assert final["downloads_ready"] is False and final["status"] == "Payment Confirmed"

@pytest.mark.parametrize("mismatch",["unknown_reference","wrong_amount","wrong_method","wrong_identity"])
def test_mismatch_rejection_and_customer_retry(mismatch,env):
    client,_=env
    code,token,saved=order(client)
    admin=founder(client)
    first="SIM-"+secrets.token_hex(8).upper()
    assert claim(client,code,token,first).status_code == 201
    settlement_ref="SIM-"+secrets.token_hex(8).upper() if mismatch=="unknown_reference" else first
    method="bank" if mismatch=="wrong_method" else saved["payment_method"]
    amount=1400 if mismatch=="wrong_amount" else 1500
    payer="+251911111111" if mismatch=="wrong_identity" else "+251900000000"
    recipient="QA-CBE-ONLY" if method=="bank" else "QA-TELEBIRR-ONLY"
    assert settlement(client,admin,settlement_ref,method,amount,payer,recipient).status_code == 201
    matched=client.post(f"/founder/api/orders/{code}/verify",headers=admin)
    assert matched.status_code == 200 and matched.json()["matched"] is False
    assert client.post(f"/founder/api/orders/{code}/approve",headers=admin,json={"reason":"must not approve"}).status_code == 409
    rejected=client.post(f"/founder/api/orders/{code}/reject",headers=admin,json={"reason":"Synthetic mismatch"})
    assert rejected.status_code == 200 and rejected.json()["retry_allowed"] is True
    retry="SIM-"+secrets.token_hex(8).upper()
    assert claim(client,code,token,retry).status_code == 201
    right_recipient="QA-TELEBIRR-ONLY" if saved["payment_method"]=="telebirr" else "QA-CBE-ONLY"
    assert settlement(client,admin,retry,saved["payment_method"],1500,"+251900000000",right_recipient).status_code == 201
    assert client.post(f"/founder/api/orders/{code}/verify",headers=admin).json()["matched"] is True
    assert client.post(f"/founder/api/orders/{code}/approve",headers=admin,json={"reason":"Corrected fictional claim"}).status_code == 200
    assert client.get(f"/api/v1/orders/{code}/downloads/part-1",headers=customer(token)).status_code == 200

def test_duplicate_claims_are_global_and_open_claims_cannot_be_replaced(env):
    client,_=env
    first,token1,_=order(client)
    second,token2,_=order(client,"bank")
    ref="SIM-"+secrets.token_hex(8).upper()
    assert claim(client,first,token1,ref).status_code == 201
    assert claim(client,first,token1,ref).status_code == 409
    assert claim(client,second,token2,ref).status_code == 409
    assert claim(client,first,token1,"SIM-"+secrets.token_hex(8).upper()).status_code == 409
    admin=founder(client)
    assert settlement(client,admin,ref).status_code == 201
    assert settlement(client,admin,ref).status_code == 409

def test_founder_auth_csrf_and_customer_tokens_are_required(env):
    client,_=env
    code,token,_=order(client)
    assert client.post(f"/founder/api/orders/{code}/verify",json={}).status_code == 401
    bad=client.post("/founder/session",headers={"Origin":ORIGIN},
        json={"username":os.environ["STAGING_FOUNDER_USERNAME"],"password":PASSWORD,"totp":"000000"})
    assert bad.status_code == 401
    admin=founder(client)
    no_csrf={"Origin":ORIGIN}
    assert client.post(f"/founder/api/orders/{code}/approve",headers=no_csrf,json={"reason":"No CSRF"}).status_code == 403
    assert client.get(f"/api/v1/orders/{code}/checkout-status").status_code == 404
    assert client.get(f"/api/v1/orders/{code}/checkout-status",
        headers={"Authorization":"Bearer "+"X"*43,"Origin":ORIGIN}).status_code == 404
    assert client.get(f"/api/v1/orders/{code}/downloads/part-1",headers=customer(token)).status_code == 403

def test_customer_order_creation_rate_limit(env,monkeypatch):
    client,_=env
    # App uses the configured limit: override for this isolated case before any request.
    client.app.state.customer_rate_limit=2
    assert order(client)[0]
    assert order(client)[0]
    third=client.post("/api/v1/orders",headers={"Idempotency-Key":secrets.token_urlsafe(32),"Origin":ORIGIN},
        json={"customer_name":"QA Parent Example","mobile":"0900000000","payment_method":"telebirr"})
    assert third.status_code == 429 and third.headers["retry-after"] == "600"

def test_customer_recovery_and_claim_endpoints_are_rate_limited(env):
    client,_=env
    client.app.state.customer_rate_limit=2
    code,token,_=order(client)
    path=f"/api/v1/orders/{code}"
    assert client.get(path+"/checkout-status",headers=customer(token)).status_code == 200
    assert client.get(path+"/checkout-status",headers=customer(token)).status_code == 200
    assert client.get(path+"/checkout-status",headers=customer(token)).status_code == 429
    ref="SIM-"+secrets.token_hex(8).upper()
    assert claim(client,code,token,ref).status_code == 201
    assert claim(client,code,token,ref).status_code == 409
    assert claim(client,code,token,ref).status_code == 429

def test_customer_download_endpoint_is_rate_limited(env):
    client,_=env
    client.app.state.customer_rate_limit=2
    code,token,saved=order(client)
    admin=founder(client)
    ref="SIM-"+secrets.token_hex(8).upper()
    assert claim(client,code,token,ref).status_code == 201
    recipient="QA-TELEBIRR-ONLY" if saved["payment_method"]=="telebirr" else "QA-CBE-ONLY"
    assert settlement(client,admin,ref,saved["payment_method"],1500,"+251900000000",recipient).status_code == 201
    assert client.post(f"/founder/api/orders/{code}/verify",headers=admin).json()["matched"] is True
    assert client.post(f"/founder/api/orders/{code}/approve",headers=admin,json={"reason":"QA test"}).status_code == 200
    url=f"/api/v1/orders/{code}/downloads/part-1"
    assert client.get(url,headers=customer(token)).status_code == 200
    assert client.get(url,headers=customer(token)).status_code == 200
    assert client.get(url,headers=customer(token)).status_code == 429
