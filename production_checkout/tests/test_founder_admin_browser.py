"""HTTPS browser acceptance for the private founder dashboard (disposable PostgreSQL only)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import socket
import ssl
import struct
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from argon2 import PasswordHasher
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from playwright.sync_api import sync_playwright
from sqlalchemy import text
import uvicorn

from production_checkout.app import build_app
from production_checkout.founder_security import FounderConfig, create_founder_router

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="requires disposable PostgreSQL")
PASSWORD = "browser-test-only founder password"
TOTP_SECRET = base64.b32encode(b"browser-test-seed-12345").decode().rstrip("=")
KEY = b"b" * 32


def totp(secret: str) -> str:
    seed = base64.b32decode(secret + "=" * ((8-len(secret)%8)%8))
    step = int(time.time() // 30)
    digest = hmac.new(seed, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return f"{(struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1000000:06d}"


def certificate_files(directory: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1))
            .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .sign(key, hashes.SHA256()))
    key_path, cert_path = directory / "founder-test.key", directory / "founder-test.crt"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path,key_path


@pytest.fixture
def running_founder_server(tmp_path):
    password_hash = PasswordHasher(time_cost=2,memory_cost=32768,parallelism=1).hash(PASSWORD)
    sock=socket.socket();sock.bind(("127.0.0.1",0));port=sock.getsockname()[1];sock.close()
    origin=f"https://127.0.0.1:{port}"
    app=build_app(database_url=DATABASE_URL,token_secret="browser-token-"+"t"*40,
                  allowed_origins=[origin],intake_enabled=True,
                  payment_accounts={"telebirr":{"name":"Synthetic Telebirr","number":"TEST-ONLY","holder":"Synthetic"},
                                    "bank":{"name":"Synthetic CBE","number":"TEST-ONLY","holder":"Synthetic"}})
    cfg=FounderConfig(username="browser-founder",password_hash=password_hash,totp_secret=TOTP_SECRET,
        session_key=b"s"*32,rate_key=b"r"*32,encryption_keys={"ci-k1":KEY},active_encryption_key_id="ci-k1",
        token_secret="browser-token-"+"t"*40,reference_hash_secret="h"*48,identity_hash_secret="i"*48,
        recipient_hash_secret="p"*48,telebirr_recipient="SYNTHETIC-TELEBIRR-RECIPIENT",
        bank_recipient="SYNTHETIC-CBE-RECIPIENT",allowed_origins=(origin,),auth_enabled=True,
        approvals_enabled=True,secure_cookie=True)
    app.include_router(create_founder_router(app.state.sessions,cfg))
    with app.state.engine.begin() as db:
        db.execute(text("TRUNCATE production_orders CASCADE"))
        db.execute(text("TRUNCATE production_founder_sessions,production_founder_rate_limits,production_founder_security_events"))
        db.execute(text("UPDATE production_founder_auth_control SET last_totp_step=-1 WHERE singleton_id=1"))
    cert,key=certificate_files(tmp_path)
    server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=port,ssl_certfile=str(cert),ssl_keyfile=str(key),log_level="error",lifespan="on"))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        try:
            with httpx.Client(verify=False,timeout=.5) as client:
                if client.get(origin+"/healthz").status_code==200:break
        except Exception:time.sleep(.1)
    else:
        server.should_exit=True;raise RuntimeError("Local HTTPS founder test app did not start")
    try:
        yield origin,app
    finally:
        server.should_exit=True;thread.join(timeout=10)
        with app.state.engine.begin() as db:
            db.execute(text("TRUNCATE production_orders CASCADE"))
            db.execute(text("TRUNCATE production_founder_sessions,production_founder_rate_limits,production_founder_security_events"))
            db.execute(text("UPDATE production_founder_auth_control SET last_totp_step=-1 WHERE singleton_id=1"))
        app.state.engine.dispose()


def test_founder_browser_auth_claim_approval_delivery_and_expiry(running_founder_server):
    origin,app=running_founder_server
    with httpx.Client(verify=False) as api:
        assert api.get(origin+"/api/v1/founder/metrics").status_code==401
        order_codes=[]
        for suffix in ("A","B"):
            r=api.post(origin+"/api/v1/orders",headers={"Idempotency-Key":base64.urlsafe_b64encode((suffix*32).encode()).decode().rstrip("=")},
                       json={"customer_name":f"Synthetic Parent {suffix}","mobile":"+251912345678","payment_method":"telebirr"})
            assert r.status_code==201,r.text;order_codes.append(r.json()["order"]["order_id"])

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":390,"height":844},ignore_https_errors=True)
        protected=page.request.get(origin+"/api/v1/founder/ui")
        assert protected.status==401
        page.goto(origin+"/api/v1/founder/ui/login")
        assert page.title()=="Founder sign in · ParentWise Ethiopia"
        page.locator("#username").fill("browser-founder");page.locator("#password").fill(PASSWORD);page.locator("#totp").fill(totp(TOTP_SECRET))
        page.locator("#login-form button").click();page.wait_for_url("**/api/v1/founder/ui")
        page.get_by_role("heading",name="Overview",exact=True).wait_for()
        page.wait_for_function("document.querySelector('#metric-revenue').textContent !== '—'", timeout=10000)
        assert page.locator("#metric-revenue").inner_text()=="0 ETB", page.locator("#global-message").inner_text()
        assert page.locator("#metric-awaiting").inner_text()=="2"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

        page.get_by_role("button",name="Payment review").click()
        page.locator("#claim-order").fill(order_codes[0]);page.locator("#lookup-order").click()
        page.locator("#claim-reference").fill("SYNTH-BROWSER-CLAIM-"+"A"*8)
        page.locator("#telegram-claim-form button[type=submit]").click()
        page.get_by_text("This is not payment confirmation.").wait_for()
        page.get_by_role("button",name="Review independently").click()
        page.locator("#observed-reference").fill("SYNTH-BROWSER-CLAIM-"+"A"*8)
        page.locator("#recipient-confirmed").check()
        page.locator("#settlement-form button[type=submit]").click()
        page.get_by_text("Independent settlement evidence recorded. No sale is counted until approval.").wait_for()
        assert page.locator("#approve-payment").is_enabled()
        assert page.locator("#metric-revenue").inner_text()=="0 ETB"
        page.locator("#decision-reason").fill("Synthetic receiving account settlement verified")
        page.locator("#approve-payment").click()
        page.get_by_text("Payment approved after independent verification.").wait_for()
        page.wait_for_function("document.querySelector('#metric-revenue').textContent === '1,500 ETB'", timeout=10000)
        assert page.locator("#metric-revenue").inner_text()=="1,500 ETB"
        assert page.locator("#metric-paid").inner_text()=="1"

        # Same transaction reference cannot be claimed for a different order.
        page.get_by_role("button",name="Payment review").click()
        page.locator("#claim-order").fill(order_codes[1]);page.locator("#lookup-order").click()
        page.locator("#claim-reference").fill("SYNTH-BROWSER-CLAIM-"+"A"*8)
        page.locator("#telegram-claim-form button[type=submit]").click()
        page.get_by_text("Settlement reference was already used").wait_for()
        assert page.locator("#metric-revenue").inner_text()=="1,500 ETB"

        page.get_by_role("button",name="Telegram delivery").click()
        delivery=page.locator(".delivery-card").filter(has_text=order_codes[0])
        def record_delivery(button_name, expected):
            page.locator("#global-message").evaluate("el => { el.textContent=''; el.classList.remove('visible'); }")
            delivery.get_by_role("button",name=button_name).click()
            page.wait_for_function("expected => document.querySelector('#global-message').textContent.includes(expected)", arg=expected)
        record_delivery("Mark preparing","Delivery marked preparing.")
        record_delivery("Mark failed","Delivery marked failed.")
        delivery.get_by_role("button",name="View history").click()
        page.wait_for_function("document.querySelectorAll('#history-list li').length === 2", timeout=10000)
        assert page.locator("#history-list li").count()==2
        page.get_by_role("button",name="Close history").click()
        record_delivery("Mark preparing","Delivery marked preparing.")
        record_delivery("Mark sent","Delivery marked sent.")
        record_delivery("Mark completed · founder-recorded","Delivery marked completed · founder-recorded.")
        history=page.request.get(origin+f"/api/v1/founder/deliveries/{order_codes[0]}/history")
        assert history.status==200 and len(history.json()["history"])==5
        assert page.locator("#metric-deliveries").inner_text()=="0"

        with app.state.engine.begin() as db:
            db.execute(text("UPDATE production_founder_sessions SET expires_at=now()-interval '1 second'"))
        page.get_by_role("button",name="Refresh data").click()
        page.wait_for_url("**/api/v1/founder/ui/login")
        browser.close()
