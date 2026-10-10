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