"""PostgreSQL-only production payment state and authorization tests.

Run only against TEST_DATABASE_URL pointing at a disposable database with
migrations 0001 and 0002 applied.
"""
from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from production_checkout.app import hmac_digest, private_token
from production_checkout.payment_state import (
    DuplicateReference, DownloadDenied, InvalidTransition, UnauthorizedFounder,
    approve_payment, authorize_download, document_third_party_exception,
    identity_digest, record_settlement_evidence, reject_payment,
    revoke_download_grant, submit_payment_claim, transaction_reference_digest,
)

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="requires disposable PostgreSQL")
TOKEN_SECRET = "disposable-order-token-secret-" + "x" * 32
REFERENCE_SECRET = "disposable-reference-hash-key-" + "x" * 32
IDENTITY_SECRET = "disposable-identity-hash-key-" + "x" * 32
RECIPIENT_SECRET = "disposable-recipient-hash-key-" + "x" * 32
FOUNDER = "qa-founder-synthetic"
RECIPIENT = hmac_digest(RECIPIENT_SECRET, "recipient:v1:fictional-recipient")


@pytest.fixture(scope="session")
def engine():
    value = create_engine(DATABASE_URL, pool_pre_ping=True)
    yield value
    value.dispose()


@pytest.fixture(autouse=True)
def clean_db(engine):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE production_orders CASCADE"))
    yield
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE production_orders CASCADE"))


