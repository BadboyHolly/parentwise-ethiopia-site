"""Sidecar state for the isolated integration run, separate from production order state."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class StagingBase(DeclarativeBase):
    pass

class OrderState(StagingBase):
    __tablename__ = "staging_order_states"
    order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"), primary_key=True)
    order_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="AWAITING_PAYMENT")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class PaymentClaim(StagingBase):
    __tablename__ = "staging_payment_claims"
    __table_args__ = (UniqueConstraint("reference", name="uq_staging_claim_reference"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False)
    reference: Mapped[str] = mapped_column(String(48), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    reported_amount_etb: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="SUBMITTED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class SimulatedSettlement(StagingBase):
    __tablename__ = "staging_simulated_settlements"
    reference: Mapped[str] = mapped_column(String(48), primary_key=True)
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_etb: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    recipient_code: Mapped[str] = mapped_column(String(40), nullable=False)
    payer_mobile: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class DownloadGrant(StagingBase):
    __tablename__ = "staging_download_grants"
    order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    package_version: Mapped[str] = mapped_column(String(32), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class AuditEvent(StagingBase):
    __tablename__ = "staging_audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("production_orders.id", ondelete="CASCADE"))
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class FounderSession(StagingBase):
    __tablename__ = "staging_founder_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class RateWindow(StagingBase):
    __tablename__ = "staging_rate_windows"
    bucket_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
