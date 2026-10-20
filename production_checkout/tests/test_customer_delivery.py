"""HTTP customer-to-founder acceptance against disposable PostgreSQL only."""
from __future__ import annotations
import base64, hashlib, hmac, os, secrets, struct, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import text

from production_checkout.app import build_app, hmac_digest
from production_checkout.customer_delivery import CustomerDeliveryConfig, create_customer_delivery_router
from production_checkout.founder_security import FounderConfig, create_founder_router
from production_checkout.private_storage import MockObjectStore, ProductFile, ProductManifest

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="requires disposable PostgreSQL")
TOKEN_SECRET="disposable-customer-token-key-"+"x"*32
REF_SECRET="disposable-ref-hash-key-"+"r"*32
ID_SECRET="disposable-identity-hash-key-"+"i"*32
RECIP_SECRET="disposable-recipient-hash-key-"+"p"*32
KEY=b"k"*32
PASSWORD="disposable founder password for tests"
TOTP_SECRET=base64.b32encode(b"0123456789abcdef0123").decode().rstrip("=")
BUCKET="fictional-private-test-bucket"
FILES={n:(b"%PDF-1.4\n% fictional dummy part "+str(n).encode()+b"\n%%EOF\n") for n in range(1,6)}
ORIGIN="https://founder.example"

def current_totp(secret):
    seed=base64.b32decode(secret+"="*((8-len(secret)%8)%8))
    counter=int(time.time()//30)
    digest=hmac.new(seed,struct.pack(">Q",counter),hashlib.sha1).digest()
    offset=digest[-1]&15
    return f"{(struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1000000:06d}"

@pytest.fixture(scope="module")
def password_hash():
    return PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1).hash(PASSWORD)

@pytest.fixture
def qa(password_hash):
    app=build_app(database_url=DATABASE_URL,token_secret=TOKEN_SECRET,
        allowed_origins=[ORIGIN],intake_enabled=False)
    cfg=FounderConfig(username="synthetic-founder",password_hash=password_hash,
        totp_secret=TOTP_SECRET,session_key=b"s"*32,rate_key=b"r"*32,
        encryption_keys={"test-k1":KEY},active_encryption_key_id="test-k1",
        token_secret=TOKEN_SECRET,reference_hash_secret=REF_SECRET,
        identity_hash_secret=ID_SECRET,recipient_hash_secret=RECIP_SECRET,
        telebirr_recipient="FICTIONAL-TELEBIRR",bank_recipient="FICTIONAL-CBE",
        allowed_origins=(ORIGIN,),auth_enabled=True,approvals_enabled=True,secure_cookie=True)
    blobs={(BUCKET, f"releases/qa-release/part-{n}.pdf"):FILES[n] for n in range(1,6)}
    manifest=ProductManifest("qa-release",[
        ProductFile(n,f"releases/qa-release/part-{n}.pdf",hashlib.sha256(FILES[n]).hexdigest())
        for n in range(1,6)])
    app.include_router(create_founder_router(app.state.sessions,cfg))
    app.state.test_store=MockObjectStore(blobs)
    app.include_router(create_customer_delivery_router(app.state.sessions,
        CustomerDeliveryConfig(TOKEN_SECRET,"q"*48,cfg,BUCKET,manifest,
                               app.state.test_store,rate_limit=100)))
    with app.state.engine.begin() as db:
        db.execute(text("TRUNCATE production_orders CASCADE"))
        db.execute(text("TRUNCATE production_customer_rate_limits, production_founder_sessions, production_founder_rate_limits, production_founder_security_events"))
        db.execute(text("UPDATE production_founder_auth_control SET last_totp_step=-1 WHERE singleton_id=1"))
    yield app,cfg
    with app.state.engine.begin() as db:
        db.execute(text("TRUNCATE production_orders CASCADE"))
        db.execute(text("TRUNCATE production_customer_rate_limits, production_founder_sessions, production_founder_rate_limits, production_founder_security_events"))
        db.execute(text("UPDATE production_founder_auth_control SET last_totp_step=-1 WHERE singleton_id=1"))
    app.state.engine.dispose()

def make_order(app, method="telebirr", mobile="+251912345678"):
    code="PW-"+uuid4().hex[:24].upper()
    token=secrets.token_urlsafe(32)
    order_id=str(uuid4())
    with app.state.engine.begin() as db:
        db.execute(text("""INSERT INTO production_orders
          (id,code,customer_name,mobile_e164,method,amount_etb,currency,status,
           idempotency_hash,request_fingerprint,access_hash,created_at)
          VALUES (:id,:code,'Synthetic Parent',:mobile,:method,1500,'ETB','AWAITING_PAYMENT',
          :idem,:fingerprint,:access_hash,now())"""),
          {"id":order_id,"code":code,"mobile":mobile,"method":method,
           "idem":secrets.token_hex(32),"fingerprint":secrets.token_hex(32),
           "access_hash":hmac_digest(TOKEN_SECRET,"stored:v1:"+token)})
    return code,token

