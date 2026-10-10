"""Server-authorized founder-only QA administration.

Admin frontend and API use the same HTTPS origin. No public registration, real money handling, customer evidence uploads or paid product downloads.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4
import os

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .admin_security import (COOKIE_NAME, SESSION_ABSOLUTE_SECONDS, SESSION_IDLE_SECONDS,
    MAX_LOGIN_PER_WINDOW, config, verified_password, accepted_totp_step,
    new_session_token, hashed_token, csrf_token, check_origin, check_csrf,
    agent_fingerprint)
from .models import Order, AdminSession, AdminAudit, AdminTotpState
from .rate_limit import reserve_attempt
from .payment_review import inspection
from .fulfillment import inspection as fulfillment_inspection

router = APIRouter()
_SESSION_MAKER = None
_LOGIN_BUCKET = hashed_token('parentwise-qa-single-founder-login-v1')


class LoginInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=512)
    totp_code: str = Field(min_length=6, max_length=6)


def now_utc():
    return datetime.now(timezone.utc)


def utc(d):
    return d.replace(tzinfo=timezone.utc) if d is not None and d.tzinfo is None else d


def audit(db: Session, event: str, success: bool, *, order_code=None):
    db.add(AdminAudit(event=event, success=success, order_code=order_code))


def require_session(request: Request, db: Session):
    cfg = config()  # fail closed before credential provisioning
    raw = request.cookies.get(COOKIE_NAME, '')
    if len(raw) != 43:
        raise HTTPException(401, 'Founder sign-in required')
    row = db.get(AdminSession, hashed_token(raw))
    now = now_utc()
    if (row is None or row.revoked_at is not None or row.credentials_version != cfg.version
            or utc(row.expires_at) <= now
            or utc(row.last_seen_at) + timedelta(seconds=SESSION_IDLE_SECONDS) <= now
            or row.user_agent_hash != agent_fingerprint(request)):
        if row is not None and row.revoked_at is None:
            row.revoked_at = now
            audit(db, 'session_rejected', False)
            db.commit()
        raise HTTPException(401, 'Founder session expired. Sign in again')
    # Sliding inactivity expiry with hard absolute maximum.
    row.last_seen_at = now
    db.commit()
    return raw, row, cfg


def session_database():
    if _SESSION_MAKER is None:
        raise HTTPException(503, 'Administrative service unavailable')
    return _SESSION_MAKER()


@router.get('/admin', response_class=HTMLResponse)
def admin_page():
    config()
    # No customer records in this file; every API endpoint is separately protected.
    template = Path(__file__).resolve().parent / 'admin-ui.html'
    return HTMLResponse(template.read_text(encoding='utf8'), headers={
        'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; "
                                   "connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
                                   "form-action 'self'", 'Referrer-Policy': 'no-referrer'
    })


@router.get('/admin/ui.js')
def admin_script():
    config()
    from fastapi.responses import Response as FastResponse
    script = (Path(__file__).resolve().parent / 'admin-ui.js').read_text(encoding='utf8')
    return FastResponse(script, media_type='text/javascript', headers={'Cache-Control': 'no-store'})


@router.post('/admin/api/login')
def login(payload: LoginInput, request: Request, response: Response):
    cfg = config()
    check_origin(request, cfg)
    with session_database() as db:
        try:
            reserve_attempt(db, bucket=_LOGIN_BUCKET, limit=MAX_LOGIN_PER_WINDOW)
        except HTTPException as exc:
            if exc.status_code == 429:
                # Denials are indistinguishable for any submitted username.
                raise HTTPException(429, 'Too many sign-in attempts. Wait 10 minutes') from None
            raise
        # Check password even with incorrect username for consistent execution.
        password_ok = verified_password(payload.password, cfg.password_hash)
        username_ok = payload.username == cfg.username
        totp_ok = False
        if password_ok and username_ok:
            state = db.get(AdminTotpState, 1, with_for_update=True)
            if state is None:
                raise HTTPException(503, 'Founder authentication state is unavailable')
            step = accepted_totp_step(cfg.totp_secret, payload.totp_code, state.last_accepted_step)
            if step is not None:
                state.last_accepted_step = step
                totp_ok = True
        if not (password_ok and username_ok and totp_ok):
            audit(db, 'login_failed', False)
            db.commit()
            raise HTTPException(401, 'Invalid founder credentials')

        # New 256-bit session ID on EVERY successful login, fixing session ID fixation.
        raw = new_session_token()
        created = now_utc()
        db.add(AdminSession(session_hash=hashed_token(raw), credentials_version=cfg.version,
                            user_agent_hash=agent_fingerprint(request), created_at=created,
                            last_seen_at=created, expires_at=created + timedelta(seconds=SESSION_ABSOLUTE_SECONDS)))
        audit(db, 'login_success', True)
        db.commit()
        response.set_cookie(key=COOKIE_NAME, value=raw, secure=True, httponly=True,
                            samesite='strict', path='/', max_age=SESSION_ABSOLUTE_SECONDS)
        return {'authenticated': True, 'csrf': csrf_token(raw, cfg.version),
                'username': cfg.username, 'expires_at': (created + timedelta(seconds=SESSION_ABSOLUTE_SECONDS)).isoformat()}


@router.get('/admin/api/session')
def session_info(request: Request):
    with session_database() as db:
        raw, row, cfg = require_session(request, db)
        return {'authenticated': True, 'username': cfg.username,
                'csrf': csrf_token(raw, cfg.version),
                'expires_at': utc(row.expires_at).isoformat(), 'test_mode': True}


@router.post('/admin/api/logout')
def logout(request: Request, response: Response):
    cfg = config()
    check_origin(request, cfg)
    with session_database() as db:
        raw, row, _ = require_session(request, db)
        check_csrf(request, raw, cfg)
        row.revoked_at = now_utc()
        audit(db, 'logout', True)
        db.commit()
        response.delete_cookie(COOKIE_NAME, path='/', secure=True, httponly=True, samesite='strict')
        return {'authenticated': False}


def order_detail(o: Order):
    return {'order_id': o.order_code, 'name': o.customer_name,
            'mobile': o.mobile_e164, 'amount_etb': o.amount_etb, 'currency': o.currency,
            'method': o.payment_method, 'status': o.status,
            'created_at': utc(o.created_at).isoformat(), 'updated_at': utc(o.updated_at).isoformat()}


@router.get('/admin/api/overview')
def overview(request: Request):
    with session_database() as db:
        require_session(request, db)
        total = db.scalar(select(func.count()).select_from(Order)) or 0
        pending = db.scalar(select(func.count()).select_from(Order).where(Order.status == 'PENDING_PAYMENT')) or 0
        method_counts = {name: count for name, count in db.execute(
            select(Order.payment_method, func.count()).group_by(Order.payment_method)).all()}
        recent = db.scalars(select(Order).order_by(Order.created_at.desc(), Order.id.desc()).limit(6)).all()
        audit(db, 'overview_view', True)
        db.commit()
        return {'test_mode': True, 'total': total, 'pending': pending,
                'methods': {'telebirr': method_counts.get('telebirr', 0), 'bank': method_counts.get('bank', 0)},
                'recent': [order_detail(o) for o in recent]}


Status = Literal['PENDING_PAYMENT', 'PROOF_SUBMITTED', 'VERIFYING', 'VERIFIED_PAID', 'DELIVERED', 'CANCELLED', 'EXPIRED', 'REFUNDED']
Method = Literal['telebirr', 'bank']


@router.get('/admin/api/orders')
def list_orders(request: Request, page: int = Query(1, ge=1, le=5000),
                page_size: int = Query(15, ge=1, le=50),
                order_id: str = Query('', max_length=40),
                status: Status | None = None, method: Method | None = None,
                from_date: date | None = None, to_date: date | None = None):
    with session_database() as db:
        require_session(request, db)
        if order_id and (not order_id.startswith('PW-QA-') or
                         not all(c in '0123456789ABCDEF' for c in order_id[6:]) or len(order_id) > 30):
            raise HTTPException(422, 'Enter a valid QA order ID or prefix')
        if from_date and to_date and from_date > to_date:
            raise HTTPException(422, 'Invalid date range')
        stmt = select(Order)
        if order_id: stmt = stmt.where(Order.order_code.startswith(order_id))
        if method: stmt = stmt.where(Order.payment_method == method)
        if status: stmt = stmt.where(Order.status == status)
        if from_date: stmt = stmt.where(Order.created_at >= datetime.combine(from_date, datetime.min.time(), timezone.utc))
        if to_date: stmt = stmt.where(Order.created_at < datetime.combine(to_date + timedelta(days=1), datetime.min.time(), timezone.utc))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        results = db.scalars(stmt.order_by(Order.created_at.desc(), Order.id.desc())
                             .offset((page - 1) * page_size).limit(page_size)).all()
        audit(db, 'orders_list_view', True)
        db.commit()
        return {'test_mode': True, 'page': page, 'page_size': page_size,
                'total': total, 'has_more': page * page_size < total,
                'items': [order_detail(o) for o in results]}


@router.get('/admin/api/orders/{order_code}')
def inspect_order(order_code: str, request: Request):
    if len(order_code) > 40:
        raise HTTPException(404, 'Order not found')
    with session_database() as db:
        require_session(request, db)
        o = db.scalar(select(Order).where(Order.order_code == order_code))
        if not o: raise HTTPException(404, 'Order not found')
        events = db.scalars(select(AdminAudit).where(AdminAudit.order_code == order_code)
                            .order_by(AdminAudit.created_at.desc()).limit(15)).all()
        audit(db, 'order_inspected', True, order_code=order_code)
        db.commit()
        return {'test_mode': True, 'order': order_detail(o), 'timeline': [
            {'event': 'created', 'at': utc(o.created_at).isoformat(), 'status': 'PENDING_PAYMENT'}],
            'audit': [{'event': e.event, 'at': utc(e.created_at).isoformat()}
                      for e in events], **inspection(db, o), **fulfillment_inspection(db, o)}


def mount_admin(app: FastAPI, sessionmaker):
    global _SESSION_MAKER
    _SESSION_MAKER = sessionmaker
    app.include_router(router)


@router.get('/admin/ui.css')
def admin_stylesheet():
    config()
    from fastapi.responses import Response as FastResponse
    stylesheet = (Path(__file__).resolve().parent / 'admin-ui.css').read_text(encoding='utf8')
    return FastResponse(stylesheet, media_type='text/css', headers={'Cache-Control': 'no-store'})