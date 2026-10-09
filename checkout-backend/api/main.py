"""Portable test-mode order API. No real payments, operator mutations or file delivery."""
import json
import os
from typing import Literal
import logging

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .db import get_database_url, make_sessionmaker
from .models import Order
from .rate_limit import reserve_attempt, bucket_for_qa, run_postgres_qa_selfcheck
from .security import equal_hash, hash_value, keyed_token, order_code, order_id, validate_idempotency_key

APP_MODE = os.getenv('APP_MODE', 'qa')
if APP_MODE != 'qa' or os.getenv('PAYMENTS_ENABLED', 'false').lower() != 'false':
    raise RuntimeError('This API is QA-only; payment collection is disabled')

SECRET = os.getenv('ORDER_TOKEN_KEY', '')
if len(SECRET) < 32:
    raise RuntimeError('ORDER_TOKEN_KEY must contain at least 32 secret characters')

DATABASE_URL = get_database_url()
engine, SessionLocal = make_sessionmaker(DATABASE_URL)

ALLOWED_ORIGINS = [x.strip() for x in os.getenv('ALLOWED_ORIGINS', 'https://parentwise-ethiopia-qa.onrender.com').split(',') if x.strip()]
if any(x == '*' or not (x.startswith('https://') or x.startswith('http://localhost:')) for x in ALLOWED_ORIGINS):
    raise RuntimeError('Explicit secure CORS origins are required')

app = FastAPI(title='ParentWise QA Orders', docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=['GET','POST'], allow_headers=['Content-Type','Authorization','Idempotency-Key'], allow_credentials=False)

@app.middleware('http')
async def response_protection(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


class CreateOrder(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    customer_name: str = Field(min_length=2, max_length=100)
    mobile: str = Field(min_length=10, max_length=13)
    payment_method: Literal['telebirr', 'bank']

    @field_validator('customer_name')
    @classmethod
    def clean_name(cls, value):
        if not any(x.isalpha() for x in value) or any(ord(x) < 32 for x in value):
            raise ValueError('Enter a valid customer name')
        return value

    @field_validator('mobile')
    @classmethod
    def normalize_phone(cls, value):
        # Ethiopian mobile prefixes 09 and 07, or equivalent +251, 10 digits total nationally.
        if len(value) == 10 and value[:2] in ('09', '07') and value.isascii() and value.isdigit():
            return '+251' + value[1:]
        if len(value) == 13 and value.startswith(('+2519', '+2517')) and value[1:].isascii() and value[1:].isdigit():
            return value
        raise ValueError('Use a valid Ethiopian mobile number: 09..., 07..., or +251...')


def public_summary(order: Order):
    return {'order_id': order.order_code, 'product': 'ParentWise Child Behavior & Discipline System',
            'amount_etb': order.amount_etb, 'currency': order.currency,
            'payment_method': order.payment_method, 'status': order.status,
            'test_mode': True, 'created_at': order.created_at.isoformat() if order.created_at else None}


def fingerprint(item: CreateOrder) -> str:
    return hash_value(json.dumps(item.model_dump(), sort_keys=True, separators=(',', ':')))


def apply_rate_limit(db, req: Request, *, atomic_with_order=False):
    # QA-only conservative global rate limit. Render proxy IPs may rotate and
    # unsanitized forwarded headers are potentially spoofable; no request
    # headers or socket addresses participate in this quota's identity.
    reserve_attempt(db, bucket=bucket_for_qa(SECRET),
                    limit=int(os.getenv('CREATE_RATE_LIMIT', '12')), commit=not atomic_with_order)


@app.on_event('startup')
def optional_qa_postgres_rate_selfcheck():
    # Opt-in diagnostic on the existing QA database. Uses unique temporary
    # rate-limit records, never creates orders, and cleans up on completion.
    if os.getenv('QA_RATE_SELFTEST', 'false').lower() == 'true':
        result = run_postgres_qa_selfcheck(SessionLocal)
        logging.getLogger('uvicorn.error').info('QA PostgreSQL rate-limit checks: %s', result)


@app.get('/healthz')
def health():
    return {'service': 'parentwise-qa-orders', 'mode': 'test', 'payments_enabled': False}


@app.get('/readyz')
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'database': 'ready', 'test_mode': True}
    except SQLAlchemyError:
        raise HTTPException(503, 'Order storage is temporarily unavailable') from None


@app.post('/api/v1/orders', status_code=201)
def create_order(item: CreateOrder, request: Request, idempotency_key: str = Header(..., alias='Idempotency-Key')):
    try:
        validate_idempotency_key(idempotency_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    key_hash = hash_value('idempotency:' + idempotency_key)
    token = keyed_token(SECRET, idempotency_key)
    digest = fingerprint(item)
    try:
        with SessionLocal() as db:
            if db.bind.dialect.name == 'postgresql':
                # Serialize identical idempotency keys *before* the initial lookup.
                # The transaction-scoped advisory lock survives through the
                # rate reservation and order INSERT; released by final COMMIT.
                advisory_key = int.from_bytes(bytes.fromhex(key_hash)[:8], 'big', signed=True)
                db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': advisory_key})
            existing = db.execute(select(Order).where(Order.idempotency_hash == key_hash)).scalar_one_or_none()
            if existing:
                if existing.request_fingerprint != digest:
                    raise HTTPException(409, 'Idempotency key already used for a different order')
                return {'order': public_summary(existing), 'access_token': token}
            # PostgreSQL commits quota and order in one transaction. Thus
            # failed creations do not permanently consume quota and retries
            # cannot interleave between an initial lookup and reservation.
            apply_rate_limit(db, request, atomic_with_order=db.bind.dialect.name == 'postgresql')
            order = Order(id=order_id(), order_code=order_code(), customer_name=item.customer_name,
                          mobile_e164=item.mobile, payment_method=item.payment_method,
                          amount_etb=1500, currency='ETB', status='PENDING_PAYMENT',
                          idempotency_hash=key_hash, request_fingerprint=digest,
                          access_token_hash=hash_value(token))
            db.add(order)
            try:
                db.commit()
                db.refresh(order)
            except IntegrityError:
                db.rollback()
                # Collision handling without leaking SQL details.
                existing = db.execute(select(Order).where(Order.idempotency_hash == key_hash)).scalar_one_or_none()
                if existing:
                    if existing.request_fingerprint != digest:
                        raise HTTPException(409, 'Idempotency key already used for a different order')
                    return {'order': public_summary(existing), 'access_token': token}
                raise HTTPException(503, 'Could not create the test order; try again') from None
            return {'order': public_summary(order), 'access_token': token}
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, 'Order storage is temporarily unavailable. Your payment was not taken.') from None


@app.get('/api/v1/orders/{order_code}')
def retrieve_order(order_code: str, authorization: str = Header(default='')):
    # Order IDs alone confer no access. Access token is a separate 256-bit secret.
    if not authorization.startswith('Bearer '):
        raise HTTPException(404, 'Order not found or access denied')
    token = authorization[7:]
    if len(token) != 43:
        raise HTTPException(404, 'Order not found or access denied')
    try:
        with SessionLocal() as db:
            row = db.execute(select(Order).where(Order.order_code == order_code)).scalar_one_or_none()
            if not row or not equal_hash(row.access_token_hash, hash_value(token)):
                raise HTTPException(404, 'Order not found or access denied')
            return {'order': public_summary(row)}
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(503, 'Order storage is temporarily unavailable') from None