def founder_login(client):
    r=client.post("/api/v1/founder/session",headers={"Origin":ORIGIN},json={
        "username":"synthetic-founder","password":PASSWORD,"totp":current_totp(TOTP_SECRET)})
    assert r.status_code==200,r.text
    return {"Origin":ORIGIN,"X-CSRF-Token":r.json()["csrf_token"]}

def submit_claim(client,code,token,reference):
    return client.post(f"/api/v1/orders/{code}/payment-claims",
        headers={"Authorization":"Bearer "+token},
        json={"transaction_reference":reference})

def settlement(client,headers,code,claim_id,reference,payer="+251912345678"):
    return client.post("/api/v1/founder/settlements",headers=headers,json={
        "order_id":code,"claim_id":claim_id,"observed_reference":reference,
        "payment_method":"telebirr","amount_etb":1500,"currency":"ETB",
        "recipient_confirmed":True,"manual_reconciliation_completed":True,"payer_mobile":payer,"evidence_source":"TELEBIRR_PORTAL",
        "settled_at":datetime.now(timezone.utc).isoformat(),"note":"Synthetic independent portal check"})

def test_complete_claim_approval_five_downloads_and_revocation(qa):
    app,_=qa
    code,token=make_order(app)
    with TestClient(app,base_url=ORIGIN) as client:
        assert client.get(f"/api/v1/orders/{code}/checkout-status",
            headers={"Authorization":"Bearer "+token}).json()["status"]=="Awaiting Payment"
        assert client.get(f"/api/v1/orders/{code}/downloads/part-1.pdf",
            headers={"Authorization":"Bearer "+token}).status_code==404
        reference="SIM-HTTP-"+secrets.token_hex(6).upper()
        claimed=submit_claim(client,code,token,reference)
        assert claimed.status_code==202,claimed.text
        claim_id=claimed.json()["claim_id"]
        assert "not confirmed" in claimed.json()["message"]
        assert client.get(f"/api/v1/orders/{code}/checkout-status",
            headers={"Authorization":"Bearer "+token}).json()["status"]=="Under Review"
        with app.state.engine.connect() as db:
            ciphertext=db.execute(text("SELECT reference_ciphertext FROM production_payment_claims WHERE id=:id"),
                                  {"id":claim_id}).scalar_one()
            assert reference not in ciphertext and ciphertext.startswith("enc:v1:")
            assert db.execute(text("SELECT payment_status FROM production_payment_fulfillment_state WHERE order_id=(SELECT id FROM production_orders WHERE code=:code)"),
                              {"code":code}).scalar_one()=="UNDER_REVIEW"
        headers=founder_login(client)
        ev=settlement(client,headers,code,claim_id,reference)
        assert ev.status_code==200,ev.text
        evidence_id=ev.json()["evidence_id"]
        approved=client.post("/api/v1/founder/approve",headers=headers,json={
            "order_id":code,"claim_id":claim_id,"evidence_id":evidence_id,
            "reason":"Independent settlement matched the bank portal record"})
        assert approved.status_code==200,approved.text
        assert client.get(f"/api/v1/orders/{code}/checkout-status",
            headers={"Authorization":"Bearer "+token}).json()["status"]=="Ready to Download"
        def fetch(part):
            with TestClient(app,base_url=ORIGIN) as concurrent_client:
                return concurrent_client.get(f"/api/v1/orders/{code}/downloads/part-{part}.pdf",
                    headers={"Authorization":"Bearer "+token})
        with ThreadPoolExecutor(max_workers=5) as pool:
            concurrent=list(pool.map(fetch,range(1,6)))
        assert all(result.status_code==200 for result in concurrent)
        for part,got in enumerate(concurrent,1):
            assert got.content==FILES[part]
            assert got.headers["cache-control"]=="private, no-store, max-age=0"
            assert "attachment" in got.headers["content-disposition"]
        app.state.test_store._objects.pop((BUCKET,"releases/qa-release/part-3.pdf"))
        missing=client.get(f"/api/v1/orders/{code}/downloads/part-3.pdf",
            headers={"Authorization":"Bearer "+token})
        assert missing.status_code==503
        app.state.test_store._objects[(BUCKET,"releases/qa-release/part-3.pdf")]=b"altered bytes"
        corrupted=client.get(f"/api/v1/orders/{code}/downloads/part-3.pdf",
            headers={"Authorization":"Bearer "+token})
        assert corrupted.status_code==503
        assert client.get(f"/api/v1/orders/{code}/downloads/part-1.pdf",
            headers={"Authorization":"Bearer "+secrets.token_urlsafe(32)}).status_code==404
        revoked=client.post("/api/v1/founder/grants/revoke",headers=headers,json={
            "order_id":code,"reason":"Synthetic revocation verification"})
        assert revoked.status_code==200,revoked.text
        assert client.get(f"/api/v1/orders/{code}/downloads/part-1.pdf",
            headers={"Authorization":"Bearer "+token}).status_code==404
        with app.state.engine.connect() as db:
            assert db.execute(text("SELECT count(*) FROM production_payment_audit_events WHERE order_id=(SELECT id FROM production_orders WHERE code=:code)"),
                              {"code":code}).scalar_one()>=4

