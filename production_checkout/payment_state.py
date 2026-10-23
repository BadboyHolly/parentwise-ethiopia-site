"""Fail-closed production payment and fulfillment state service.

These transaction functions are not mounted as HTTP routes. Future customer
handlers must authenticate the order token; founder handlers must first
authenticate MFA/CSRF and pass the resulting founder ID. No staging models,
fictional recipient values, or settlement simulator are imported here.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .app import hmac_digest

_REFERENCE = re.compile(r"^[A-Z0-9][A-Z0-9/_-]{2,127}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_FOUNDER_ID = re.compile(r"^[A-Za-z0-9._@-]{1,80}$")
_RELATIONSHIPS = {"SPOUSE", "RELATIVE", "OTHER"}


class PaymentStateError(Exception):
    """Safe domain failure; callers should not expose database details."""


class OrderNotFound(PaymentStateError):
    pass


class UnauthorizedFounder(PaymentStateError):
    pass


class InvalidTransition(PaymentStateError):
    pass


class DuplicateReference(PaymentStateError):
    pass


class DownloadDenied(PaymentStateError):
    pass


def transaction_reference_digest(secret: str, reference: str) -> str:
    if len(secret) < 32 or not isinstance(reference, str):
        raise ValueError("Reference hashing configuration is invalid")
    normalized = re.sub(r"\s+", "", reference).upper()
    if not _REFERENCE.fullmatch(normalized):
        raise ValueError("Transaction reference format is invalid")
    return hmac_digest(secret, "transaction-reference:v1:" + normalized)


def identity_digest(secret: str, mobile_e164: str) -> str:
    if len(secret) < 32 or not re.fullmatch(r"\+251[97][0-9]{8}", mobile_e164):
        raise ValueError("Identity hashing input is invalid")
    return hmac_digest(secret, "payer-identity:v1:" + mobile_e164)


def _founder(actor_id: str | None) -> str:
    if not isinstance(actor_id, str) or not _FOUNDER_ID.fullmatch(actor_id):
        raise UnauthorizedFounder("Authenticated founder identity is required")
    return actor_id


def _digest(value: str, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 HMAC")
    return value


def _locked_order_state(db: Session, order_code: str):
    row = db.execute(text("""
        SELECT o.id AS order_id, o.code, o.method, o.amount_etb, o.currency,
               o.mobile_e164, o.access_hash,
               s.payment_status, s.fulfillment_status
          FROM production_orders o
          JOIN production_payment_fulfillment_state s ON s.order_id = o.id
         WHERE o.code = :code
         FOR UPDATE OF o, s
    """), {"code": order_code}).mappings().first()
    if row is None:
        raise OrderNotFound("Order not found")
    return row


def _audit(db: Session, *, order_id: str, event_type: str, actor_type: str,
           actor_id: str | None, event_data: dict[str, Any] | None = None) -> None:
    db.execute(text("""
        INSERT INTO production_payment_audit_events
          (order_id, event_type, actor_type, actor_id, event_data)
        VALUES (:order_id, :event_type, :actor_type, :actor_id, CAST(:event_data AS JSONB))
    """), {"order_id": order_id, "event_type": event_type,
           "actor_type": actor_type, "actor_id": actor_id,
           "event_data": json.dumps(event_data or {}, separators=(",", ":"))})


def submit_payment_claim(
    db: Session, *, order_code: str, access_token: str, token_secret: str,
    reference_hash_secret: str, transaction_reference: str,
    reference_ciphertext: str,
) -> str:
    """Store a private claim. The raw token/reference are never written to DB."""
    if len(token_secret) < 32:
        raise ValueError("Order token configuration is invalid")
    if (not isinstance(reference_ciphertext, str) or
            not reference_ciphertext.startswith("enc:v1:") or
            not 7 < len(reference_ciphertext) <= 4096):
        raise ValueError("Transaction reference must be encrypted before storage")
    ref_digest = transaction_reference_digest(reference_hash_secret, transaction_reference)
    try:
        with db.begin():
            order = _locked_order_state(db, order_code)
            presented = hmac_digest(token_secret, "stored:v1:" + (access_token or ""))
            if not hmac.compare_digest(order["access_hash"], presented):
                raise DownloadDenied("Order authorization failed")
            if order["payment_status"] not in {"AWAITING_PAYMENT", "PAYMENT_REJECTED"}:
                raise InvalidTransition("A claim cannot be submitted in the current state")
            claim_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO production_payment_claims
                  (id, order_id, payment_method, amount_etb, currency,
                   reference_digest, reference_ciphertext)
                VALUES (:id, :order_id, :method, :amount, :currency, :digest, :ciphertext)
            """), {"id": claim_id, "order_id": order["order_id"],
                   "method": order["method"], "amount": order["amount_etb"],
                   "currency": order["currency"], "digest": ref_digest,
                   "ciphertext": reference_ciphertext})
            db.execute(text("""
                UPDATE production_payment_fulfillment_state
                   SET payment_status = 'UNDER_REVIEW'
                 WHERE order_id = :order_id
            """), {"order_id": order["order_id"]})
            _audit(db, order_id=order["order_id"], event_type="PAYMENT_CLAIM_SUBMITTED",
                   actor_type="CUSTOMER", actor_id=None,
                   event_data={"claim_id": claim_id})
            return claim_id
    except IntegrityError as exc:
        if "uq" in str(getattr(exc, "orig", exc)).lower() or "unique" in str(exc).lower():
            raise DuplicateReference("Transaction reference has already been claimed") from None
        raise


