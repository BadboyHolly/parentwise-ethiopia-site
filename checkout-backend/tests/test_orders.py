import importlib
import os
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from api.security import issue_idempotency_key


@pytest.fixture
def api(tmp_path, monkeypatch):
    dbfile = tmp_path / 'qa.db'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{dbfile}')
    monkeypatch.setenv('ORDER_TOKEN_KEY', 'test-only-secret-value-that-is-never-deployed-12345')
    monkeypatch.setenv('APP_MODE','qa')
    monkeypatch.setenv('PAYMENTS_ENABLED','false')
    monkeypatch.setenv('ALLOWED_ORIGINS','http://localhost:3000')
    monkeypatch.setenv('CREATE_RATE_LIMIT','100')
    ini = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    ini.set_main_option('script_location',str(Path(__file__).resolve().parents[1] / 'migrations'))
    command.upgrade(ini, 'head')
    import api.main as main
    main = importlib.reload(main)
    with TestClient(main.app) as client:
        yield client, str(dbfile), main
    main.engine.dispose()


def create(client, method='telebirr', key=None, **changes):
    data={'customer_name':'QA Test Parent','mobile':'0912345678','payment_method':method}
    data.update(changes)
    return client.post('/api/v1/orders',headers={'Idempotency-Key':key or issue_idempotency_key()},json=data)


def test_migration_and_postgresql_shape(api):
    client, file, main = api
    with main.engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM sqlite_master WHERE name='orders'")) == 1
        assert conn.scalar(text("SELECT count(*) FROM sqlite_master WHERE name='api_rate_windows'")) == 1


def test_create_persist_and_token_auth(api):
    client, file, main = api
    result=create(client)
    assert result.status_code==201, result.text
    order=result.json()['order']; token=result.json()['access_token']
    assert order['order_id'].startswith('PW-QA-')
    assert order['amount_etb']==1500 and order['currency']=='ETB'
    assert order['status']=='PENDING_PAYMENT' and order['test_mode'] is True
    assert 'mobile' not in str(result.json()) and 'customer_name' not in str(result.json())
    assert client.get('/api/v1/orders/'+order['order_id']).status_code==404
    authorized=client.get('/api/v1/orders/'+order['order_id'],headers={'Authorization':'Bearer '+token})
    assert authorized.status_code==200 and authorized.json()['order']==order
    with main.SessionLocal() as db:
        assert db.scalar(select(main.Order).where(main.Order.order_code==order['order_id'])).customer_name=='QA Test Parent'


def test_uniqueness_and_idempotent_retry(api):
    client,file,main=api
    key=issue_idempotency_key()
    a=create(client,key=key)
    b=create(client,key=key)
    assert a.status_code==201 and b.status_code==201
    assert a.json()==b.json()
    c=create(client)
    assert c.status_code==201 and c.json()['order']['order_id']!=a.json()['order']['order_id']
    with main.SessionLocal() as db:
        assert db.scalar(select(text('count(*)')).select_from(main.Order))==2


def test_conflicting_idempotency_returns_409(api):
    client,*_=api
    key=issue_idempotency_key()
    assert create(client,key=key).status_code==201
    assert create(client,key=key,method='bank').status_code==409

@pytest.mark.parametrize('changes',[
 {'customer_name':''}, {'customer_name':'  '}, {'mobile':'123'},
 {'mobile':'0812345678'}, {'mobile':'+251811111111'},
 {'payment_method':'cash'}, {'amount_etb':1}, {'status':'VERIFIED_PAID'},
])
def test_invalid_input_rejected(api,changes):
    client,*_=api
    assert create(client,**changes).status_code==422


def test_both_payment_methods_and_mobile_normalization(api):
    client,file,main=api
    x=create(client,method='bank',mobile='0712345678')
    assert x.status_code==201
    with main.SessionLocal() as db:
        row=db.scalar(select(main.Order).where(main.Order.order_code==x.json()['order']['order_id']))
        assert row.mobile_e164=='+251712345678' and row.payment_method=='bank'


def test_no_cross_customer_token_access(api):
    client,*_=api
    a=create(client).json(); b=create(client).json()
    x=client.get('/api/v1/orders/'+a['order']['order_id'],headers={'Authorization':'Bearer '+b['access_token']})
    assert x.status_code==404
    assert client.get('/api/v1/orders/PW-QA-AAAAAAAAAAAA').status_code==404


