"""Founder-only QA simulated payment reconciliation. No payment provider integration.

The internal QA ledger is a synthetic fixture, NOT external financial evidence.
All mutations require a live founder session, same-origin and CSRF.
"""
import re
import secrets
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .admin_security import check_origin, check_csrf
from .models import Order, PaymentReview, PaymentEvent, SimulatedLedgerEntry

router = APIRouter()
_ORDER_MAKER = None
REF_RE = re.compile(r'^QA-(TB|BK)-[A-F0-9]{16}$')


def stamp():
    return datetime.now(timezone.utc)


def assert_simulation():
    from os import getenv
    if getenv('APP_MODE', 'qa') != 'qa' or getenv('PAYMENTS_ENABLED', 'false').lower() != 'false':
        raise HTTPException(503, 'Simulated payment review is unavailable')


def authenticated(request, db):
    from .admin import require_session
    assert_simulation()
    raw, _, cfg = require_session(request, db)
    check_origin(request, cfg)
    check_csrf(request, raw, cfg)


def find_order(db, code):
    if not re.fullmatch(r'PW-QA-[A-F0-9]{24}', code):
        raise HTTPException(404, 'QA order not found')
    row = db.scalar(select(Order).where(Order.order_code == code).with_for_update())
    if row is None:
        raise HTTPException(404, 'QA order not found')
    return row


def push_event(db, order, action, before, after, *, review_id=None, explanation=None):
    db.add(PaymentEvent(id=str(uuid4()), order_id=order.id, review_id=review_id,
                        action=action, previous_status=before, new_status=after,
                        reason=explanation, occurred_at=stamp(), actor='qa_founder'))
    order.updated_at = stamp()


def review_data(review):
    return {
        'id': review.id, 'payment_method': review.payment_method,
        'test_reference': review.test_reference, 'reported_amount_etb': review.reported_amount_etb,
        'currency': review.currency, 'state': review.state, 'independent_check': review.independent_check,
        'evidence_received_at': review.evidence_received_at.isoformat(),
        'checked_at': review.checked_at.isoformat() if review.checked_at else None,
        'decided_at': review.decided_at.isoformat() if review.decided_at else None,
        'decision_reason': review.decision_reason
    }


class LedgerFixture(BaseModel):
    model_config = ConfigDict(extra='forbid')
    method: Literal['telebirr', 'bank']
    amount_etb: Literal[1500, 1400] = 1500