def record_founder_telegram_claim(
    db: Session, *, actor_id: str | None, order_code: str, payment_method: str,
    reference_hash_secret: str, transaction_reference: str,
    reference_ciphertext: str,
) -> str:
    """Record a Telegram-reported claim without asserting settlement.

    The founder identity is taken from the authenticated session. The order's
    configured method and server-priced amount are authoritative; this function
    only accepts the explicitly matched method and an encrypted reference.
    """
    actor = _founder(actor_id)
    if payment_method not in {"telebirr", "bank"}:
        raise ValueError("Claim payment method is invalid")
    if (not isinstance(reference_ciphertext, str) or
            not reference_ciphertext.startswith("enc:v1:") or
            not 7 < len(reference_ciphertext) <= 4096):
        raise ValueError("Transaction reference must be encrypted before storage")
    ref_digest = transaction_reference_digest(reference_hash_secret, transaction_reference)
    try:
        with db.begin():
            order = _locked_order_state(db, order_code)
            if order["method"] != payment_method or order["amount_etb"] != 1500 or order["currency"] != "ETB":
                raise InvalidTransition("Claim details do not match the order")
            if order["payment_status"] not in {"AWAITING_PAYMENT", "PAYMENT_REJECTED"}:
                raise InvalidTransition("A claim cannot be recorded in the current state")
            claim_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO production_payment_claims
                  (id, order_id, payment_method, amount_etb, currency,
                   reference_digest, reference_ciphertext)
                VALUES (:id, :order_id, :method, :amount, :currency, :digest, :ciphertext)
            """), {"id": claim_id, "order_id": order["order_id"],
                   "method": payment_method, "amount": order["amount_etb"],
                   "currency": order["currency"], "digest": ref_digest,
                   "ciphertext": reference_ciphertext})
            db.execute(text("""
                UPDATE production_payment_fulfillment_state
                   SET payment_status = 'UNDER_REVIEW'
                 WHERE order_id = :order_id
            """), {"order_id": order["order_id"]})
            _audit(db, order_id=order["order_id"],
                   event_type="PAYMENT_CLAIM_RECORDED_TELEGRAM",
                   actor_type="FOUNDER", actor_id=actor,
                   event_data={"claim_id": claim_id, "channel": "TELEGRAM"})
            return claim_id
    except IntegrityError as exc:
        if "uq" in str(getattr(exc, "orig", exc)).lower() or "unique" in str(exc).lower():
            raise DuplicateReference("Transaction reference has already been claimed") from None
        raise


def record_settlement_evidence(
    db: Session, *, actor_id: str | None, order_code: str, claim_id: str,
    reference_digest: str, payment_method: str, amount_etb: int, currency: str,
    recipient_digest: str, payer_identity_digest: str, evidence_source: str,
    settled_at: datetime, evidence_note_ciphertext: str = "",
) -> str:
    """Record a founder-observed settlement; it does not approve or unlock."""
    actor = _founder(actor_id)
    ref_digest = _digest(reference_digest, "reference_digest")
    recipient = _digest(recipient_digest, "recipient_digest")
    payer = _digest(payer_identity_digest, "payer_identity_digest")
    if payment_method not in {"telebirr", "bank"}:
        raise ValueError("Settlement payment method is invalid")
    if evidence_source not in {"TELEBIRR_PORTAL", "BANK_STATEMENT"}:
        raise ValueError("Settlement source is invalid")
    if not isinstance(settled_at, datetime) or settled_at.tzinfo is None:
        raise ValueError("Settlement time must include a timezone")
    if len(evidence_note_ciphertext) > 4096:
        raise ValueError("Evidence note exceeds the storage limit")
    try:
        with db.begin():
            order = _locked_order_state(db, order_code)
            if order["payment_status"] != "UNDER_REVIEW":
                raise InvalidTransition("Settlement evidence requires a pending claim")
            claim = db.execute(text("""
                SELECT id, order_id, claim_status FROM production_payment_claims
                 WHERE id = :id AND order_id = :order_id FOR UPDATE
            """), {"id": claim_id, "order_id": order["order_id"]}).mappings().first()
            if claim is None or claim["claim_status"] != "SUBMITTED":
                raise InvalidTransition("Claim is unavailable for evidence")
            evidence_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO production_settlement_evidence
                  (id, order_id, claim_id, reference_digest, payment_method,
                   amount_etb, currency, recipient_digest, payer_identity_digest,
                   evidence_source, evidence_note_ciphertext, settled_at, observed_by)
                VALUES (:id, :order_id, :claim_id, :reference_digest, :method,
                        :amount, :currency, :recipient, :payer, :source, :note,
                        :settled_at, :actor)
            """), {"id": evidence_id, "order_id": order["order_id"],
                   "claim_id": claim_id, "reference_digest": ref_digest,
                   "method": payment_method, "amount": amount_etb,
                   "currency": currency, "recipient": recipient, "payer": payer,
                   "source": evidence_source, "note": evidence_note_ciphertext,
                   "settled_at": settled_at, "actor": actor})
            db.execute(text("""
                UPDATE production_payment_claims SET claim_status = 'EVIDENCE_RECORDED'
                 WHERE id = :id
            """), {"id": claim_id})
            _audit(db, order_id=order["order_id"], event_type="SETTLEMENT_EVIDENCE_RECORDED",
                   actor_type="FOUNDER", actor_id=actor,
                   event_data={"claim_id": claim_id, "evidence_id": evidence_id})
            return evidence_id
    except IntegrityError as exc:
        if "unique" in str(exc).lower():
            raise DuplicateReference("Settlement reference has already been recorded") from None
        raise


