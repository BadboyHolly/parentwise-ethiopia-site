"""Phase 5 QA dummy fulfillment integration; disposable founder + PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
import os, secrets
import pytest
from sqlalchemy import select, text
from fastapi.testclient import TestClient
from api import fulfillment
from api.models import Order, QaFulfillment, QaFulfillmentEvent
from test_payment_review import review_env, ledger, claim, check, confirm, code, post, ORIGIN
from test_admin import system  # expose dependent isolated founder fixture to pytest

@pytest.fixture
def env(review_env):
    client,maker,headers=review_env
    fulfillment.mount_fulfillment(client.app,maker)
    yield client,maker,headers

def eligible(env,index=0):
    client,_,h=env
    ref=ledger(client,h)
    assert claim(client,h,index,ref).status_code==201
    assert check(client,h,index).json()['independent_check']=='MATCHED'
    result=confirm(client,h,index)
    assert result.status_code==200,result.text

def action(env,index,name,payload):
    client,_,h=env
    return post(client,'/admin/api/orders/'+code(index)+'/fulfillment/'+name,h,payload)

def yes():return {'confirm_qa_action':True}
def dispatch():return {'confirm_qa_action':True,'dummy_document_checked':True}
def receipt(ref='QA-ACK-0123456789ABCDEF'):
    return {'confirm_qa_action':True,'source':'QA_SIMULATED_CUSTOMER_ACK','qa_ack_reference':ref}

def test_verified_payment_registers_versioned_dummy_queue_only(env):
    client,maker,h=env
    pre=client.get('/admin/api/fulfillment/queue')
    assert pre.status_code==200 and pre.json()['total']==0
    assert action(env,0,'prepare',yes()).status_code==409
    eligible(env,0)
    q=client.get('/admin/api/fulfillment/queue').json()
    assert q['total']==1 and q['simulated_only'] is True
    f=q['items'][0]
    assert f['order_id']==code(0)
    assert f['status']=='PENDING_FULFILLMENT'
    assert f['package_version']=='QA-DEMO-2026.10-v1'
    assert f['attempt_count']==0 and f['real_files_sent'] is False
    assert client.get('/admin/api/fulfillment/queue?state=PREPARING').json()['total']==0
    inspected=client.get('/admin/api/orders/'+code(0)).json()
    assert inspected['fulfillment']['status']=='PENDING_FULFILLMENT'
    assert len(inspected['fulfillment_events'])==1
    with maker() as db:
        assert db.scalar(select(QaFulfillment).where(QaFulfillment.order_id== '0')).qa_review_id

def test_prepare_dispatch_explicit_receipt_and_immutable_event_history(env):
    client,maker,h=env
    eligible(env)
    assert action(env,0,'dispatch',dispatch()).status_code==409
    assert action(env,0,'prepare',{'confirm_qa_action':False}).status_code==422
    assert action(env,0,'prepare',yes()).status_code==200
    assert action(env,0,'prepare',yes()).status_code==409
    assert action(env,0,'dispatch',{'confirm_qa_action':True,'dummy_document_checked':False}).status_code==422
    d=action(env,0,'dispatch',dispatch())
    assert d.status_code==200 and d.json()['fulfillment']['status']=='SENT'
    assert d.json()['fulfillment']['attempt_count']==1
    assert action(env,0,'dispatch',dispatch()).status_code==409
    assert action(env,0,'receipt',{'confirm_qa_action':True,'source':'QA_SIMULATED_CUSTOMER_ACK'}).status_code==422
    assert action(env,0,'receipt',receipt('real-telegram-confirmation')).status_code==422
    result=action(env,0,'receipt',receipt())
    assert result.status_code==200 and result.json()['fulfillment']['status']=='DELIVERED'
    assert result.json()['fulfillment']['simulated_only'] is True
    assert action(env,0,'receipt',receipt()).status_code==409
    assert action(env,0,'failure',{'reason':'Try again'}).status_code==409
    detail=client.get('/admin/api/orders/'+code(0)+'/fulfillment').json()
    assert [x['action'] for x in detail['fulfillment_events']]==[
        'qa_dummy_fulfillment_enrolled','qa_dummy_preparation',
        'qa_dummy_dispatch_record','qa_dummy_receipt_attested']
    with maker() as db:
        assert len(db.scalars(select(QaFulfillmentEvent)).all())==4

def test_failed_delivery_retry_and_resend_once(env):
    eligible(env)
    assert action(env,0,'prepare',yes()).status_code==200
    assert action(env,0,'failure',{'reason':'Simulated unsupported device'}).status_code==200
    assert action(env,0,'failure',{'reason':'Simulated unsupported device'}).status_code==409
    assert action(env,0,'retry',{'reason':'Dummy retry requested'}).status_code==200
    assert action(env,0,'dispatch',dispatch()).status_code==200
    assert action(env,0,'failure',{'reason':'Simulated receiving failure'}).status_code==200
    assert action(env,0,'retry',{'reason':'Simulated new dummy attempt'}).status_code==200
    sent=action(env,0,'dispatch',dispatch())
    assert sent.status_code==200 and sent.json()['fulfillment']['attempt_count']==2
    assert action(env,0,'receipt',receipt()).status_code==200

def test_missing_matched_payment_and_unsafe_routes(env):
    client,_,h=env
    assert action(env,0,'prepare',yes()).status_code==409
    ref=ledger(client,h,amount=1400)
    assert claim(client,h,0,ref).status_code==201
    assert check(client,h,0).json()['independent_check']=='DISCREPANCY'
    assert action(env,0,'prepare',yes()).status_code==409
    assert client.get('/admin/api/fulfillment/queue').json()['total']==0
    anonymous=TestClient(client.app,base_url=ORIGIN)
    assert anonymous.get('/admin/api/fulfillment/queue').status_code==401
    assert anonymous.get('/admin/api/orders/'+code(0)+'/fulfillment').status_code==401
    assert anonymous.get('/admin/api/fulfillment/dummy-document').status_code==401
    assert anonymous.post('/admin/api/orders/'+code(0)+'/fulfillment/prepare',
                          json=yes(),headers={'Origin':ORIGIN}).status_code==401
    assert action(env,0,'prepare',yes()).status_code==409
    assert post(client,'/admin/api/orders/'+code(0)+'/fulfillment/prepare',
                {'Origin':ORIGIN},yes()).status_code==403
    assert post(client,'/admin/api/orders/'+code(0)+'/fulfillment/prepare',
                {'Origin':'https://attacker.invalid','X-CSRF-Token':h['X-CSRF-Token']},yes()).status_code==403

def test_fictional_ack_unique_between_orders(env):
    eligible(env,0);eligible(env,2)
    for i in (0,2):
        assert action(env,i,'prepare',yes()).status_code==200
        assert action(env,i,'dispatch',dispatch()).status_code==200
    assert action(env,0,'receipt',receipt()).status_code==200
    assert action(env,2,'receipt',receipt()).status_code==409
    assert action(env,2,'receipt',receipt('QA-ACK-FFEEDDCCBBAA0011')).status_code==200

def test_double_click_concurrency_serialized_by_row_locks(env):
    if not os.getenv('PW_TEST_POSTGRES_URL'):
        pytest.skip('PostgreSQL row locking required')
    eligible(env)
    client,_,h=env
    p='/admin/api/orders/'+code(0)+'/fulfillment/prepare'
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _: post(client,p,h,yes()).status_code,range(4)))
    assert responses.count(200)==1,responses
    assert responses.count(409)==3,responses
    p='/admin/api/orders/'+code(0)+'/fulfillment/dispatch'
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _: post(client,p,h,dispatch()).status_code,range(4)))
    assert responses.count(200)==1,responses
    assert responses.count(409)==3,responses
    q=client.get('/admin/api/orders/'+code(0)+'/fulfillment').json()
    assert q['fulfillment']['attempt_count']==1
    assert [x['action'] for x in q['fulfillment_events']].count('qa_dummy_dispatch_record')==1

def test_customer_token_recovery_contains_only_simulated_status(env,monkeypatch):
    eligible(env)
    client,maker,_=env
    from api.security import hash_value
    monkeypatch.setenv('ORDER_TOKEN_KEY','CI-dummy-token-key-only-never-production-123456789')
    from api import main
    token='x'*43
    with maker.begin() as db:
        order=db.scalar(select(Order).where(Order.order_code==code(0)))
        order.access_token_hash=hash_value(token)
    monkeypatch.setattr(main,'SessionLocal',maker)
    # Importing the full app also mounts admin and replaces its global session
    # maker. Restore this test's isolated founder fixture before mutations.
    from api import admin as admin_module
    monkeypatch.setattr(admin_module,'_SESSION_MAKER',maker)
    monkeypatch.setattr(fulfillment,'_MAKER',maker)
    with TestClient(main.app) as public:
        def get():
            return public.get('/api/v1/orders/'+code(0),headers={'Authorization':'Bearer '+token})
        first=get()
        assert first.status_code==200
        assert first.json()['order']['fulfillment']['status']=='PENDING_FULFILLMENT'
        assert action(env,0,'prepare',yes()).status_code==200
        assert action(env,0,'dispatch',dispatch()).status_code==200
        next_result=get()
        assert next_result.status_code==200
        f=next_result.json()['order']['fulfillment']
        assert f['status']=='SENT' and f['real_files_sent'] is False
        assert f['package_version']=='QA-DEMO-2026.10-v1'
        assert set(f)=={'status','package_version','channel','simulated_only',
                        'real_files_sent','support','message'}
        assert set(next_result.json()['order'])=={'order_id','product','amount_etb',
            'currency','payment_method','status','test_mode','created_at','fulfillment'}
        assert 'qa_ack_reference' not in str(next_result.json())
        assert 'customer_name' not in str(next_result.json())
        assert public.get('/api/v1/orders/'+code(0)).status_code==404

def test_pg_audit_trigger_and_dummy_asset_auth(env):
    client,maker,_=env
    resp=client.get('/admin/api/fulfillment/dummy-document')
    assert resp.status_code==200
    assert 'FICTIONAL' in resp.text and 'NOT a paid' in resp.text
    assert 'attachment' in resp.headers['content-disposition']
    if maker.kw['bind'].dialect.name=='postgresql':
        with maker() as db:
            enabled=db.scalar(text("""SELECT EXISTS (
              SELECT 1 FROM pg_trigger WHERE tgname='qa_fulfillment_events_append_only'
              AND tgrelid='public.qa_fulfillment_events'::regclass)"""))
        assert enabled is True
