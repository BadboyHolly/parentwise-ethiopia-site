"""QA-only manual Telegram fulfillment SIMULATION. No paid files or external sends."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4
import os, re
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from .admin_security import check_origin, check_csrf
from .models import Order, PaymentReview, SimulatedLedgerEntry, QaFulfillment, QaFulfillmentEvent

router = APIRouter()
_MAKER = None
PACKAGE_VERSION = 'QA-DEMO-2026.10-v1'
CHANNEL = 'TELEGRAM_FOUNDER_ASSISTED_QA_SIMULATION'
ACK_PATTERN = re.compile(r'^QA-ACK-[A-F0-9]{16}$')

def stamp(): return datetime.now(timezone.utc)

def require_qa():
    if os.getenv('APP_MODE','qa') != 'qa' or os.getenv('PAYMENTS_ENABLED','false').lower() != 'false':
        raise HTTPException(503, 'QA fulfillment simulation unavailable')

def founder(request, db, mutation=False):
    from .admin import require_session
    require_qa()
    raw, _, cfg = require_session(request, db)
    if mutation:
        check_origin(request, cfg)
        check_csrf(request, raw, cfg)

def find_order(db, code, lock=False):
    if not re.fullmatch(r'PW-QA-[A-F0-9]{24}', code):
        raise HTTPException(404, 'QA order not found')
    stmt = select(Order).where(Order.order_code == code)
    order = db.scalar(stmt.with_for_update() if lock else stmt)
    if not order: raise HTTPException(404, 'QA order not found')
    return order

def verified_dummy_credit(db, order, review_id=None):
    # Not a production verification gate. This is only an internal fictional ledger.
    if order.status != 'VERIFIED_PAID' or order.amount_etb != 1500 or order.currency != 'ETB':
        return None
    stmt = select(PaymentReview).where(
        PaymentReview.order_id == order.id, PaymentReview.state == 'VERIFIED_PAID',
        PaymentReview.independent_check == 'MATCHED',
        PaymentReview.reported_amount_etb == 1500, PaymentReview.currency == 'ETB')
    if review_id: stmt = stmt.where(PaymentReview.id == review_id)
    review = db.scalar(stmt)
    if not review: return None
    credit = db.scalar(select(SimulatedLedgerEntry.id).where(
        SimulatedLedgerEntry.credited_order_id == order.id,
        SimulatedLedgerEntry.test_reference == review.test_reference,
        SimulatedLedgerEntry.payment_method == review.payment_method,
        SimulatedLedgerEntry.amount_etb == 1500, SimulatedLedgerEntry.currency == 'ETB'))
    return review if credit else None

def event(db, f, action, before, after, *, note=None, ack=None):
    db.add(QaFulfillmentEvent(id=str(uuid4()), fulfillment_id=f.id, order_id=f.order_id,
        action=action, from_state=before, to_state=after, actor='qa_founder',
        note=note, qa_ack_reference=ack, happened_at=stamp()))
    f.updated_at = stamp()

def enroll_qa_verified(db, order, review, fixture):
    # Called in the SAME locked transaction as Phase 4 confirmation.
    # Validate those exact ORM rows before the transaction flush/commit.
    if not (order.status == 'VERIFIED_PAID' and order.amount_etb == 1500 and order.currency == 'ETB'
            and review.order_id == order.id and review.state == 'VERIFIED_PAID'
            and review.independent_check == 'MATCHED' and review.reported_amount_etb == 1500
            and review.currency == 'ETB' and fixture.credited_order_id == order.id
            and fixture.test_reference == review.test_reference
            and fixture.payment_method == review.payment_method
            and fixture.amount_etb == 1500 and fixture.currency == 'ETB'):
        raise HTTPException(409, 'Matched fictional ledger entry required')
    if db.scalar(select(QaFulfillment.id).where(QaFulfillment.order_id == order.id)):
        raise HTTPException(409, 'QA fulfillment already registered')
    f = QaFulfillment(id=str(uuid4()), order_id=order.id, qa_review_id=review.id,
        state='PENDING_FULFILLMENT', package_version=PACKAGE_VERSION,
        delivery_channel=CHANNEL, attempt_count=0, created_at=stamp(), updated_at=stamp())
    db.add(f); db.flush()
    event(db, f, 'qa_dummy_fulfillment_enrolled', 'NONE', f.state,
          note='Fictional ledger only; no actual payment or product access')
    return f

def summary(f):
    return dict(status=f.state, package_version=f.package_version,
        delivery_channel=f.delivery_channel, attempt_count=f.attempt_count,
        created_at=f.created_at.isoformat(), updated_at=f.updated_at.isoformat(),
        sent_at=f.sent_at.isoformat() if f.sent_at else None,
        delivered_at=f.delivered_at.isoformat() if f.delivered_at else None,
        failure_at=f.failure_at.isoformat() if f.failure_at else None,
        test_mode=True, simulated_only=True, real_files_sent=False)

def public_delivery(db, order):
    f=db.scalar(select(QaFulfillment).where(QaFulfillment.order_id == order.id))
    if not f or not verified_dummy_credit(db, order, f.qa_review_id): return None
    return dict(status=f.state, package_version=f.package_version,
        channel='Founder-assisted Telegram (simulation only)', simulated_only=True,
        real_files_sent=False, support='https://t.me/ParentWiseEthiopia',
        message='QA SIMULATION ONLY: no actual Telegram delivery, money, or paid product access. Real orders require independent actual-payment verification.')

def inspection(db, order):
    f=db.scalar(select(QaFulfillment).where(QaFulfillment.order_id == order.id))
    if not f: return dict(fulfillment=None, fulfillment_events=[])
    events=db.scalars(select(QaFulfillmentEvent).where(QaFulfillmentEvent.fulfillment_id==f.id)
        .order_by(QaFulfillmentEvent.happened_at, QaFulfillmentEvent.id).limit(100)).all()
    return dict(fulfillment=summary(f), fulfillment_events=[
        dict(action=e.action, before=e.from_state, after=e.to_state,
             at=e.happened_at.isoformat(), note=e.note, qa_ack_reference=e.qa_ack_reference)
        for e in events])

def lock_eligible(db, code):
    order=find_order(db, code, lock=True)
    f=db.scalar(select(QaFulfillment).where(QaFulfillment.order_id==order.id).with_for_update())
    if not f or not verified_dummy_credit(db, order, f.qa_review_id):
        raise HTTPException(409,'Only fully verified fictional QA credits enter dummy fulfillment')
    if f.package_version!=PACKAGE_VERSION or f.delivery_channel!=CHANNEL:
        raise HTTPException(409,'Unsupported QA dummy package')
    return f

class Confirm(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirm_qa_action: Literal[True]

class Dispatch(Confirm):
    dummy_document_checked: Literal[True]

class Receipt(Confirm):
    qa_ack_reference: str=Field(min_length=23,max_length=23)
    source: Literal['QA_SIMULATED_CUSTOMER_ACK']

class Reason(BaseModel):
    model_config=ConfigDict(extra='forbid', str_strip_whitespace=True)
    reason: str=Field(min_length=8,max_length=250)

@router.get('/admin/api/fulfillment/queue')
def queue(request:Request, page:int=Query(1,ge=1,le=5000),
          page_size:int=Query(15,ge=1,le=50),
          state:Literal['PENDING_FULFILLMENT','PREPARING','SENT','DELIVERED','DELIVERY_FAILED']|None=None):
    with _MAKER() as db:
        founder(request,db)
        stmt=select(QaFulfillment,Order).join(Order,QaFulfillment.order_id==Order.id).where(
            Order.status=='VERIFIED_PAID', QaFulfillment.package_version==PACKAGE_VERSION)
        if state: stmt=stmt.where(QaFulfillment.state==state)
        rows=db.execute(stmt.order_by(QaFulfillment.created_at.desc(),QaFulfillment.id.desc())
            .offset((page-1)*page_size).limit(page_size)).all()
        items=[dict(order_id=o.order_code,payment_state=o.status,**summary(f))
               for f,o in rows if verified_dummy_credit(db,o,f.qa_review_id)]
        total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return dict(test_mode=True,simulated_only=True,total=total,page=page,
                    has_more=page*page_size<total,items=items)

@router.get('/admin/api/fulfillment/dummy-document')
def dummy_file(request:Request):
    with _MAKER() as db:
        founder(request,db)
        path=Path(__file__).resolve().parent.parent/'qa-assets'/'QA_DUMMY_DELIVERY.txt'
        return PlainTextResponse(path.read_text(encoding='utf-8'),headers={
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Content-Disposition':'attachment; filename="PARENTWISE_QA_DUMMY_ONLY.txt"'})

@router.get('/admin/api/orders/{code}/fulfillment')
def detail(code:str,request:Request):
    with _MAKER() as db:
        founder(request,db)
        return dict(test_mode=True,simulated_only=True,**inspection(db,find_order(db,code)))

def transition(code,request,expected,target,action,*,reason=None,dispatch=False,ack=None):
    with _MAKER() as db:
        founder(request,db,mutation=True)
        f=lock_eligible(db,code)
        if f.state not in expected:
            raise HTTPException(409,'Duplicate or invalid simulated fulfillment transition')
        before=f.state
        f.state=target
        if dispatch:
            f.attempt_count+=1
            f.sent_at=stamp()
        if target=='DELIVERED':
            f.delivered_at=stamp()
            f.qa_ack_reference=ack
        if target=='DELIVERY_FAILED': f.failure_at=stamp()
        event(db,f,action,before,target,note=reason,ack=ack)
        try: db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409,'Fictional receipt reference already used') from None
        return dict(test_mode=True,simulated_only=True,fulfillment=summary(f))

@router.post('/admin/api/orders/{code}/fulfillment/prepare')
def prepare(code:str,payload:Confirm,request:Request):
    return transition(code,request,('PENDING_FULFILLMENT',),'PREPARING','qa_dummy_preparation')

@router.post('/admin/api/orders/{code}/fulfillment/dispatch')
def dispatch(code:str,payload:Dispatch,request:Request):
    return transition(code,request,('PREPARING',),'SENT','qa_dummy_dispatch_record',
        reason='Hypothetical dummy dispatch; software did not contact Telegram',dispatch=True)

@router.post('/admin/api/orders/{code}/fulfillment/receipt')
def receive(code:str,payload:Receipt,request:Request):
    if not re.fullmatch(r'QA-ACK-[A-F0-9]{16}',payload.qa_ack_reference):
        raise HTTPException(422,'Only fictional QA-ACK acknowledgement references allowed')
    return transition(code,request,('SENT',),'DELIVERED','qa_dummy_receipt_attested',
        reason='Fictional QA receipt attestation; not proof of Telegram receipt',ack=payload.qa_ack_reference)

@router.post('/admin/api/orders/{code}/fulfillment/failure')
def failure(code:str,payload:Reason,request:Request):
    return transition(code,request,('PREPARING','SENT'),'DELIVERY_FAILED',
        'qa_dummy_delivery_failed',reason=payload.reason)

@router.post('/admin/api/orders/{code}/fulfillment/retry')
def retry(code:str,payload:Reason,request:Request):
    return transition(code,request,('DELIVERY_FAILED',),'PREPARING',
        'qa_dummy_retry_preparation',reason=payload.reason)

def mount_fulfillment(app,maker):
    global _MAKER
    _MAKER=maker
    app.include_router(router)