def document_third_party_exception(
    db: Session, *, actor_id: str | None, order_code: str, claim_id: str,
    evidence_id: str, relationship: str, rationale: str,
    identity_hash_secret: str,
) -> str:
    """Record a manual payer/buyer mismatch exception; it is not approval."""
    actor = _founder(actor_id)
    if relationship not in _RELATIONSHIPS:
        raise ValueError("Relationship category is invalid")
    if not isinstance(rationale, str) or not 10 <= len(rationale.strip()) <= 1000:
        raise ValueError("A documented reason is required")
    with db.begin():
        order = _locked_order_state(db, order_code)
        if order["payment_status"] != "UNDER_REVIEW":
            raise InvalidTransition("Third-party exceptions require a pending order")
        evidence = db.execute(text("""
            SELECT payer_identity_digest FROM production_settlement_evidence
             WHERE id = :evidence_id AND order_id = :order_id AND claim_id = :claim_id
             FOR UPDATE
        """), {"evidence_id": evidence_id, "order_id": order["order_id"],
               "claim_id": claim_id}).mappings().first()
        if evidence is None:
            raise InvalidTransition("Settlement evidence does not match this claim")
        buyer_digest = identity_digest(identity_hash_secret, order["mobile_e164"])
        if hmac.compare_digest(evidence["payer_identity_digest"], buyer_digest):
            raise InvalidTransition("An exception is only valid for a payer identity mismatch")
        exception_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO production_third_party_payer_exceptions
              (id, order_id, claim_id, evidence_id, relationship, rationale, documented_by)
            VALUES (:id, :order_id, :claim_id, :evidence_id, :relationship, :rationale, :actor)
        """), {"id": exception_id, "order_id": order["order_id"],
               "claim_id": claim_id, "evidence_id": evidence_id,
               "relationship": relationship, "rationale": rationale.strip(),
               "actor": actor})
        _audit(db, order_id=order["order_id"], event_type="THIRD_PARTY_EXCEPTION_DOCUMENTED",
               actor_type="FOUNDER", actor_id=actor,
               event_data={"claim_id": claim_id, "evidence_id": evidence_id,
                           "exception_id": exception_id, "relationship": relationship})
        return exception_id


def approve_payment(
    db: Session, *, actor_id: str | None, order_code: str, claim_id: str,
    evidence_id: str, reason: str, token_secret: str,
    reference_hash_secret: str, identity_hash_secret: str,
    expected_recipient_digest: str, third_party_exception_id: str | None = None,
    fulfillment_mode: str = "manual_telegram",
) -> str | None:
    """Explicit founder approval after all server-side settlement comparisons."""
    actor = _founder(actor_id)
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
        raise ValueError("An approval reason is required")
    expected_recipient = _digest(expected_recipient_digest, "expected_recipient_digest")
    if len(token_secret) < 32 or len(reference_hash_secret) < 32:
        raise ValueError("Server key configuration is invalid")
    if fulfillment_mode not in {"website_download", "manual_telegram"}:
        raise ValueError("Unsupported fulfillment mode")
    try:
        with db.begin():
            order = _locked_order_state(db, order_code)
            if order["payment_status"] != "UNDER_REVIEW":
                raise InvalidTransition("Order is not awaiting a founder decision")
            row = db.execute(text("""
                SELECT c.id AS claim_id, c.reference_digest AS claim_reference,
                       c.claim_status, c.payment_method AS claim_method,
                       c.amount_etb AS claim_amount, c.currency AS claim_currency,
                       e.id AS evidence_id, e.reference_digest AS settlement_reference,
                       e.payment_method AS settlement_method, e.amount_etb AS settlement_amount,
                       e.currency AS settlement_currency, e.recipient_digest,
                       e.payer_identity_digest
                  FROM production_payment_claims c
                  JOIN production_settlement_evidence e
                    ON e.claim_id = c.id AND e.order_id = c.order_id
                 WHERE c.id = :claim_id AND e.id = :evidence_id
                   AND c.order_id = :order_id
                 FOR UPDATE OF c, e
            """), {"claim_id": claim_id, "evidence_id": evidence_id,
                   "order_id": order["order_id"]}).mappings().first()
            if row is None or row["claim_status"] != "EVIDENCE_RECORDED":
                raise InvalidTransition("Matching settlement evidence is required")
            matches = (
                hmac.compare_digest(row["claim_reference"], row["settlement_reference"])
                and row["claim_method"] == row["settlement_method"] == order["method"]
                and row["claim_amount"] == row["settlement_amount"] == 1500
                and row["claim_currency"] == row["settlement_currency"] == "ETB"
                and hmac.compare_digest(row["recipient_digest"], expected_recipient)
            )
            if not matches:
                raise InvalidTransition("Settlement does not independently match the claim and order")
            buyer_digest = identity_digest(identity_hash_secret, order["mobile_e164"])
            identity_matches = hmac.compare_digest(row["payer_identity_digest"], buyer_digest)
            if identity_matches and third_party_exception_id is not None:
                raise InvalidTransition("Third-party exception is not needed for a buyer-paid transfer")
            if not identity_matches:
                if not third_party_exception_id:
                    raise InvalidTransition("Documented founder exception is required for third-party payer")
                exception = db.execute(text("""
                    SELECT id FROM production_third_party_payer_exceptions
                     WHERE id = :id AND order_id = :order_id AND claim_id = :claim_id
                       AND evidence_id = :evidence_id
                """), {"id": third_party_exception_id, "order_id": order["order_id"],
                       "claim_id": claim_id, "evidence_id": evidence_id}).first()
                if exception is None:
                    raise InvalidTransition("Matching third-party exception is required")
            decision_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO production_founder_approval_decisions
                  (id, order_id, claim_id, evidence_id, decision, founder_id, reason)
                VALUES (:id, :order_id, :claim_id, :evidence_id, 'APPROVE', :founder, :reason)
            """), {"id": decision_id, "order_id": order["order_id"],
                   "claim_id": claim_id, "evidence_id": evidence_id,
                   "founder": actor, "reason": reason.strip()})
            if fulfillment_mode == "website_download":
                # Deferred channel retained for a separately reviewed release.
                db.execute(text("""
                    UPDATE production_payment_fulfillment_state
                       SET payment_status = 'PAYMENT_CONFIRMED',
                           fulfillment_status = 'READY_TO_DOWNLOAD'
                     WHERE order_id = :order_id
                """), {"order_id": order["order_id"]})
                grant_id = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO production_download_grants
                      (id, order_id, approval_decision_id, approval_kind, grant_status)
                    VALUES (:id, :order_id, :decision_id, 'APPROVE', 'ACTIVE')
                """), {"id": grant_id, "order_id": order["order_id"],
                       "decision_id": decision_id})
            else:
                # V1 approval confirms settlement but creates no website grant.
                # Manual Telegram delivery is tracked in its own audited table.
                db.execute(text("""
                    UPDATE production_payment_fulfillment_state
                       SET payment_status = 'PAYMENT_CONFIRMED'
                     WHERE order_id = :order_id
                """), {"order_id": order["order_id"]})
                db.execute(text("""
                    INSERT INTO production_manual_deliveries(order_id, status, updated_by)
                    VALUES (:order_id, 'PENDING', :founder)
                """), {"order_id": order["order_id"], "founder": actor})
                db.execute(text("""
                    INSERT INTO production_manual_delivery_events(order_id, old_status, new_status, actor_id)
                    VALUES (:order_id, NULL, 'PENDING', :founder)
                """), {"order_id": order["order_id"], "founder": actor})
                grant_id = None
            db.execute(text("""
                UPDATE production_payment_claims SET claim_status = 'APPROVED'
                 WHERE id = :id
            """), {"id": claim_id})
            _audit(db, order_id=order["order_id"], event_type="PAYMENT_APPROVED",
                   actor_type="FOUNDER", actor_id=actor,
                   event_data={"claim_id": claim_id, "evidence_id": evidence_id,
                               "decision_id": decision_id, "fulfillment_mode": fulfillment_mode,
                               "grant_id": grant_id})
            return grant_id
    except IntegrityError as exc:
        if "unique" in str(exc).lower():
            raise InvalidTransition("A conflicting or repeated decision already exists") from None
        raise


def reject_payment(
    db: Session, *, actor_id: str | None, order_code: str, claim_id: str,
    reason: str, evidence_id: str | None = None,
) -> None:
    actor = _founder(actor_id)
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
        raise ValueError("A rejection reason is required")
    with db.begin():
        order = _locked_order_state(db, order_code)
        if order["payment_status"] != "UNDER_REVIEW":
            raise InvalidTransition("Order is not awaiting a founder decision")
        claim = db.execute(text("""
            SELECT id FROM production_payment_claims
             WHERE id = :claim_id AND order_id = :order_id FOR UPDATE
        """), {"claim_id": claim_id, "order_id": order["order_id"]}).first()
        if claim is None:
            raise InvalidTransition("Claim does not belong to this order")
        if evidence_id is not None:
            evidence = db.execute(text("""
                SELECT id FROM production_settlement_evidence
                 WHERE id = :evidence_id AND order_id = :order_id AND claim_id = :claim_id
            """), {"evidence_id": evidence_id, "order_id": order["order_id"],
                   "claim_id": claim_id}).first()
            if evidence is None:
                raise InvalidTransition("Evidence does not belong to this claim")
        decision_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO production_founder_approval_decisions
              (id, order_id, claim_id, evidence_id, decision, founder_id, reason)
            VALUES (:id, :order_id, :claim_id, :evidence_id, 'REJECT', :founder, :reason)
        """), {"id": decision_id, "order_id": order["order_id"],
               "claim_id": claim_id, "evidence_id": evidence_id,
               "founder": actor, "reason": reason.strip()})
        db.execute(text("""
            UPDATE production_payment_claims SET claim_status = 'REJECTED' WHERE id = :id
        """), {"id": claim_id})
        db.execute(text("""
            UPDATE production_payment_fulfillment_state
               SET payment_status = 'PAYMENT_REJECTED' WHERE order_id = :order_id
        """), {"order_id": order["order_id"]})
        _audit(db, order_id=order["order_id"], event_type="PAYMENT_REJECTED",
               actor_type="FOUNDER", actor_id=actor,
               event_data={"claim_id": claim_id, "decision_id": decision_id})


