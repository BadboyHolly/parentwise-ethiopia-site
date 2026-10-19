"""Synthetic founder MFA, simulated settlement matching and audited approval."""
import hashlib, hmac, json, secrets, uuid
from datetime import timezone
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .models import OrderState, PaymentClaim, SimulatedSettlement, DownloadGrant
from .security import audit, issue_founder_session, require_founder, utcnow, valid_totp

QA_RECIPIENTS = {"telebirr":"QA-TELEBIRR-ONLY", "bank":"QA-CBE-ONLY"}

class FounderLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=200)
    totp: str = Field(pattern=r"^[0-9]{6}$")

class SettlementInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    test_reference: str = Field(pattern=r"^SIM-[A-Z0-9]{8,40}$", min_length=12, max_length=48)
    payment_method: str = Field(pattern=r"^(telebirr|bank)$")
    amount_etb: int = Field(ge=1, le=100000)
    currency: str = Field(pattern=r"^ETB$")
    recipient_code: str = Field(pattern=r"^QA-[A-Z0-9-]{3,32}$")
    payer_mobile: str = Field(pattern=r"^\+251[0-9]{9}$")

class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="Synthetic QA review", min_length=3, max_length=200)

def mount_founder_verification(app):
    @app.post("/founder/session")
    def login(item: FounderLogin, response: Response):
        if not hmac.compare_digest(item.username, app.state.founder_username) or not valid_totp(app.state.founder_totp_secret, item.totp):
            raise HTTPException(401, "Founder sign-in failed")
        try:
            app.state.password_hasher.verify(app.state.founder_password_hash, item.password)
        except VerifyMismatchError:
            raise HTTPException(401, "Founder sign-in failed") from None
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        with app.state.order_sessions.begin() as db:
            issue_founder_session(db, token, csrf)
            audit(db, None, "synthetic_founder", "founder_session_created", "{}")
        response.set_cookie("pw_stage_founder", token, httponly=True, secure=True,
                            samesite="strict", max_age=900, path="/founder")
        return {"csrf_token": csrf, "expires_in_seconds": 900, "synthetic_only": True}

    @app.post("/founder/api/simulated-settlements", status_code=201)
    def add_settlement(item: SettlementInput, request: Request):
        try:
            with app.state.order_sessions.begin() as db:
                actor = require_founder(request, db)
                if item.recipient_code not in QA_RECIPIENTS.values():
                    raise HTTPException(422, "Only fictional QA recipient codes are accepted")
                row = SimulatedSettlement(reference=item.test_reference, payment_method=item.payment_method,
                    amount_etb=item.amount_etb, currency=item.currency, recipient_code=item.recipient_code,
                    payer_mobile=item.payer_mobile, recorded_by=actor, created_at=utcnow())
                db.add(row)
                audit(db, None, actor, "fictional_settlement_recorded",
                      json.dumps({"method":item.payment_method,"amount_etb":item.amount_etb},separators=(",",":")))
                db.flush()
                return {"recorded":True,"simulated_only":True}
        except IntegrityError:
            raise HTTPException(409, "This fictional settlement reference already exists") from None

    @app.post("/founder/api/orders/{code}/verify")
    def verify_claim(code: str, request: Request):
        with app.state.order_sessions.begin() as db:
            actor = require_founder(request, db)
            from production_checkout.app import Order
            order = db.scalar(select(Order).where(Order.code == code).with_for_update())
            if order is None:
                raise HTTPException(404, "Order not found")
            state = db.scalar(select(OrderState).where(OrderState.order_id == order.id).with_for_update())
            claim = db.scalar(select(PaymentClaim).where(PaymentClaim.order_id == order.id).order_by(PaymentClaim.created_at.desc()).with_for_update())
            if state is None or state.status != "UNDER_REVIEW" or claim is None or claim.state not in ("SUBMITTED","DISCREPANCY"):
                raise HTTPException(409, "There is no reviewable payment claim")
            evidence = db.scalar(select(SimulatedSettlement).where(SimulatedSettlement.reference == claim.reference))
            matched = bool(evidence and
                evidence.payment_method == order.method == claim.payment_method and
                evidence.amount_etb == order.amount_etb == claim.reported_amount_etb and
                evidence.currency == order.currency == claim.currency and
                evidence.recipient_code == QA_RECIPIENTS[order.method] and
                evidence.payer_mobile == order.mobile_e164)
            claim.state = "MATCHED" if matched else "DISCREPANCY"
            state.updated_at = utcnow()
            audit(db, order.id, actor, "fictional_settlement_match" if matched else "fictional_settlement_discrepancy",
                  json.dumps({"claim_id":claim.id,"matched":matched},separators=(",",":")))
            return {"matched":matched,"can_approve":matched,"simulated_only":True}

    @app.post("/founder/api/orders/{code}/approve")
    def approve(code: str, request: Request, item: DecisionInput):
        with app.state.order_sessions.begin() as db:
            actor = require_founder(request, db)
            from production_checkout.app import Order
            order = db.scalar(select(Order).where(Order.code == code).with_for_update())
            if order is None:
                raise HTTPException(404, "Order not found")
            state = db.scalar(select(OrderState).where(OrderState.order_id == order.id).with_for_update())
            claim = db.scalar(select(PaymentClaim).where(PaymentClaim.order_id == order.id).order_by(PaymentClaim.created_at.desc()).with_for_update())
            if state is None or state.status != "UNDER_REVIEW" or claim is None or claim.state != "MATCHED":
                raise HTTPException(409, "Only an independently matched claim can be approved")
            state.status = "PAYMENT_CONFIRMED"
            state.updated_at = utcnow()
            audit(db, order.id, actor, "founder_payment_approved",
                  json.dumps({"claim_id":claim.id,"reason":item.reason},separators=(",",":")))
            grant = db.scalar(select(DownloadGrant).where(DownloadGrant.order_id == order.id).with_for_update())
            if grant is None:
                grant = DownloadGrant(order_id=order.id, active=True, package_version="QA-DUMMY-v1",
                                      issued_at=utcnow(), revoked_at=None)
                db.add(grant)
            else:
                grant.active, grant.revoked_at = True, None
                grant.issued_at = utcnow()
            state.status = "READY_TO_DOWNLOAD"
            audit(db, order.id, actor, "private_dummy_download_grant_issued", "{}")
            return {"status":"Ready to Download","downloads_ready":True,"simulated_only":True}

    @app.post("/founder/api/orders/{code}/reject")
    def reject(code: str, request: Request, item: DecisionInput):
        with app.state.order_sessions.begin() as db:
            actor = require_founder(request, db)
            from production_checkout.app import Order
            order = db.scalar(select(Order).where(Order.code == code).with_for_update())
            if order is None:
                raise HTTPException(404, "Order not found")
            state = db.scalar(select(OrderState).where(OrderState.order_id == order.id).with_for_update())
            claim = db.scalar(select(PaymentClaim).where(PaymentClaim.order_id == order.id).order_by(PaymentClaim.created_at.desc()).with_for_update())
            if state is None or state.status != "UNDER_REVIEW" or claim is None or claim.state not in ("SUBMITTED","DISCREPANCY","MATCHED"):
                raise HTTPException(409, "There is no rejectable claim")
            claim.state = "REJECTED"
            state.status = "AWAITING_PAYMENT"
            state.updated_at = utcnow()
            audit(db, order.id, actor, "payment_claim_rejected",
                  json.dumps({"claim_id":claim.id,"reason":item.reason},separators=(",",":")))
            return {"status":"Awaiting Payment","retry_allowed":True}

    @app.post("/founder/api/orders/{code}/downloads/revoke")
    def revoke(code: str, request: Request, item: DecisionInput):
        with app.state.order_sessions.begin() as db:
            actor = require_founder(request, db)
            from production_checkout.app import Order
            order = db.scalar(select(Order).where(Order.code == code).with_for_update())
            if order is None:
                raise HTTPException(404, "Order not found")
            state = db.scalar(select(OrderState).where(OrderState.order_id == order.id).with_for_update())
            grant = db.scalar(select(DownloadGrant).where(DownloadGrant.order_id == order.id).with_for_update())
            if not grant or not grant.active:
                raise HTTPException(409, "No active download grant exists")
            grant.active, grant.revoked_at = False, utcnow()
            if state:
                state.status = "PAYMENT_CONFIRMED"
                state.updated_at = utcnow()
            audit(db, order.id, actor, "private_download_grant_revoked",
                  json.dumps({"reason":item.reason},separators=(",",":")))
            return {"revoked":True,"downloads_ready":False}
