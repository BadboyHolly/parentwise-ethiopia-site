import base64
import hmac
import hashlib
import struct
import secrets
import time
from datetime import datetime, timedelta, timezone

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from api.models import Base, Order, AdminAudit, AdminSession, AdminTotpState
from api import admin, admin_security

PASSWORD='FakeLocalTestPassword!fromTestOnly'
SECRET='JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'
ORIGIN='https://admin.example.test'


def otp(secret=SECRET, when=None):
    now=int(time.time()) if when is None else when
    digest=hmac.new(base64.b32decode(secret),struct.pack('>Q',now//30),hashlib.sha1).digest()
    offset=digest[-1]&15
    return f"{(int.from_bytes(digest[offset:offset+4],'big')&0x7fffffff)%1000000:06d}"


@pytest.fixture
def system(tmp_path,monkeypatch):
    monkeypatch.setenv('FOUNDER_USERNAME','FounderQA')
    monkeypatch.setenv('FOUNDER_PASSWORD_HASH',PasswordHasher(time_cost=1,memory_cost=10240).hash(PASSWORD))
    monkeypatch.setenv('FOUNDER_TOTP_SECRET',SECRET)
    monkeypatch.setenv('ADMIN_ORIGIN',ORIGIN)
    monkeypatch.setenv('APP_MODE','qa')
    monkeypatch.setenv('PAYMENTS_ENABLED','false')
    engine=create_engine(f'sqlite:///{tmp_path}/admin.db',connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    maker=sessionmaker(engine,expire_on_commit=False)
    with maker.begin() as db:
        db.add(AdminTotpState(id=1,last_accepted_step=0))
        for i in range(27):
            db.add(Order(id=str(i),order_code=f'PW-QA-{i:024X}',customer_name=f'Fictional Parent {i}', mobile_e164='+251912345678',payment_method='bank' if i%2 else 'telebirr',amount_etb=1500,currency='ETB',status='PENDING_PAYMENT',idempotency_hash=f'{i:064X}',request_fingerprint='f'*64,access_token_hash='a'*64))
    app=FastAPI(docs_url=None)
    admin.mount_admin(app,maker)
    with TestClient(app,base_url=ORIGIN) as client: yield client,maker,monkeypatch
    engine.dispose()


def sign_in(client, username='FounderQA', password=PASSWORD, totp_code=None, headers=None):
    return client.post('/admin/api/login',json={'username':username,'password':password,'totp_code':totp_code or otp()},headers={'Origin':ORIGIN,**(headers or {})})


def test_no_public_order_lists_or_account_registration(system):
    client, _, _ = system
    for p in ('/admin/api/overview','/admin/api/orders','/admin/api/orders/PW-QA-000000000000000000000000','/admin/api/session'):
        assert client.get(p).status_code==401
    assert client.post('/admin/api/register').status_code==404
    assert client.post('/admin/api/orders/PW-QA-000000000000000000000000/paid').status_code==404
    assert client.post('/admin/api/orders/PW-QA-000000000000000000000000/refund').status_code==404
    assert client.post('/admin/api/orders/PW-QA-000000000000000000000000/deliver').status_code==404
    assert client.get('/admin').status_code==200
    assert 'Fictional Parent' not in client.get('/admin').text


def test_signin_creates_hardened_session_and_allows_queries(system):
    client,maker,_=system
    r=sign_in(client); assert r.status_code==200,r.text
    cookie=r.headers['set-cookie']; assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=strict' in cookie and '__Host-pw_admin_session=' in cookie
    assert 'csrf' in r.json() and len(r.json()['csrf'])==43
    assert client.get('/admin/api/session').status_code==200
    stats=client.get('/admin/api/overview');assert stats.status_code==200;assert stats.json()['total']==27 and stats.json()['pending']==27
    assert stats.json()['methods']=={'telebirr':14,'bank':13}
    result=client.get('/admin/api/orders?page=2&page_size=10')
    assert result.status_code==200 and len(result.json()['items'])==10 and result.json()['has_more']
    assert result.json()['total']==27
    with maker() as db:
        sess=db.scalars(select(AdminSession)).one()
        assert len(sess.session_hash)==64
        assert sess.session_hash not in cookie


def test_reject_wrong_password_wrong_totp_and_replay(system):
    client,maker,_=system
    assert sign_in(client,password='notcorrect').status_code==401
    assert sign_in(client,totp_code='000000').status_code==401
    assert sign_in(client).status_code==200
    # Current TOTP cannot be reused for another session even with correct password.
    assert sign_in(client).status_code==401
    with maker() as db:
        types=[e.event for e in db.scalars(select(AdminAudit)).all()]
        assert types.count('login_failed')==3 and 'login_success' in types


def test_customer_bearer_token_does_not_authorize(system):
    client,*_=system
    x=client.get('/admin/api/orders',headers={'Authorization':'Bearer FakeCustomerToken'})
    assert x.status_code==401


def test_filters_and_details(system):
    client,*_=system
    assert sign_in(client).status_code==200
    filtered=client.get('/admin/api/orders?method=bank&status=PENDING_PAYMENT&page_size=7')
    assert filtered.status_code==200 and filtered.json()['total']==13 and len(filtered.json()['items'])==7
    prefix=client.get('/admin/api/orders?order_id=PW-QA-00000000000000000000001')
    assert prefix.status_code==200 and prefix.json()['total']>=1
    info=client.get('/admin/api/orders/PW-QA-000000000000000000000001')
    assert info.status_code==200 and info.json()['order']['name']=='Fictional Parent 1' and info.json()['timeline'][0]['status']=='PENDING_PAYMENT'
    assert client.get('/admin/api/orders?method=other').status_code==422
    assert client.get('/admin/api/orders?page_size=200').status_code==422
    assert client.get('/admin/api/orders?from_date=2026-10-10&to_date=2026-09-01').status_code==422


def test_logout_csrf_origin_and_session_revoke(system):
    client,maker,_=system
    r=sign_in(client);csrf=r.json()['csrf']; assert r.status_code==200
    assert client.post('/admin/api/logout',headers={'Origin':'https://evil.example','X-CSRF-Token':csrf}).status_code==403
    assert client.post('/admin/api/logout',headers={'Origin':ORIGIN,'X-CSRF-Token':'wrong'}).status_code==403
    assert client.get('/admin/api/overview').status_code==200
    assert client.post('/admin/api/logout',headers={'Origin':ORIGIN,'X-CSRF-Token':csrf}).status_code==200
    assert client.get('/admin/api/orders').status_code==401
    with maker() as db:assert db.scalars(select(AdminSession)).first().revoked_at is not None


def test_session_expiration_and_agent_binding(system):
    client,maker,_=system
    assert sign_in(client).status_code==200
    assert client.get('/admin/api/orders',headers={'User-Agent':'forged-other-agent'}).status_code==401


def test_idle_expiration(system):
    client,maker,_=system
    assert sign_in(client).status_code==200
    with maker.begin() as db:
        s=db.scalars(select(AdminSession)).one();s.last_seen_at=datetime.now(timezone.utc)-timedelta(minutes=21)
    assert client.get('/admin/api/orders').status_code==401


def test_credentials_rotation_revokes_old_sessions(system):
    client,maker,monkeypatch=system
    assert sign_in(client).status_code==200
    monkeypatch.setenv('FOUNDER_PASSWORD_HASH',PasswordHasher(time_cost=1,memory_cost=10240).hash('NewTestPasswordSoLong!'))
    assert client.get('/admin/api/orders').status_code==401


def test_origin_login_csrf_and_same_site(system):
    client,*_=system
    assert client.post('/admin/api/login',json={'username':'FounderQA','password':PASSWORD,'totp_code':otp()}).status_code==403
    assert sign_in(client,headers={'Origin':'https://evil.example'}).status_code==403
    assert sign_in(client,headers={'Sec-Fetch-Site':'cross-site'}).status_code==403


def test_login_global_rate_limit(system):
    client,*_=system
    responses=[sign_in(client,password='incorrect').status_code for _ in range(9)]
    assert responses==[401]*8+[429]


def test_unconfigured_fail_closed(system):
    client,_,monkeypatch=system
    monkeypatch.delenv('FOUNDER_PASSWORD_HASH')
    assert client.get('/admin').status_code==503
    assert client.get('/admin/api/orders').status_code==503