def order(engine, mobile="+251912345678"):
    order_id = str(uuid4())
    code = "PW-" + uuid4().hex[:24].upper()
    idempotency = secrets.token_hex(32)
    token = private_token(TOKEN_SECRET, secrets.token_urlsafe(32))
    access_hash = hmac_digest(TOKEN_SECRET, "stored:v1:" + token)
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO production_orders
              (id, code, customer_name, mobile_e164, method, amount_etb, currency, status,
               idempotency_hash, request_fingerprint, access_hash, created_at)
            VALUES (:id, :code, 'QA Synthetic Parent', :mobile, 'telebirr', 1500, 'ETB',
                    'AWAITING_PAYMENT', :idem, :fingerprint, :access_hash, now())
        """), {"id": order_id, "code": code, "mobile": mobile,
               "idem": idempotency, "fingerprint": secrets.token_hex(32),
               "access_hash": access_hash})
    return code, token


def session(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)()


def claim(engine, code, token, reference):
    with session(engine) as db:
        claim_id = submit_payment_claim(
            db, order_code=code, access_token=token, token_secret=TOKEN_SECRET,
            reference_hash_secret=REFERENCE_SECRET, transaction_reference=reference,
            reference_ciphertext="enc:v1:synthetic-ciphertext",
        )
    return claim_id


def evidence(engine, code, claim_id, *, reference=None, method="telebirr",
             amount=1500, currency="ETB", recipient=RECIPIENT, payer_mobile="+251912345678"):
    ref = reference or "SIM-" + secrets.token_hex(12).upper()
    if reference is None:
        with engine.connect() as connection:
            ref_digest = connection.execute(text("""
                SELECT reference_digest FROM production_payment_claims WHERE id=:claim_id
            """), {"claim_id": claim_id}).scalar_one()
    else:
        ref_digest = transaction_reference_digest(REFERENCE_SECRET, ref)
    with session(engine) as db:
        evidence_id = record_settlement_evidence(
            db, actor_id=FOUNDER, order_code=code, claim_id=claim_id,
            reference_digest=ref_digest, payment_method=method, amount_etb=amount,
            currency=currency, recipient_digest=recipient,
            payer_identity_digest=identity_digest(IDENTITY_SECRET, payer_mobile),
            evidence_source="TELEBIRR_PORTAL",
            settled_at=datetime.now(timezone.utc),
        )
    return evidence_id, ref


def approve(engine, code, claim_id, evidence_id, *, exception_id=None, actor=FOUNDER):
    with session(engine) as db:
        return approve_payment(
            db, actor_id=actor, order_code=code, claim_id=claim_id,
            evidence_id=evidence_id, reason="Independently matched synthetic settlement",
            token_secret=TOKEN_SECRET, reference_hash_secret=REFERENCE_SECRET,
            identity_hash_secret=IDENTITY_SECRET, expected_recipient_digest=RECIPIENT,
            third_party_exception_id=exception_id,
        )


def test_approved_match_creates_single_active_grant_and_authorizes_original_token(engine):
    code, token = order(engine)
    claim_id = claim(engine, code, token, "SIM-" + secrets.token_hex(12).upper())
    evidence_id, _ = evidence(engine, code, claim_id)
    grant_id = approve(engine, code, claim_id, evidence_id)
    with session(engine) as db:
        authorized_order = authorize_download(
            db, order_code=code, access_token=token, token_secret=TOKEN_SECRET)
    assert authorized_order
    with engine.connect() as connection:
        state = connection.execute(text("""
            SELECT payment_status, fulfillment_status FROM production_payment_fulfillment_state
             WHERE order_id = (SELECT id FROM production_orders WHERE code=:code)
        """), {"code": code}).one()
        grant = connection.execute(text("""
            SELECT id, grant_status FROM production_download_grants
             WHERE order_id = (SELECT id FROM production_orders WHERE code=:code)
        """), {"code": code}).one()
        assert tuple(state) == ("PAYMENT_CONFIRMED", "READY_TO_DOWNLOAD")
        assert tuple(grant) == (grant_id, "ACTIVE")


def test_claim_token_is_checked_and_reference_is_globally_unique(engine):
    code1, token1 = order(engine)
    code2, token2 = order(engine)
    with session(engine) as db:
        with pytest.raises(DownloadDenied):
            submit_payment_claim(
                db, order_code=code1, access_token=token2, token_secret=TOKEN_SECRET,
                reference_hash_secret=REFERENCE_SECRET, transaction_reference="SIM-WRONGTOKEN",
                reference_ciphertext="enc:v1:ciphertext",
            )
    claim(engine, code1, token1, "SIM-GLOBAL-DUPLICATE")
    with pytest.raises(DuplicateReference):
        claim(engine, code2, token2, "sim-global-duplicate")


def test_settlement_reference_cannot_be_reused_for_a_different_claim(engine):
    code1, token1 = order(engine)
    code2, token2 = order(engine)
    claim1 = claim(engine, code1, token1, "SIM-CLAIM-ONE-" + secrets.token_hex(4))
    claim2 = claim(engine, code2, token2, "SIM-CLAIM-TWO-" + secrets.token_hex(4))
    shared_settlement_ref = "SIM-SETTLEMENT-GLOBAL-" + secrets.token_hex(4)
    evidence(engine, code1, claim1, reference=shared_settlement_ref)
    with pytest.raises(DuplicateReference):
        evidence(engine, code2, claim2, reference=shared_settlement_ref)


def test_third_party_payment_requires_documented_founder_exception(engine):
    code, token = order(engine)
    claim_id = claim(engine, code, token, "SIM-RELATIVE-" + secrets.token_hex(4))
    evidence_id, _ = evidence(engine, code, claim_id, payer_mobile="+251911111111")
    with pytest.raises(InvalidTransition, match="exception"):
        approve(engine, code, claim_id, evidence_id)
    with session(engine) as db:
        exception_id = document_third_party_exception(
            db, actor_id=FOUNDER, order_code=code, claim_id=claim_id,
            evidence_id=evidence_id, relationship="SPOUSE",
            rationale="Customer confirmed spouse paid from their account",
            identity_hash_secret=IDENTITY_SECRET,
        )
    assert approve(engine, code, claim_id, evidence_id, exception_id=exception_id)


@pytest.mark.parametrize("mismatch", ["reference", "method", "amount", "currency", "recipient"])
def test_approval_requires_every_independent_settlement_field(engine, mismatch):
    code, token = order(engine)
    reference = "SIM-MATCH-" + secrets.token_hex(4)
    claim_id = claim(engine, code, token, reference)
    observed_ref = "SIM-OTHER-" + secrets.token_hex(4) if mismatch == "reference" else reference
    options = {
        "method": "bank" if mismatch == "method" else "telebirr",
        "amount": 1400 if mismatch == "amount" else 1500,
        "currency": "USD" if mismatch == "currency" else "ETB",
        "recipient": hmac_digest(RECIPIENT_SECRET, "recipient:v1:wrong") if mismatch == "recipient" else RECIPIENT,
    }
    evidence_id, _ = evidence(engine, code, claim_id, reference=observed_ref, **options)
    with pytest.raises(InvalidTransition, match="match"):
        approve(engine, code, claim_id, evidence_id)


def test_unauthorized_founder_and_repeated_or_conflicting_decisions_are_denied(engine):
    code, token = order(engine)
    claim_id = claim(engine, code, token, "SIM-AUTH-" + secrets.token_hex(4))
    evidence_id, _ = evidence(engine, code, claim_id)
    with pytest.raises(UnauthorizedFounder):
        approve(engine, code, claim_id, evidence_id, actor=None)
    approve(engine, code, claim_id, evidence_id)
    with pytest.raises(InvalidTransition):
        approve(engine, code, claim_id, evidence_id)
    with session(engine) as db:
        with pytest.raises(InvalidTransition):
            reject_payment(db, actor_id=FOUNDER, order_code=code, claim_id=claim_id,
                           reason="Conflicting second decision")


def test_rejection_does_not_grant_and_allows_a_new_claim(engine):
    code, token = order(engine)
    claim_id = claim(engine, code, token, "SIM-REJECT-" + secrets.token_hex(4))
    with session(engine) as db:
        reject_payment(db, actor_id=FOUNDER, order_code=code, claim_id=claim_id,
                       reason="Independent evidence was not available")
    with engine.connect() as connection:
        state = connection.execute(text("""
            SELECT payment_status, fulfillment_status FROM production_payment_fulfillment_state
             WHERE order_id=(SELECT id FROM production_orders WHERE code=:code)
        """), {"code": code}).one()
        assert tuple(state) == ("PAYMENT_REJECTED", "LOCKED")
        assert connection.execute(text("SELECT count(*) FROM production_download_grants")).scalar_one() == 0
    assert claim(engine, code, token, "SIM-RETRY-" + secrets.token_hex(4))


def test_concurrent_duplicate_reference_claim_only_commits_once(engine):
    first = order(engine)
    second = order(engine)
    ref = "SIM-RACE-" + secrets.token_hex(8)
    def submit(record):
        code, token = record
        try:
            return claim(engine, code, token, ref)
        except DuplicateReference:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, [first, second]))
    assert sum(value is not None for value in results) == 1


def test_concurrent_approval_issues_exactly_one_grant(engine):
    code, token = order(engine)
    claim_id = claim(engine, code, token, "SIM-APPROVAL-RACE-" + secrets.token_hex(4))
    evidence_id, _ = evidence(engine, code, claim_id)
    def run():
        try:
            return approve(engine, code, claim_id, evidence_id)
        except InvalidTransition:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        grants = list(executor.map(lambda _: run(), range(2)))
    assert sum(value is not None for value in grants) == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM production_download_grants")).scalar_one() == 1
        assert connection.execute(text("""
            SELECT count(*) FROM production_founder_approval_decisions
             WHERE decision='APPROVE'
        """)).scalar_one() == 1


def test_revocation_denies_future_access_and_grant_cannot_be_reactivated(engine):
    code, token = order(engine)
    claim_id = claim(engine, code, token, "SIM-REVOKE-" + secrets.token_hex(4))
    evidence_id, _ = evidence(engine, code, claim_id)
    approve(engine, code, claim_id, evidence_id)
    with session(engine) as db:
        assert authorize_download(db, order_code=code, access_token=token,
                                  token_secret=TOKEN_SECRET)
    with session(engine) as db:
        revoke_download_grant(db, actor_id=FOUNDER, order_code=code,
                              reason="Customer support requested access revocation")
    with session(engine) as db:
        with pytest.raises(DownloadDenied):
            authorize_download(db, order_code=code, access_token=token,
                              token_secret=TOKEN_SECRET)
    with engine.begin() as connection:
        with pytest.raises(DBAPIError):
            with connection.begin_nested():
                connection.execute(text("""
                    UPDATE production_download_grants SET grant_status='ACTIVE',
                      revoked_at=NULL, revoked_by=NULL, revoke_reason=NULL
                     WHERE order_id=(SELECT id FROM production_orders WHERE code=:code)
                """), {"code": code})


def test_database_rejects_ready_state_without_decision_and_audit_is_append_only(engine):
    code, _ = order(engine)
    with engine.connect() as connection:
        order_id = connection.execute(text(
            "SELECT id FROM production_orders WHERE code=:code"), {"code": code}).scalar_one()
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text("""
                UPDATE production_payment_fulfillment_state
                   SET payment_status='PAYMENT_CONFIRMED',
                       fulfillment_status='READY_TO_DOWNLOAD' WHERE order_id=:id
            """), {"id": order_id})
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO production_payment_audit_events(order_id,event_type,actor_type)
            VALUES (:id,'QA_TEST_EVENT','SYSTEM')
        """), {"id": order_id})
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text("""
                UPDATE production_payment_audit_events SET event_type='ALTERED'
                 WHERE event_type='QA_TEST_EVENT'
            """))


def test_order_table_remains_awaiting_payment_only(engine):
    code, _ = order(engine)
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text("""
                UPDATE production_orders SET status='PAYMENT_CONFIRMED' WHERE code=:code
            """), {"code": code})