def test_third_party_exception_requires_founder_action_and_missing_payer_is_rejected(qa):
    app,_=qa
    code,token=make_order(app)
    with TestClient(app,base_url=ORIGIN) as client:
        ref="SIM-RELATIVE-"+secrets.token_hex(4).upper()
        claim=submit_claim(client,code,token,ref); assert claim.status_code==202
        claim_id=claim.json()["claim_id"]
        headers=founder_login(client)
        missing=client.post("/api/v1/founder/settlements",headers=headers,json={
            "order_id":code,"claim_id":claim_id,"observed_reference":ref,
            "payment_method":"telebirr","amount_etb":1500,"currency":"ETB",
            "recipient_confirmed":True,"evidence_source":"TELEBIRR_PORTAL",
            "settled_at":datetime.now(timezone.utc).isoformat()})
        assert missing.status_code==422
        unchecked=client.post("/api/v1/founder/settlements",headers=headers,json={
            "order_id":code,"claim_id":claim_id,"observed_reference":ref,
            "payment_method":"telebirr","amount_etb":1500,"currency":"ETB",
            "recipient_confirmed":True,"manual_reconciliation_completed":False,
            "payer_mobile":"+251911111111","evidence_source":"TELEBIRR_PORTAL",
            "settled_at":datetime.now(timezone.utc).isoformat()})
        assert unchecked.status_code==409
        ev=settlement(client,headers,code,claim_id,ref,payer="+251911111111")
        assert ev.status_code==200,ev.text
        evidence_id=ev.json()["evidence_id"]
        body={"order_id":code,"claim_id":claim_id,"evidence_id":evidence_id,
              "reason":"Review matched transfer independently"}
        assert client.post("/api/v1/founder/approve",headers=headers,json=body).status_code==409
        exception=client.post("/api/v1/founder/third-party-exceptions",headers=headers,json={
            "order_id":code,"claim_id":claim_id,"evidence_id":evidence_id,
            "relationship":"SPOUSE","rationale":"Synthetic spouse payment confirmed with buyer"})
        assert exception.status_code==200,exception.text
        approved=client.post("/api/v1/founder/approve",headers=headers,json={
            **body,"third_party_exception_id":exception.json()["exception_id"]})
        assert approved.status_code==200,approved.text
        assert client.get(f"/api/v1/orders/{code}/downloads/part-2.pdf",
            headers={"Authorization":"Bearer "+token}).status_code==200

def test_customer_reference_is_globally_unique_and_invalid_token_never_accesses_order(qa):
    app,_=qa
    code1,token1=make_order(app); code2,token2=make_order(app)
    with TestClient(app,base_url=ORIGIN) as client:
        ref="SIM-DUP-"+secrets.token_hex(6).upper()
        assert submit_claim(client,code1,token1,ref).status_code==202
        assert submit_claim(client,code2,token2,ref.lower()).status_code==409
        assert client.get(f"/api/v1/orders/{code1}/checkout-status",
            headers={"Authorization":"Bearer "+secrets.token_urlsafe(32)}).status_code==404


def test_founder_http_rejection_is_audited_and_never_unlocks_download(qa):
    app,_=qa
    code,token=make_order(app)
    with TestClient(app,base_url=ORIGIN) as client:
        claimed=submit_claim(client,code,token,"SIM-REJECT-"+secrets.token_hex(5).upper())
        assert claimed.status_code==202
        claim_id=claimed.json()["claim_id"]
        headers=founder_login(client)
        rejected=client.post("/api/v1/founder/reject",headers=headers,json={
            "order_id":code,"claim_id":claim_id,
            "reason":"Independent settlement could not be verified"})
        assert rejected.status_code==200,rejected.text
        assert client.get(f"/api/v1/orders/{code}/checkout-status",
            headers={"Authorization":"Bearer "+token}).json()["status"]=="Awaiting Payment"
        assert client.get(f"/api/v1/orders/{code}/downloads/part-1.pdf",
            headers={"Authorization":"Bearer "+token}).status_code==404
        with app.state.engine.connect() as db:
            assert db.execute(text("SELECT count(*) FROM production_payment_audit_events WHERE order_id=(SELECT id FROM production_orders WHERE code=:code) AND event_type='PAYMENT_REJECTED'"),
                              {"code":code}).scalar_one()==1
