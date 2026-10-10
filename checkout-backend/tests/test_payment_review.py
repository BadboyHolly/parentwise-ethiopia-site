"""Synthetic-founder QA reconciliation tests; compatible with disposable PostgreSQL CI."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, text
from api import payment_review
from api.models import Order, PaymentReview, PaymentEvent, SimulatedLedgerEntry
from test_admin import system, sign_in, ORIGIN


@pytest.fixture
def review_env(system):
    client, maker, patcher = system
    payment_review.mount_payment_review(client.app, maker)
    login = sign_in(client)
    assert login.status_code == 200
    headers = {'Origin': ORIGIN, 'X-CSRF-Token': login.json()['csrf']}
    yield client, maker, headers


def code(index):
    return f'PW-QA-{index:024X}'


def post(client, path, headers, body=None):
    return client.post(path, headers=headers, json=body if body is not None else {})


def ledger(client, headers, method='telebirr', amount=1500):
    r = post(client,'/admin/api/qa-ledger',headers,{'method':method,'amount_etb':amount})
    assert r.status_code == 201, r.text
    assert r.json()['simulated_only'] is True
    return r.json()['test_reference']


def claim(client, headers, index, ref, amount=1500):
    return post(client,f'/admin/api/orders/{code(index)}/proof',headers,
                {'test_reference':ref,'reported_amount_etb':amount,'currency':'ETB'})


def check(client, headers, index):
    return post(client,f'/admin/api/orders/{code(index)}/check',headers)


def confirm(client, headers, index):
    return post(client,f'/admin/api/orders/{code(index)}/confirm',headers,
                {'confirm_simulated_match':True})


def test_full_simulated_payment_audited(review_env):
    client, maker, headers = review_env
    ref=ledger(client,headers)
    assert claim(client,headers,0,ref).status_code==201
    mid=client.get('/admin/api/orders/'+code(0)).json()
    assert mid['order']['status']=='PROOF_SUBMITTED'
    assert mid['reviews'][0]['independent_check']=='NOT_CHECKED'
    matched=check(client,headers,0)
    assert matched.status_code==200 and matched.json()['independent_check']=='MATCHED'
    assert confirm(client,headers,0).status_code==200
    inspection=client.get('/admin/api/orders/'+code(0)).json()
    assert inspection['order']['status']=='VERIFIED_PAID'
    assert inspection['reviews'][0]['state']=='VERIFIED_PAID'
    assert [e['event'] for e in inspection['verification_history']]==[
        'fictional_proof_recorded','qa_ledger_match','qa_payment_verified']
    with maker() as db:
        credited=db.scalar(select(SimulatedLedgerEntry).where(SimulatedLedgerEntry.test_reference==ref))
        assert credited.credited_order_id==db.scalar(select(Order.id).where(Order.order_code==code(0)))
        assert len(db.scalars(select(PaymentEvent).where(PaymentEvent.order_id==credited.credited_order_id)).all())==3


def test_cannot_confirm_unchecked_claim_or_without_explicit_confirm(review_env):
    client,_,headers=review_env
    ref=ledger(client,headers)
    assert claim(client,headers,0,ref).status_code==201
    assert confirm(client,headers,0).status_code==409
    assert check(client,headers,0).status_code==200
    assert post(client,f'/admin/api/orders/{code(0)}/confirm',headers,
                {'confirm_simulated_match':False}).status_code==422
    assert confirm(client,headers,0).status_code==200
    assert confirm(client,headers,0).status_code==409


def test_wrong_amount_and_missing_ledger_fail(review_env):
    client,_,headers=review_env
    ref=ledger(client,headers,amount=1400)
    assert claim(client,headers,0,ref).status_code==201
    mismatch=check(client,headers,0)
    assert mismatch.status_code==200 and mismatch.json()['independent_check']=='DISCREPANCY'
    assert confirm(client,headers,0).status_code==409
    reject=post(client,f'/admin/api/orders/{code(0)}/reject',headers,
                {'reason':'Synthetic amount discrepancy'})
    assert reject.status_code==200 and reject.json()['status']=='PENDING_PAYMENT'
    newref='QA-TB-1234567890ABCDEF'
    assert claim(client,headers,0,newref).status_code==201
    assert check(client,headers,0).json()['independent_check']=='DISCREPANCY'
    assert confirm(client,headers,0).status_code==409


def test_wrong_reported_amount_fails_check(review_env):
    client,_,headers=review_env
    ref=ledger(client,headers)
    assert claim(client,headers,0,ref,1499).status_code==201
    assert check(client,headers,0).json()['independent_check']=='DISCREPANCY'
    assert confirm(client,headers,0).status_code==409


def test_duplicate_reference_cross_order_and_method_rejected(review_env):
    client,_,headers=review_env
    ref=ledger(client,headers)
    assert claim(client,headers,0,ref).status_code==201
    assert claim(client,headers,2,ref).status_code==409
    assert claim(client,headers,1,ref).status_code==422


def test_retry_after_rejection_preserves_history(review_env):
    client,_,headers=review_env
    bad=ledger(client,headers,amount=1400)
    assert claim(client,headers,0,bad).status_code==201
    assert check(client,headers,0).status_code==200
    assert post(client,f'/admin/api/orders/{code(0)}/reject',headers,
                {'reason':'QA ledger mismatch'}).status_code==200
    good=ledger(client,headers)
    assert claim(client,headers,0,good).status_code==201
    assert check(client,headers,0).status_code==200
    assert confirm(client,headers,0).status_code==200
    history=client.get('/admin/api/orders/'+code(0)).json()
    assert len(history['reviews'])==2
    assert len(history['verification_history'])==6
    assert history['reviews'][1]['state']=='REJECTED'


def test_cancel_is_terminal_and_cannot_touch_verified(review_env):
    client,_,headers=review_env
    r=post(client,f'/admin/api/orders/{code(3)}/cancel',headers,
           {'reason':'QA test cancellation'})
    assert r.status_code==200 and r.json()['status']=='CANCELLED'
    assert post(client,f'/admin/api/orders/{code(3)}/cancel',headers,
                {'reason':'Another cancellation'}).status_code==409
    ref=ledger(client,headers)
    assert claim(client,headers,0,ref).status_code==201
    assert check(client,headers,0).status_code==200
    assert confirm(client,headers,0).status_code==200
    assert post(client,f'/admin/api/orders/{code(0)}/cancel',headers,
                {'reason':'Not allowed after verification'}).status_code==409


def test_access_control_and_csrf(review_env):
    client,_,headers=review_env
    # Remove cookie for unauthenticated request without disturbing authenticated client.
    from fastapi.testclient import TestClient
    anonymous=TestClient(client.app,base_url=ORIGIN)
    assert anonymous.post('/admin/api/qa-ledger',json={'method':'bank','amount_etb':1500}).status_code==401
    assert anonymous.post('/admin/api/orders/'+code(0)+'/proof',json={}).status_code==422 # body validation before auth
    assert post(client,'/admin/api/qa-ledger',{'Origin':ORIGIN},{'method':'bank','amount_etb':1500}).status_code==403
    assert post(client,'/admin/api/qa-ledger',{'Origin':'https://evil.example','X-CSRF-Token':headers['X-CSRF-Token']},
                {'method':'bank','amount_etb':1500}).status_code==403
    assert post(client,'/admin/api/qa-ledger',headers,{'method':'bank','amount_etb':1500,'verified':True}).status_code==422


def test_no_real_refs_no_real_payments(review_env):
    client,_,headers=review_env
    assert claim(client,headers,0,'1234567890123456789012').status_code==422
    assert claim(client,headers,0,'QA-TB-XYZXYZXYZXYZXYZX').status_code==422
    for route in ('/api/v1/payments/verify','/admin/api/orders/'+code(0)+'/deliver',
                  '/admin/api/orders/'+code(0)+'/refund'):
        assert post(client,route,headers).status_code==404


def test_concurrent_verification_only_one_credits_on_pg(review_env):
    from os import getenv
    if not getenv('PW_TEST_POSTGRES_URL'):
        pytest.skip('Atomic race test requires PostgreSQL')
    client,maker,headers=review_env
    ref=ledger(client,headers)
    assert claim(client,headers,0,ref).status_code==201
    assert check(client,headers,0).status_code==200
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(lambda _:confirm(client,headers,0).status_code,range(5)))
    assert results.count(200)==1, results
    assert results.count(409)==4, results
    with maker() as db:
        row=db.scalar(select(SimulatedLedgerEntry).where(SimulatedLedgerEntry.test_reference==ref))
        assert row.credited_order_id is not None
        assert len(db.scalars(select(PaymentEvent).where(PaymentEvent.action=='qa_payment_verified')).all())==1


def test_immutable_audit_trigger_on_pg(review_env):
    from os import getenv
    if not getenv('PW_TEST_POSTGRES_URL'):
        pytest.skip('Trigger immutability test requires PostgreSQL')
    client,maker,headers=review_env
    ref=ledger(client,headers)
    assert claim(client,headers,0,ref).status_code==201
    # Disposable PostgreSQL's migrated public schema has the migration trigger.
    # Isolated synthetic schemas are created with metadata.create_all(), so check
    # the real Alembic DDL target without modifying founder/prod data.
    with maker() as db:
        exists=db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'qa_payment_events_append_only' AND tgrelid='public.qa_payment_events'::regclass)"))
        assert exists is True


def test_customer_summary_after_qa_verified(review_env, monkeypatch):
    monkeypatch.setenv('ORDER_TOKEN_KEY','fictitious-test-only-server-key-1234567890')
    from api.security import hash_value
    from fastapi.testclient import TestClient
    client,maker,headers=review_env
    ref=ledger(client,headers)
    assert claim(client,headers,0,ref).status_code==201
    assert check(client,headers,0).status_code==200
    assert confirm(client,headers,0).status_code==200
    token='f'*43
    with maker.begin() as db:
        row=db.scalar(select(Order).where(Order.order_code==code(0)))
        row.access_token_hash=hash_value(token)
    import api.main as main
    # Import only after authenticated mutation, because main registers its own
    # admin-session maker at module-import time in the same test interpreter.
    monkeypatch.setattr(main,'SessionLocal',maker)
    with TestClient(main.app) as web:
        response=web.get('/api/v1/orders/'+code(0),headers={'Authorization':'Bearer '+token})
        assert response.status_code==200
        summary=response.json()['order']
        assert summary['status']=='VERIFIED_PAID' and summary['test_mode'] is True
        assert summary['amount_etb']==1500
        assert web.get('/api/v1/orders/'+code(0)).status_code==404