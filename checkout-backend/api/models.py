from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (
        CheckConstraint('amount_etb = 1500', name='ck_order_price'),
        CheckConstraint("currency = 'ETB'", name='ck_order_currency'),
        CheckConstraint("payment_method IN ('telebirr','bank')", name='ck_payment_method'),
        CheckConstraint("status IN ('PENDING_PAYMENT','PROOF_SUBMITTED','VERIFYING','VERIFIED_PAID','CANCELLED')", name='ck_qa_order_state'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mobile_e164: Mapped[str] = mapped_column(String(16), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_etb: Mapped[int] = mapped_column(Integer, nullable=False, default=1500)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default='ETB')
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='PENDING_PAYMENT')
    idempotency_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    access_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index('ix_orders_created_at', Order.created_at)


class RateWindow(Base):
    __tablename__ = 'api_rate_windows'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class AdminSession(Base):
    __tablename__ = 'admin_sessions'
    session_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    credentials_version: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index('ix_admin_sessions_expires_at', AdminSession.expires_at)


class AdminTotpState(Base):
    __tablename__ = 'admin_totp_state'
    __table_args__ = (CheckConstraint('id = 1', name='ck_one_founder'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_accepted_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AdminAudit(Base):
    __tablename__ = 'admin_audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    success: Mapped[bool] = mapped_column(__import__('sqlalchemy').Boolean, nullable=False)
    order_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index('ix_admin_audit_created_at', AdminAudit.created_at)


class SimulatedLedgerEntry(Base):
    __tablename__ = 'qa_simulated_ledger'
    __table_args__ = (
        UniqueConstraint('payment_method', 'test_reference', name='uq_qa_ledger_ref'),
        CheckConstraint('amount_etb > 0', name='ck_qa_ledger_positive'),
        CheckConstraint("currency = 'ETB'", name='ck_qa_ledger_currency'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    test_reference: Mapped[str] = mapped_column(String(22), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_etb: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    credited_order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('orders.id'), unique=True, nullable=True)


class PaymentReview(Base):
    __tablename__ = 'qa_payment_reviews'
    __table_args__ = (
        UniqueConstraint('payment_method', 'test_reference', name='uq_qa_claim_reference'),
        CheckConstraint('reported_amount_etb > 0', name='ck_qa_claim_positive'),
        CheckConstraint("currency = 'ETB'", name='ck_qa_claim_currency'),
        CheckConstraint("state IN ('PROOF_SUBMITTED','VERIFYING','VERIFIED_PAID','REJECTED')", name='ck_qa_claim_state'),
        CheckConstraint("independent_check IN ('NOT_CHECKED','MATCHED','DISCREPANCY')", name='ck_qa_claim_independent'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey('orders.id'), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    test_reference: Mapped[str] = mapped_column(String(22), nullable=False)
    reported_amount_etb: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    independent_check: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(320), nullable=True)


Index('ix_qa_reviews_order', PaymentReview.order_id)


class PaymentEvent(Base):
    __tablename__ = 'qa_payment_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey('orders.id'), nullable=False)
    review_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('qa_payment_reviews.id'), nullable=True)
    actor: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(24), nullable=False)
    new_status: Mapped[str] = mapped_column(String(24), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(400), nullable=True)


Index('ix_qa_events_order', PaymentEvent.order_id, PaymentEvent.occurred_at)

class QaFulfillment(Base):
    __tablename__ = 'qa_fulfillments'
    __table_args__ = (
        CheckConstraint("state IN ('PENDING_FULFILLMENT','PREPARING','SENT','DELIVERED','DELIVERY_FAILED')",name='ck_qa_fulfillment_state'),
        CheckConstraint("package_version = 'QA-DEMO-2026.10-v1'",name='ck_qa_dummy_version'),
        CheckConstraint("delivery_channel = 'TELEGRAM_FOUNDER_ASSISTED_QA_SIMULATION'",name='ck_qa_dummy_channel'),
        CheckConstraint('attempt_count >= 0',name='ck_qa_attempt_positive'),
    )
    id: Mapped[str] = mapped_column(String(36),primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36),ForeignKey('orders.id'),nullable=False,unique=True)
    qa_review_id: Mapped[str] = mapped_column(String(36),ForeignKey('qa_payment_reviews.id'),nullable=False,unique=True)
    package_version: Mapped[str] = mapped_column(String(40),nullable=False)
    delivery_channel: Mapped[str] = mapped_column(String(50),nullable=False)
    state: Mapped[str] = mapped_column(String(24),nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    qa_ack_reference: Mapped[str | None] = mapped_column(String(23),unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

Index('ix_qa_fulfillments_state_created',QaFulfillment.state,QaFulfillment.created_at)


class QaFulfillmentEvent(Base):
    __tablename__ = 'qa_fulfillment_events'
    id: Mapped[str] = mapped_column(String(36),primary_key=True)
    fulfillment_id: Mapped[str] = mapped_column(String(36),ForeignKey('qa_fulfillments.id'),nullable=False)
    order_id: Mapped[str] = mapped_column(String(36),ForeignKey('orders.id'),nullable=False)
    action: Mapped[str] = mapped_column(String(60),nullable=False)
    from_state: Mapped[str] = mapped_column(String(24),nullable=False)
    to_state: Mapped[str] = mapped_column(String(24),nullable=False)
    actor: Mapped[str] = mapped_column(String(24),nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    qa_ack_reference: Mapped[str | None] = mapped_column(String(23))
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)

Index('ix_qa_fulfillment_events_fulfillment',QaFulfillmentEvent.fulfillment_id,QaFulfillmentEvent.happened_at)