class ReportedProof(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    test_reference: str = Field(min_length=22, max_length=22)
    reported_amount_etb: int = Field(ge=1, le=100000)
    currency: Literal['ETB'] = 'ETB'


class FounderDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    confirm_simulated_match: bool = False
    reason: str = Field(default='', max_length=300)


class Rejection(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    reason: str = Field(min_length=8, max_length=300)


@router.post('/admin/api/qa-ledger', status_code=201)
def create_fixture(payload: LedgerFixture, request: Request):
    """Generate synthetic credit IN OUR QA DB. Not a Telebirr/bank transaction."""
    with _ORDER_MAKER() as db:
        authenticated(request, db)
        prefix = 'TB' if payload.method == 'telebirr' else 'BK'
        fixture = SimulatedLedgerEntry(id=str(uuid4()), test_reference='QA-' + prefix + '-' + secrets.token_hex(8).upper(),
                                       payment_method=payload.method, amount_etb=payload.amount_etb,
                                       currency='ETB', generated_at=stamp(), credited_order_id=None)
        db.add(fixture)
        db.commit()
        return {'test_mode': True, 'simulated_only': True, 'test_reference': fixture.test_reference,
                'method': fixture.payment_method, 'amount_etb': fixture.amount_etb, 'currency': fixture.currency}


@router.post('/admin/api/orders/{code}/proof', status_code=201)
def submit_proof(code: str, payload: ReportedProof, request: Request):
    if not REF_RE.fullmatch(payload.test_reference):
        raise HTTPException(422, 'Only fictional QA transaction references are allowed')
    with _ORDER_MAKER() as db:
        authenticated(request, db)
        order = find_order(db, code)
        if order.status != 'PENDING_PAYMENT':
            raise HTTPException(409, 'Order is not awaiting a new claim')
        if not payload.test_reference.startswith('QA-TB-' if order.payment_method == 'telebirr' else 'QA-BK-'):
            raise HTTPException(422, 'Reference does not match selected payment method')
        review = PaymentReview(id=str(uuid4()), order_id=order.id, payment_method=order.payment_method,
                               test_reference=payload.test_reference, reported_amount_etb=payload.reported_amount_etb,
                               currency='ETB', state='PROOF_SUBMITTED', independent_check='NOT_CHECKED',
                               evidence_received_at=stamp())
        db.add(review)
        prior = order.status
        order.status = 'PROOF_SUBMITTED'
        push_event(db, order, 'fictional_proof_recorded', prior, order.status, review_id=review.id)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Test transaction reference already submitted for an order') from None
        return {'test_mode': True, 'simulated_only': True, 'order_status': order.status, 'review': review_data(review)}


@router.post('/admin/api/orders/{code}/check')
def independent_check(code: str, request: Request):
    """Server recomputes independent test-ledger match; client cannot assert MATCHED."""
    with _ORDER_MAKER() as db:
        authenticated(request, db)
        order = find_order(db, code)
        if order.status != 'PROOF_SUBMITTED':
            raise HTTPException(409, 'Order proof must be submitted before checking')
        review = db.scalar(select(PaymentReview).where(PaymentReview.order_id == order.id,
                     PaymentReview.state == 'PROOF_SUBMITTED').with_for_update())
        if not review:
            raise HTTPException(409, 'No pending simulated proof')
        fixture = db.scalar(select(SimulatedLedgerEntry).where(
            SimulatedLedgerEntry.payment_method == review.payment_method,
            SimulatedLedgerEntry.test_reference == review.test_reference).with_for_update())
        match = bool(fixture and fixture.amount_etb == review.reported_amount_etb == order.amount_etb
                     and fixture.currency == review.currency == order.currency
                     and fixture.credited_order_id is None)
        review.independent_check = 'MATCHED' if match else 'DISCREPANCY'
        review.checked_at = stamp()
        review.state = 'VERIFYING'
        prior = order.status
        order.status = 'VERIFYING'
        push_event(db, order, 'qa_ledger_match' if match else 'qa_ledger_discrepancy',
                   prior, order.status, review_id=review.id,
                   explanation=None if match else 'QA ledger reference, amount, currency or availability did not match')
        db.commit()
        return {'test_mode': True, 'simulated_only': True, 'order_status': order.status,
                'independent_check': review.independent_check}


@router.post('/admin/api/orders/{code}/confirm')
def confirm_match(code: str, payload: FounderDecision, request: Request):
    if payload.confirm_simulated_match is not True:
        raise HTTPException(422, 'Explicit simulated verification confirmation required')
    with _ORDER_MAKER() as db:
        authenticated(request, db)
        order = find_order(db, code)
        if order.status != 'VERIFYING':
            raise HTTPException(409, 'Order is not in verification review')
        review = db.scalar(select(PaymentReview).where(PaymentReview.order_id == order.id,
                     PaymentReview.state == 'VERIFYING').with_for_update())
        if not review or review.independent_check != 'MATCHED':
            raise HTTPException(409, 'Successful independent QA ledger check required')
        fixture = db.scalar(select(SimulatedLedgerEntry).where(
            SimulatedLedgerEntry.test_reference == review.test_reference,
            SimulatedLedgerEntry.payment_method == review.payment_method).with_for_update())
        if (not fixture or fixture.credited_order_id is not None
            or fixture.amount_etb != review.reported_amount_etb or fixture.amount_etb != order.amount_etb
            or fixture.currency != order.currency):
            raise HTTPException(409, 'Ledger credit is unavailable or mismatched')
        fixture.credited_order_id = order.id
        review.state = 'VERIFIED_PAID'
        review.decided_at = stamp()
        review.decision_reason = 'Confirmed ONLY against fabricated QA ledger record'
        prior = order.status
        order.status = 'VERIFIED_PAID'
        push_event(db, order, 'qa_payment_verified', prior, order.status, review_id=review.id)
        db.commit()
        return {'test_mode': True, 'simulated_only': True, 'status': 'VERIFIED_PAID'}


@router.post('/admin/api/orders/{code}/reject')
def reject_claim(code: str, payload: Rejection, request: Request):
    with _ORDER_MAKER() as db:
        authenticated(request, db)
        order = find_order(db, code)
        if order.status not in ('PROOF_SUBMITTED', 'VERIFYING'):
            raise HTTPException(409, 'Order does not have an active claim to reject')
        review = db.scalar(select(PaymentReview).where(PaymentReview.order_id == order.id,
                       PaymentReview.state.in_(['PROOF_SUBMITTED','VERIFYING'])).with_for_update())
        if not review:
            raise HTTPException(409, 'Active claim not found')
        review.state = 'REJECTED'
        review.decided_at = stamp()
        review.decision_reason = payload.reason
        prior = order.status
        order.status = 'PENDING_PAYMENT'
        push_event(db, order, 'qa_claim_rejected', prior, order.status, review_id=review.id,
                   explanation=payload.reason)
        db.commit()
        return {'test_mode': True, 'simulated_only': True, 'status': order.status}


@router.post('/admin/api/orders/{code}/cancel')
def cancel_order(code: str, payload: Rejection, request: Request):
    with _ORDER_MAKER() as db:
        authenticated(request, db)
        order = find_order(db, code)
        if order.status not in ('PENDING_PAYMENT','PROOF_SUBMITTED','VERIFYING'):
            raise HTTPException(409, 'This simulated order can no longer be cancelled')
        if order.status in ('PROOF_SUBMITTED','VERIFYING'):
            active = db.scalar(select(PaymentReview).where(PaymentReview.order_id == order.id,
                PaymentReview.state.in_(['PROOF_SUBMITTED','VERIFYING'])).with_for_update())
            if active:
                active.state = 'REJECTED'
                active.decided_at = stamp()
                active.decision_reason = 'Cancelled: ' + payload.reason
        prior = order.status
        order.status = 'CANCELLED'
        push_event(db, order, 'qa_order_cancelled', prior, order.status,
                   explanation=payload.reason)
        db.commit()
        return {'test_mode': True, 'simulated_only': True, 'status': 'CANCELLED'}


def inspection(db, order):
    reviews = db.scalars(select(PaymentReview).where(PaymentReview.order_id == order.id)
        .order_by(PaymentReview.evidence_received_at.desc(), PaymentReview.id.desc()).limit(30)).all()
    events = db.scalars(select(PaymentEvent).where(PaymentEvent.order_id == order.id)
        .order_by(PaymentEvent.occurred_at.asc(), PaymentEvent.id.asc()).limit(100)).all()
    return {'reviews': [review_data(x) for x in reviews],
            'verification_history': [
                {'event': e.action, 'before': e.previous_status, 'after': e.new_status,
                 'at': e.occurred_at.isoformat(), 'reason': e.reason}
                for e in events]}


def mount_payment_review(app, sessionmaker):
    global _ORDER_MAKER
    _ORDER_MAKER = sessionmaker
    app.include_router(router)