def test_restart_persistence_same_file(api):
    client,path,main=api
    record=create(client).json()
    main.engine.dispose()
    # Reinstantiate the API/database engine as a fresh process would.
    second=importlib.reload(main)
    with TestClient(second.app) as restarted:
        got=restarted.get('/api/v1/orders/'+record['order']['order_id'], headers={'Authorization':'Bearer '+record['access_token']})
        assert got.status_code==200
        assert got.json()['order']['order_id']==record['order']['order_id']
    second.engine.dispose()


def test_database_error_is_safe(api):
    client,path,main=api
    with main.engine.begin() as conn:
        conn.execute(text('DROP TABLE orders'))
    r=create(client)
    assert r.status_code==503
    assert 'Order storage is temporarily unavailable' in r.json()['detail']
    assert 'sqlite' not in r.text.lower() and 'select' not in r.text.lower()


def test_no_payment_routes_and_health(api):
    client,*_=api
    assert client.get('/healthz').json()['payments_enabled'] is False
    assert client.get('/readyz').status_code==200
    assert client.post('/api/v1/payments/verify').status_code==404
    assert client.get('/api/v1/orders').status_code==405


def test_rate_limit(api,monkeypatch):
    client,path,main=api
    monkeypatch.setenv('CREATE_RATE_LIMIT','2')
    assert create(client).status_code==201
    assert create(client).status_code==201
    assert create(client).status_code==429


def test_invalid_idempotency_key(api):
    client,*_=api
    assert create(client,key='aaa').status_code==400


def test_concurrent_same_idempotency_key_creates_one_order(api):
    from concurrent.futures import ThreadPoolExecutor
    client, _, main = api
    key = issue_idempotency_key()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: create(client, key=key), range(4)))
    assert [r.status_code for r in results] == [201] * 4, [(r.status_code, r.text[:160]) for r in results]
    ids = {r.json()['order']['order_id'] for r in results}
    assert len(ids) == 1
    with main.SessionLocal() as db:
        assert db.scalar(select(text('count(*)')).select_from(main.Order)) == 1


def test_bearer_secret_not_leaked_in_persistence(api):
    client, _, main = api
    key=issue_idempotency_key()
    result=create(client,key=key).json()
    with main.SessionLocal() as db:
        row = db.scalar(select(main.Order).where(main.Order.order_code==result['order']['order_id']))
        assert result['access_token'] != row.access_token_hash
        assert key not in (str(row.idempotency_hash), str(row.access_token_hash))


def test_qa_mode_rejects_payments_activation(api, monkeypatch):
    _, _, main = api
    monkeypatch.setenv('PAYMENTS_ENABLED', 'true')
    with pytest.raises(RuntimeError, match='payment collection is disabled'):
        importlib.reload(main)

def test_qa_global_quota_unaffected_by_spoofed_forwarded_headers(api, monkeypatch):
    client, path, main = api
    monkeypatch.setenv('CREATE_RATE_LIMIT', '3')
    versions = [
        {},
        {'X-Forwarded-For': '198.51.100.11'},
        {'X-Forwarded-For': '192.0.2.1, 203.0.113.8', 'CF-Connecting-IP': '192.0.2.44'},
        {'Forwarded': 'for=198.51.100.55'},
        {'X-Forwarded-For': '10.0.0.1'},
    ]
    codes = [
        client.post('/api/v1/orders',
                    headers={'Idempotency-Key':issue_idempotency_key(), **h},
                    json={'customer_name':'QA Test Parent','mobile':'0912345678','payment_method':'telebirr'}).status_code
        for h in versions
    ]
    assert codes == [201, 201, 201, 429, 429], codes


def test_idempotent_retry_survives_exhausted_qa_quota(api, monkeypatch):
    client, _, main = api
    monkeypatch.setenv('CREATE_RATE_LIMIT', '2')
    key = issue_idempotency_key()
    first = create(client, key=key)
    second = create(client)
    blocked = create(client)
    retry = create(client, key=key)
    assert [first.status_code, second.status_code, blocked.status_code, retry.status_code] == [201, 201, 429, 201]
    assert first.json() == retry.json()


def test_concurrent_distinct_new_orders_respect_qa_global_limit(api, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    client, _, main = api
    monkeypatch.setenv('CREATE_RATE_LIMIT', '3')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: create(client), range(8)))
    codes = [r.status_code for r in results]
    assert codes.count(201) == 3, codes
    assert codes.count(429) == 5, codes
    with main.SessionLocal() as db:
        assert db.scalar(select(text('count(*)')).select_from(main.Order)) == 3
