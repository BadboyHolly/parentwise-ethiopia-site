"""PostgreSQL-only QA rate-limit regressions (never production).

Run: QA_PG_TESTS=1 APP_MODE=qa PAYMENTS_ENABLED=false pytest -q tests/test_rate_postgres.py
DATABASE_URL must point to a QA PostgreSQL database. Each test uses a unique
rate-window key; cleanup deletes only its own keys, not customer orders.
"""
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from api.models import RateWindow
from api.rate_limit import reserve_attempt, bucket_for_qa


@pytest.fixture
def pg_bucket():
    if (os.getenv('QA_PG_TESTS') != '1' or os.getenv('APP_MODE') != 'qa'
            or os.getenv('PAYMENTS_ENABLED', 'false') != 'false'):
        pytest.skip('Explicit QA-only PostgreSQL test opt-in required')
    url = os.getenv('DATABASE_URL', '')
    if url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url[len('postgres://'):]
    elif url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    if not url.startswith('postgresql+psycopg://'):
        pytest.skip('PostgreSQL connection unavailable')
    engine = create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 5})
    maker = sessionmaker(engine)
    key = sha256(('qa-pg-rate-' + secrets.token_hex(20)).encode()).hexdigest()
    try:
        yield maker, key
    finally:
        with maker.begin() as db:
            db.execute(delete(RateWindow).where(RateWindow.key == key))
        engine.dispose()


def attempt(maker, key, limit=3, now=None):
    with maker() as db:
        try:
            reserve_attempt(db, bucket=key, limit=limit, now=now)
            return 201
        except HTTPException as exc:
            return exc.status_code


def test_postgres_denials_never_reopen_unexpired_bucket(pg_bucket):
    maker, key = pg_bucket
    assert [attempt(maker, key) for _ in range(8)] == [201, 201, 201, 429, 429, 429, 429, 429]
    with maker() as db:
        assert db.scalar(select(RateWindow.count).where(RateWindow.key == key)) == 3


def test_postgres_concurrent_insert_upsert_atomic(pg_bucket):
    maker, key = pg_bucket
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: attempt(maker, key), range(12)))
    assert results.count(201) == 3, results
    assert results.count(429) == 9, results
    with maker() as db:
        assert db.scalar(select(RateWindow.count).where(RateWindow.key == key)) == 3


def test_postgres_expired_window_resets(pg_bucket):
    maker, key = pg_bucket
    when = datetime.now(timezone.utc)
    assert attempt(maker, key, 1, when) == 201
    assert attempt(maker, key, 1, when + timedelta(seconds=5)) == 429
    assert attempt(maker, key, 1, when + timedelta(minutes=11)) == 201


def test_proxy_and_forged_forwarding_headers_cannot_change_qa_bucket(pg_bucket):
    # Request identity is not used in QA rate limiting. This also ensures
    # deliberately forged XFF/CF headers never enter its bucket function.
    maker, key = pg_bucket
    headers = [
        {},
        {'X-Forwarded-For': '198.51.100.77'},
        {'X-Forwarded-For': '203.0.113.22, 192.0.2.31'},
        {'CF-Connecting-IP': '192.0.2.88'},
        {'Forwarded': 'for=203.0.113.44'},
    ]
    assert len({bucket_for_qa('static-qa-secret') for _ in headers}) == 1
    assert [attempt(maker, key, limit=2) for _ in headers] == [201, 201, 429, 429, 429]
