"""Disposable-PostgreSQL tests for founder session and payment route controls."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import text

from production_checkout.app import build_app
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
def founder_app(password_hash):
    app = build_app(database_url=DATABASE_URL, token_secret="t"*48,
                    allowed_origins=["https://founder.example"], intake_enabled=False)
    cfg = FounderConfig(
        username="founder-primary", password_hash=password_hash, totp_secret=TOTP_SECRET,
        session_key=b"s"*32, rate_key=b"r"*32, encryption_keys={"test-k1":KEY},
        active_encryption_key_id="test-k1", token_secret="t"*48,
        reference_hash_secret="h"*48, identity_hash_secret="i"*48,
        recipient_hash_secret="p"*48, telebirr_recipient="TEST-TEL-RECIPIENT",
        bank_recipient="TEST-BANK-RECIPIENT", allowed_origins=("https://founder.example",),
        auth_enabled=True, approvals_enabled=False, secure_cookie=True,
    )
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
            db.execute(text("UPDATE production_founder_sessions SET expires_at=now()-interval '1 minute'"))
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

