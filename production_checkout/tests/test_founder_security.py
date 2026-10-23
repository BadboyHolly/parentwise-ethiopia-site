"""Disposable-PostgreSQL tests for founder session and payment route controls."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
import secrets
from datetime import datetime, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import text

from production_checkout.app import build_app, hmac_digest, private_token
from production_checkout.founder_security import (
    FounderConfig, InvalidCiphertext, create_founder_router, decrypt_sensitive,
    encrypt_sensitive, _totp_counter,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="requires disposable PostgreSQL")
PASSWORD = "test-only disposable founder password"
TOTP_SECRET = base64.b32encode(b"0123456789abcdef0123").decode().rstrip("=")
KEY = b"t" * 32


def totp(secret: str, now: int | None = None) -> str:
    seed = base64.b32decode(secret + "=" * ((8-len(secret)%8)%8))
    step = int((time.time() if now is None else now)//30)
    digest = hmac.new(seed, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return f"{(struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1000000:06d}"


@pytest.fixture(scope="module")
def password_hash():
    return PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2).hash(PASSWORD)


@pytest.fixture
def founder_app(password_hash, request):
    app = build_app(database_url=DATABASE_URL, token_secret="t"*48,
                    allowed_origins=["https://founder.example"], intake_enabled=True)
    cfg = FounderConfig(
        username="founder-primary", password_hash=password_hash, totp_secret=TOTP_SECRET,
        session_key=b"s"*32, rate_key=b"r"*32, encryption_keys={"test-k1":KEY},
        active_encryption_key_id="test-k1", token_secret="t"*48,
        reference_hash_secret="h"*48, identity_hash_secret="i"*48,
        recipient_hash_secret="p"*48, telebirr_recipient="TEST-TEL-RECIPIENT",
        bank_recipient="TEST-BANK-RECIPIENT", allowed_origins=("https://founder.example",),
        auth_enabled=True, approvals_enabled=bool(getattr(request, "param", False)), secure_cookie=True,
    )
    app.state.founder_config = cfg
    app.include_router(create_founder_router(app.state.sessions, cfg))
    with app.state.engine.begin() as db:
        db.execute(text("TRUNCATE production_orders CASCADE"))
        db.execute(text("TRUNCATE production_founder_sessions, production_founder_rate_limits, production_founder_security_events"))
        db.execute(text("UPDATE production_founder_auth_control SET last_totp_step=-1 WHERE singleton_id=1"))
    yield app
    with app.state.engine.begin() as db:
        db.execute(text("TRUNCATE production_orders CASCADE"))
        db.execute(text("TRUNCATE production_founder_sessions, production_founder_rate_limits, production_founder_security_events"))
        db.execute(text("UPDATE production_founder_auth_control SET last_totp_step=-1 WHERE singleton_id=1"))
    app.state.engine.dispose()


def login(client):
    return client.post("/api/v1/founder/session", headers={"Origin":"https://founder.example"},
        json={"username":"founder-primary","password":PASSWORD,"totp":totp(TOTP_SECRET)})


def test_argon2id_totp_login_creates_hashed_httponly_secure_session(founder_app):
    with TestClient(founder_app, base_url="https://founder.example") as client:
        response=login(client)
        assert response.status_code == 200, response.text
        cookie=response.cookies.get("pw_founder_session")
        assert cookie and len(cookie)>30
        set_cookie=response.headers["set-cookie"].lower()
        assert "httponly" in set_cookie and "secure" in set_cookie and "samesite=strict" in set_cookie
        assert response.headers["cache-control"] == "no-store"
        assert "csrf_token" in response.json()
        with founder_app.state.sessions() as db:
            stored=db.execute(text("SELECT session_hash,founder_id FROM production_founder_sessions")).one()
            assert stored[0] != cookie and stored[1] == "founder-primary"


def test_invalid_password_totp_and_replay_are_rejected(founder_app):
    with TestClient(founder_app, base_url="https://founder.example") as client:
        r=client.post("/api/v1/founder/session",headers={"Origin":"https://founder.example"},
            json={"username":"founder-primary","password":"wrong password value","totp":totp(TOTP_SECRET)})
        assert r.status_code == 401
        first=login(client); assert first.status_code == 200
        replay=client.post("/api/v1/founder/session",headers={"Origin":"https://founder.example"},
            json={"username":"founder-primary","password":PASSWORD,"totp":totp(TOTP_SECRET)})
        assert replay.status_code == 401
        with founder_app.state.sessions() as db:
            assert db.scalar(text("SELECT count(*) FROM production_founder_security_events WHERE event_type='MFA_REPLAY_BLOCKED'")) == 1


def test_origin_and_login_rate_limit(founder_app):
    with TestClient(founder_app, base_url="https://founder.example") as client:
        denied=client.post("/api/v1/founder/session",json={"username":"founder-primary","password":PASSWORD,"totp":totp(TOTP_SECRET)})
        assert denied.status_code == 403
        statuses=[]
        for _ in range(7):
            statuses.append(client.post("/api/v1/founder/session",headers={"Origin":"https://founder.example"},
                json={"username":"founder-primary","password":"incorrect long password","totp":"000000"}).status_code)
        assert statuses[:5] == [401]*5 and statuses[-1] == 429


def test_expired_session_missing_csrf_and_logout_revoke(founder_app):
    with TestClient(founder_app, base_url="https://founder.example") as client:
        response=login(client); assert response.status_code==200
        csrf=response.json()["csrf_token"]
        assert client.delete("/api/v1/founder/session",headers={"Origin":"https://founder.example"}).status_code==403
        assert client.delete("/api/v1/founder/session",headers={"Origin":"https://founder.example","X-CSRF-Token":"wrong"}).status_code==403
        ok=client.delete("/api/v1/founder/session",headers={"Origin":"https://founder.example","X-CSRF-Token":csrf})
        assert ok.status_code==204
        assert client.get("/api/v1/founder/session").status_code==401
        again=login(client); assert again.status_code==401  # same TOTP step cannot be replayed


def test_expired_session_denies_requests(founder_app):
    with TestClient(founder_app, base_url="https://founder.example") as client:
        assert login(client).status_code==200
        with founder_app.state.engine.begin() as db:
            db.execute(text("UPDATE production_founder_sessions SET created_at=now()-interval '9 hours', expires_at=now()-interval '1 minute'"))
        assert client.get("/api/v1/founder/session").status_code==401


def test_approval_gate_and_forged_founder_identity_are_denied(founder_app):
    with TestClient(founder_app, base_url="https://founder.example") as client:
        response=login(client); assert response.status_code==200
        csrf=response.json()["csrf_token"]
        headers={"Origin":"https://founder.example","X-CSRF-Token":csrf}
        forged=client.post("/api/v1/founder/reject",headers=headers,json={
            "order_id":"PW-"+"A"*24,"claim_id":"x","reason":"No evidence supplied","founder_id":"root"})
        assert forged.status_code==422
        blocked=client.post("/api/v1/founder/reject",headers=headers,json={
            "order_id":"PW-"+"A"*24,"claim_id":"x","reason":"No evidence supplied"})
        assert blocked.status_code==503
        claim_blocked=client.post("/api/v1/founder/claims/telegram",headers=headers,json={
            "order_id":"PW-"+"A"*24,"payment_method":"telebirr",
            "transaction_reference":"SIM-GATE-CLOSED"})
        assert claim_blocked.status_code==503


def test_founder_metrics_and_manual_delivery_routes_are_authenticated_and_gated(founder_app):
    with TestClient(founder_app, base_url="https://founder.example") as client:
        assert client.get("/api/v1/founder/metrics").status_code == 401
        assert client.get("/api/v1/founder/deliveries/pending").status_code == 401
        response = login(client); assert response.status_code == 200
        assert client.get("/api/v1/founder/metrics").status_code == 200
        assert client.get("/api/v1/founder/deliveries/pending").json() == {"deliveries": []}
        blocked = client.post("/api/v1/founder/deliveries/status",
            headers={"Origin":"https://founder.example","X-CSRF-Token":response.json()["csrf_token"]},
            json={"order_id":"PW-"+"A"*24,"status":"SENT"})
        assert blocked.status_code == 503


@pytest.mark.parametrize("founder_app", [True], indirect=True)
def test_founder_mfa_approval_and_telegram_delivery_journey(founder_app):
    cfg = founder_app.state.founder_config
    reference = "SIM-FOUNDER-" + secrets.token_hex(6).upper()
    with TestClient(founder_app, base_url="https://founder.example") as client:
        order_created=client.post("/api/v1/orders",
            headers={"Idempotency-Key":base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")},
            json={"customer_name":"Synthetic Founder Test","mobile":"+251912345678",
                  "payment_method":"telebirr"})
        assert order_created.status_code == 201, order_created.text
        code=order_created.json()["order"]["order_id"]
        assert client.get("/api/v1/founder/orders/search",
                          params={"q":code}).status_code == 401
        logged = login(client); assert logged.status_code == 200
        csrf = logged.json()["csrf_token"]
        headers={"Origin":"https://founder.example","X-CSRF-Token":csrf}
        lookup=client.get("/api/v1/founder/orders/search",params={"q":code})
        assert lookup.status_code == 200, lookup.text
        assert lookup.json()["order"]["payment_status"] == "AWAITING_PAYMENT"
        claim_response=client.post("/api/v1/founder/claims/telegram",headers=headers,json={
            "order_id":code,"payment_method":"telebirr","transaction_reference":reference,
        })
        assert claim_response.status_code == 201, claim_response.text
        assert claim_response.json()["status"] == "UNDER_REVIEW_NOT_PAYMENT_CONFIRMATION"
        claim_id=claim_response.json()["claim_id"]
        assert client.get("/api/v1/founder/metrics").json()["verified_revenue_etb"] == 0
        with founder_app.state.engine.connect() as db:
            stored=db.execute(text("""
                SELECT c.reference_ciphertext,s.payment_status
                  FROM production_payment_claims c
                  JOIN production_payment_fulfillment_state s ON s.order_id=c.order_id
                 WHERE c.id=:claim
            """),{"claim":claim_id}).one()
            audit=db.execute(text("""
                SELECT actor_type,actor_id,event_data->>'channel'
                  FROM production_payment_audit_events
                 WHERE event_type='PAYMENT_CLAIM_RECORDED_TELEGRAM'
            """)).one()
        assert reference not in stored.reference_ciphertext
        assert stored.payment_status == "UNDER_REVIEW"
        assert audit == ("FOUNDER","founder-primary","TELEGRAM")
        settlement=client.post("/api/v1/founder/settlements",headers=headers,json={
            "order_id":code,"claim_id":claim_id,"observed_reference":reference,
            "payment_method":"telebirr","amount_etb":1500,"currency":"ETB",
            "recipient_confirmed":True,"payer_mobile":"+251912345678",
            "evidence_source":"TELEBIRR_PORTAL","settled_at":datetime.now(timezone.utc).isoformat(),
        })
        assert settlement.status_code == 200, settlement.text
        evidence_id=settlement.json()["evidence_id"]
        approved=client.post("/api/v1/founder/approve",headers=headers,json={
            "order_id":code,"claim_id":claim_id,"evidence_id":evidence_id,
            "reason":"Synthetic independent settlement verified",
        })
        assert approved.status_code == 200, approved.text
        assert approved.json() == {"grant_id":None,"status":"PAYMENT_CONFIRMED",
                                   "fulfillment_mode":"manual_telegram","delivery_status":"PENDING"}
        assert client.get("/api/v1/founder/metrics").json()["verified_revenue_etb"] == 1500
        for state in ("PREPARING","SENT","DELIVERED"):
            changed=client.post("/api/v1/founder/deliveries/status",headers=headers,
                                json={"order_id":code,"status":state})
            assert changed.status_code == 200, changed.text
        metrics=client.get("/api/v1/founder/metrics").json()
        assert metrics["payment_verified"] == 1
        assert metrics["verified_revenue_etb"] == 1500
        assert metrics["delivery_delivered"] == 1
    with founder_app.state.engine.connect() as db:
        order_id=db.scalar(text("SELECT id FROM production_orders WHERE code=:code"),{"code":code})
        assert db.execute(text("SELECT count(*) FROM production_download_grants WHERE order_id=:id"),
                          {"id":order_id}).scalar_one() == 0


def _insert_order(app, *, method="telebirr"):
    cfg=app.state.founder_config
    code="PW-"+secrets.token_hex(12).upper()
    order_id=str(uuid4())
    token=private_token(cfg.token_secret,secrets.token_urlsafe(32))
    with app.state.engine.begin() as db:
        db.execute(text("""
            INSERT INTO production_orders
              (id,code,customer_name,mobile_e164,method,amount_etb,currency,status,
               idempotency_hash,request_fingerprint,access_hash,created_at)
            VALUES (:id,:code,'Synthetic Telegram Parent','+251912345678',:method,1500,
                    'ETB','AWAITING_PAYMENT',:idem,:fingerprint,:access_hash,now())
        """),{"id":order_id,"code":code,"method":method,"idem":secrets.token_hex(32),
               "fingerprint":secrets.token_hex(32),
               "access_hash":hmac_digest(cfg.token_secret,"stored:v1:"+token)})
    return code


@pytest.mark.parametrize("founder_app", [True], indirect=True)
def test_telegram_claim_requires_session_csrf_gate_and_matching_order(founder_app):
    code=_insert_order(founder_app,method="bank")
    body={"order_id":code,"payment_method":"telebirr",
          "transaction_reference":"SIM-MISMATCH-"+secrets.token_hex(4).upper()}
    with TestClient(founder_app,base_url="https://founder.example") as client:
        assert client.post("/api/v1/founder/claims/telegram",json=body).status_code==401
        logged=login(client); assert logged.status_code==200
        headers={"Origin":"https://founder.example"}
        assert client.post("/api/v1/founder/claims/telegram",headers=headers,json=body).status_code==403
        headers["X-CSRF-Token"]=logged.json()["csrf_token"]
        assert client.post("/api/v1/founder/claims/telegram",headers=headers,json=body).status_code==409
        body["payment_method"]="bank"
        first=client.post("/api/v1/founder/claims/telegram",headers=headers,json=body)
        assert first.status_code==201, first.text
        duplicate=client.post("/api/v1/founder/claims/telegram",headers=headers,json=body)
        assert duplicate.status_code==409
        missing={**body,"order_id":"PW-"+"F"*24,
                 "transaction_reference":"SIM-MISSING-"+secrets.token_hex(4).upper()}
        assert client.post("/api/v1/founder/claims/telegram",headers=headers,json=missing).status_code==404


@pytest.mark.parametrize("founder_app", [True], indirect=True)
def test_concurrent_telegram_claim_requests_cannot_reuse_reference(founder_app):
    codes=[_insert_order(founder_app),_insert_order(founder_app)]
    reference="SIM-CONCURRENT-TG-"+secrets.token_hex(6).upper()
    with TestClient(founder_app,base_url="https://founder.example") as client:
        logged=login(client); assert logged.status_code==200
        headers={"Origin":"https://founder.example","X-CSRF-Token":logged.json()["csrf_token"]}
        def submit(code):
            return client.post("/api/v1/founder/claims/telegram",headers=headers,json={
                "order_id":code,"payment_method":"telebirr","transaction_reference":reference})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(submit,codes))
        assert sorted(response.status_code for response in responses)==[201,409]
    with founder_app.state.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM production_payment_claims WHERE reference_digest IS NOT NULL"))==1
        assert db.scalar(text("SELECT count(*) FROM production_payment_audit_events WHERE event_type='PAYMENT_CLAIM_RECORDED_TELEGRAM'"))==1


def test_founder_request_cannot_supply_recipient_configuration(founder_app):
    with TestClient(founder_app, base_url="https://founder.example") as client:
        response=login(client); assert response.status_code==200
        body={"order_id":"PW-"+"A"*24,"claim_id":"claim-1","observed_reference":"SIM-REFERENCE-1",
              "payment_method":"telebirr","amount_etb":1500,"currency":"ETB","recipient_confirmed":True,
              "payer_mobile":"+251912345678","evidence_source":"TELEBIRR_PORTAL",
              "settled_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"recipient":"ATTACKER-ACCOUNT"}
        result=client.post("/api/v1/founder/settlements",headers={"Origin":"https://founder.example",
              "X-CSRF-Token":response.json()["csrf_token"]},json=body)
        assert result.status_code==422


def test_encryption_key_rotation_aad_and_tamper_detection():
    old={"old":b"o"*32,"new":b"n"*32}
    envelope=encrypt_sensitive("SIMULATED-REFERENCE",keyring=old,key_id="old",aad="claim:one")
    assert decrypt_sensitive(envelope,keyring=old,aad="claim:one")=="SIMULATED-REFERENCE"
    with pytest.raises(InvalidCiphertext): decrypt_sensitive(envelope,keyring=old,aad="claim:two")
    parts=envelope.split(":"); parts[-1]=("A" if parts[-1][0]!="A" else "B")+parts[-1][1:]
    with pytest.raises(InvalidCiphertext): decrypt_sensitive(":".join(parts),keyring=old,aad="claim:one")
    new_envelope=encrypt_sensitive("ROTATED",keyring=old,key_id="new",aad="claim:one")
    assert decrypt_sensitive(new_envelope,keyring=old,aad="claim:one")=="ROTATED"


def test_totp_parser_rejects_invalid_codes():
    assert _totp_counter(TOTP_SECRET,totp(TOTP_SECRET),int(time.time())) is not None
    assert _totp_counter(TOTP_SECRET,"12x456") is None