def revoke_download_grant(
    db: Session, *, actor_id: str | None, order_code: str, reason: str,
) -> None:
    actor = _founder(actor_id)
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
        raise ValueError("A revocation reason is required")
    with db.begin():
        order = _locked_order_state(db, order_code)
        if order["payment_status"] != "PAYMENT_CONFIRMED" or order["fulfillment_status"] != "READY_TO_DOWNLOAD":
            raise InvalidTransition("Order has no active approved delivery")
        grant = db.execute(text("""
            SELECT id FROM production_download_grants
             WHERE order_id = :order_id AND grant_status = 'ACTIVE' FOR UPDATE
        """), {"order_id": order["order_id"]}).first()
        if grant is None:
            raise InvalidTransition("Active grant not found")
        db.execute(text("""
            UPDATE production_payment_fulfillment_state
               SET fulfillment_status = 'REVOKED' WHERE order_id = :order_id
        """), {"order_id": order["order_id"]})
        db.execute(text("""
            UPDATE production_download_grants
               SET grant_status = 'REVOKED', revoked_at = now(),
                   revoked_by = :actor, revoke_reason = :reason
             WHERE id = :id
        """), {"id": grant.id, "actor": actor, "reason": reason.strip()})
        _audit(db, order_id=order["order_id"], event_type="DOWNLOAD_GRANT_REVOKED",
               actor_type="FOUNDER", actor_id=actor,
               event_data={"grant_id": str(grant.id)})


def authorize_download(
    db: Session, *, order_code: str, access_token: str, token_secret: str,
) -> str:
    """Return order UUID only if token, approval state and active grant all match."""
    if len(token_secret) < 32:
        raise ValueError("Order token configuration is invalid")
    with db.begin():
        row = db.execute(text("""
            SELECT o.id, o.access_hash, s.payment_status, s.fulfillment_status, g.id AS grant_id
              FROM production_orders o
              JOIN production_payment_fulfillment_state s ON s.order_id = o.id
              JOIN production_download_grants g ON g.order_id = o.id
             WHERE o.code = :code AND g.grant_status = 'ACTIVE'
             FOR UPDATE OF o, s, g
        """), {"code": order_code}).mappings().first()
        presented = hmac_digest(token_secret, "stored:v1:" + (access_token or ""))
        if (row is None or not hmac.compare_digest(row["access_hash"], presented)
                or row["payment_status"] != "PAYMENT_CONFIRMED"
                or row["fulfillment_status"] != "READY_TO_DOWNLOAD"):
            raise DownloadDenied("Download not available")
        return row["id"]
