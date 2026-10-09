"""QA-only PostgreSQL-backed global order-creation limiter.

Peer addresses can vary behind reverse proxies. QA uses one conservative
shared bucket: independent of forwarded headers and socket addresses.
Not suitable for public production traffic because one client can exhaust
the quota for everyone.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .models import RateWindow

WINDOW = timedelta(minutes=10)


def bucket_for_qa(secret: str) -> str:
    return sha256((secret + ':qa-global-order-create:v3').encode()).hexdigest()


def reserve_attempt(db, *, bucket: str, limit: int, now=None, commit=True):
    """Atomically consume a 10-minute quota slot in SQL."""
    if not (1 <= limit <= 10000):
        raise RuntimeError('Invalid QA creation limit')
    now = now or datetime.now(timezone.utc)
    expiry = now + WINDOW
    dialect = db.bind.dialect.name
    if dialect == 'postgresql':
        statement = pg_insert(RateWindow).values(key=bucket, count=1, expires_at=expiry)
    elif dialect == 'sqlite':  # disposable test databases only
        statement = sqlite_insert(RateWindow).values(key=bucket, count=1, expires_at=expiry)
    else:
        raise RuntimeError('Unsupported rate-limit database')
    statement = statement.on_conflict_do_update(
        index_elements=[RateWindow.key],
        set_={
            'count': case((RateWindow.expires_at <= now, 1), else_=RateWindow.count + 1),
            'expires_at': case((RateWindow.expires_at <= now, expiry), else_=RateWindow.expires_at),
        },
    ).returning(RateWindow.count)
    count = db.execute(statement).scalar_one()
    if count > limit:
        db.rollback()
        raise HTTPException(429, 'Too many QA test orders in this 10-minute window. Try again later.')
    if commit:
        db.commit()
    return count


def run_postgres_qa_selfcheck(sessionmaker):
    """Opt-in startup check using only temporary QA rate-limit keys.

    Runs real PostgreSQL sequential/concurrent writes, then cleans its own rows.
    No customer records are generated and no credentials are logged.
    """
    if sessionmaker.kw.get('bind').dialect.name != 'postgresql':
        raise RuntimeError('QA PostgreSQL selfcheck requires PostgreSQL')
    prefix = 'qa-selfcheck-' + uuid4().hex
    keys = [sha256((prefix + str(i)).encode()).hexdigest() for i in range(2)]
    try:
        results = []
        for _ in range(5):
            with sessionmaker() as db:
                try:
                    reserve_attempt(db, bucket=keys[0], limit=3)
                    results.append(201)
                except HTTPException as exc:
                    results.append(exc.status_code)
        assert results == [201, 201, 201, 429, 429], results

        def hit(_):
            with sessionmaker() as db:
                try:
                    reserve_attempt(db, bucket=keys[1], limit=3)
                    return 201
                except HTTPException as exc:
                    return exc.status_code

        with ThreadPoolExecutor(max_workers=8) as pool:
            concurrent = list(pool.map(hit, range(8)))
        assert concurrent.count(201) == 3 and concurrent.count(429) == 5, concurrent
        with sessionmaker() as db:
            count = db.scalar(select(RateWindow.count).where(RateWindow.key == keys[1]))
            assert count == 3, count
        return 'PASS sequential=3/2 concurrent=3/5 persisted_count=3'
    finally:
        with sessionmaker.begin() as db:
            db.execute(delete(RateWindow).where(RateWindow.key.in_(keys)))
