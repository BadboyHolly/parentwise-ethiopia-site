"""Customer claim and recovery routes; claims never mutate production paid state."""
import json, re, uuid
from datetime import timezone
from fastapi import HTTPException, Request, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .models import OrderState, PaymentClaim, DownloadGrant
from .security import order_for_customer, utcnow, audit

SIM_REFERENCE = re.compile(r"^SIM-[A-Z0-9]{8,40}$")

class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    test_reference: str = Field(min_length=12, max_length=48, pattern=r"^SIM-[A-Z0-9]{8,40}$")
    reported_amount_etb: int = Field(ge=1, le=100000)
    currency: str = Field(min_length=3, max_length=3)

def mount_payment_claims(app):
    @app.post("/api/v1/orders/{code}/payment-claims", status_code=201)
    def submit_claim(code: str, item: ClaimInput, request: Request,
                     authorization: str = Header(default="", alias="Authorization")):
        if item.currency != "ETB":
            raise HTTPException(422, "Use ETB for this QA claim")
        try:
            with app.state.order_sessions.begin() as db:
                order = order_for_customer(db, code, authorization, app.state.order_token_secret)
                state = db.scalar(select(OrderState).where(OrderState.order_id == order.id).with_for_update())
                if state is None:
                    state = OrderState(order_id=order.id, order_code=order.code, status="AWAITING_PAYMENT", updated_at=utcnow())
                    db.add(state)
                if state.status != "AWAITING_PAYMENT":
                    raise HTTPException(409, "This order cannot accept another claim yet")
                previous = db.scalar(select(PaymentClaim).where(PaymentClaim.order_id == order.id).order_by(PaymentClaim.created_at.desc()))
                if previous and previous.state != "REJECTED":
                    raise HTTPException(409, "A payment claim is already under review")
                duplicate = db.scalar(select(PaymentClaim).where(PaymentClaim.reference == item.test_reference))
                if duplicate:
                    raise HTTPException(409, "This transaction reference was already claimed")
                claim = PaymentClaim(id=str(uuid.uuid4()), order_id=order.id,
                                     reference=item.test_reference, payment_method=order.method,
                                     reported_amount_etb=item.reported_amount_etb, currency=item.currency,
                                     state="SUBMITTED", created_at=utcnow())
                db.add(claim)
                state.status = "UNDER_REVIEW"
                state.updated_at = utcnow()
                audit(db, order.id, "customer", "payment_claim_submitted",
                      json.dumps({"claim_id": claim.id, "payment_method": order.method}, separators=(",", ":")))
                db.flush()
                return {"claim_id": claim.id, "customer_status": "Under Review", "claim_is_payment_confirmation": False}
        except IntegrityError:
            raise HTTPException(409, "This transaction reference was already claimed") from None

    @app.get("/api/v1/orders/{code}/checkout-status")
    def checkout_status(code: str, request: Request, authorization: str = Header(default="", alias="Authorization")):
        with app.state.order_sessions() as db:
            order = order_for_customer(db, code, authorization, app.state.order_token_secret)
            state = db.scalar(select(OrderState).where(OrderState.order_id == order.id))
            status = state.status if state else "AWAITING_PAYMENT"
            grant = db.scalar(select(DownloadGrant).where(DownloadGrant.order_id == order.id))
            latest_claim = db.scalar(select(PaymentClaim).where(PaymentClaim.order_id == order.id)
                                      .order_by(PaymentClaim.created_at.desc()).limit(1))
            ready = bool(grant and grant.active and grant.revoked_at is None and status == "READY_TO_DOWNLOAD")
            # Approval remains confirmed after access revocation, but the customer
            # must not be told downloads are ready when no active grant exists.
            if status == "READY_TO_DOWNLOAD" and not ready:
                status = "PAYMENT_CONFIRMED"
            labels = {"AWAITING_PAYMENT":"Awaiting Payment","UNDER_REVIEW":"Under Review",
                      "PAYMENT_CONFIRMED":"Payment Confirmed","READY_TO_DOWNLOAD":"Ready to Download"}
            claim_outcome = "NOT_MATCHED" if latest_claim and latest_claim.state == "REJECTED" else None
            return {"order_id": order.code, "status": labels.get(status, "Awaiting Payment"),
                    "downloads_ready": ready, "download_access_revoked": bool(grant and grant.revoked_at is not None),
                    "claim_outcome": claim_outcome, "payment_confirmation_requires_founder": True}
