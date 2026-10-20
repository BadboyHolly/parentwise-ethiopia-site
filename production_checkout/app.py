"""Independent ParentWise order intake. No payment approval, receipts or PDF delivery.

This package MUST NOT run against the QA database. Real order intake is
separate from funds settlement, identity verification and fulfillment.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import CheckConstraint, DateTime, Integer, String, create_engine, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

PRODUCT = "ParentWise Ethiopia"
PRICE_ETB = 1500
CURRENCY = "ETB"
# Builder-only sentinel values. Production must supply recipient details through
# private environment configuration; staging always injects fictional QA values.
ACCOUNTS = {
    "telebirr": {"name": "Telebirr", "number": "NOT-CONFIGURED", "holder": "NOT-CONFIGURED"},
    "bank": {"name": "Commercial Bank of Ethiopia", "number": "NOT-CONFIGURED", "holder": "NOT-CONFIGURED"},
}
ORDER_PATTERN = re.compile(r"^PW-[0-9A-F]{24}$")
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "production_orders"
    __table_args__ = (
        CheckConstraint("amount_etb = 1500", name="ck_prod_order_amount"),
        CheckConstraint("currency = 'ETB'", name="ck_prod_order_currency"),
        CheckConstraint("method IN ('telebirr','bank')", name="ck_prod_order_method"),
        CheckConstraint("status = 'AWAITING_PAYMENT'", name="ck_prod_order_unverified"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mobile_e164: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_etb: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    access_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CreateOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    customer_name: str = Field(min_length=2, max_length=100)
    mobile: str = Field(min_length=10, max_length=13)
    payment_method: Literal["telebirr", "bank"]

    @field_validator("customer_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or any(ord(c) < 32 for c in value):
            raise ValueError("Enter a valid name")
        return value

    @field_validator("mobile")
    @classmethod
    def normalize_mobile(cls, value: str) -> str:
        if re.fullmatch(r"0[97][0-9]{8}", value, flags=re.ASCII):
            return "+251" + value[1:]
        if re.fullmatch(r"\+251[97][0-9]{8}", value, flags=re.ASCII):
            return value
        raise ValueError("Use a valid Ethiopian mobile: 09…, 07… or +251…")


def hmac_digest(secret: str, label: str) -> str:
    return hmac.new(secret.encode("utf-8"), label.encode("utf-8"), hashlib.sha256).hexdigest()


def private_token(secret: str, key: str) -> str:
    raw = hmac.new(secret.encode(), ("access:v1:" + key).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def check_key(key: str) -> None:
    if not IDEMPOTENCY_PATTERN.fullmatch(key or ""):
        raise HTTPException(400, "Invalid idempotency key")
    try:
        decoded = base64.urlsafe_b64decode(key + "=")
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid idempotency key") from None
    if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != key:
        raise HTTPException(400, "Invalid idempotency key")


def summary(order: Order, payment_accounts: dict[str, dict[str, str]] | None = None) -> dict:
    accounts = ACCOUNTS if payment_accounts is None else payment_accounts
    return {
        "order_id": order.code,
        "product": PRODUCT,
        "amount_etb": order.amount_etb,
        "currency": order.currency,
        "payment_method": order.method,
        "status": order.status,
        "created_at": (order.created_at if order.created_at.tzinfo else order.created_at.replace(tzinfo=timezone.utc)).isoformat(),
        "payment_instructions": {**accounts[order.method], "amount_etb": PRICE_ETB, "currency": CURRENCY},
    }


def build_app(
    *,
    database_url: str,
    token_secret: str,
    allowed_origins: list[str],
    intake_enabled: bool = False,
    allow_sqlite_for_tests: bool = False,
    payment_accounts: dict[str, dict[str, str]] | None = None,
) -> FastAPI:
    if len(token_secret) < 32:
        raise RuntimeError("A durable ORDER_TOKEN_KEY >= 32 characters is required")
    if not database_url.startswith("postgresql+psycopg://") and not (
        allow_sqlite_for_tests and database_url.startswith("sqlite://")
    ):
        raise RuntimeError("Production checkout requires a separate PostgreSQL database")
    if not allowed_origins or any(x == "*" or not (
        x.startswith("https://") or (allow_sqlite_for_tests and x.startswith("http://localhost"))
    ) for x in allowed_origins):
        raise RuntimeError("An explicit HTTPS allowed-origin list is required")
    accounts = ACCOUNTS if payment_accounts is None else payment_accounts
    if set(accounts) != {"telebirr", "bank"} or any(
        not isinstance(accounts[method], dict) or not {"name", "number", "holder"} <= set(accounts[method])
        for method in ("telebirr", "bank")
    ):
        raise RuntimeError("Both payment instruction records must be configured")
    accounts = {method: dict(value) for method, value in accounts.items()}

    engine_kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite://"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["connect_args"] = {"connect_timeout": 5}
    engine = create_engine(database_url, **engine_kwargs)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app = FastAPI(title="ParentWise Orders", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine
    app.state.sessions = sessions
    app.state.intake_enabled = intake_enabled
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def privacy_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.get("/healthz")
    def health():
        return {"service": "parentwise-order-intake", "order_intake_enabled": intake_enabled, "payment_verification_enabled": False}

    @app.get("/readyz")
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                # Migration must have created this independently. No runtime create_all.
                conn.execute(text("SELECT 1 FROM production_orders LIMIT 1"))
            return {"database": "ready"}
        except SQLAlchemyError:
            raise HTTPException(503, "Order storage is unavailable") from None

    @app.post("/api/v1/orders", status_code=201)
    def create_order(
        item: CreateOrder, request: Request,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ):
        if not intake_enabled:
            raise HTTPException(503, "Order intake has not opened")
        check_key(idempotency_key)
        idem_hash = hmac_digest(token_secret, "idempotency:v1:" + idempotency_key)
        token = private_token(token_secret, idempotency_key)
        fingerprint = hmac_digest(
            token_secret,
            "payload:v1:" + json.dumps(item.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        )
        try:
            with sessions() as db:
                if db.bind.dialect.name == "postgresql":
                    advisory = int.from_bytes(bytes.fromhex(idem_hash)[:8], "big", signed=True)
                    db.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": advisory})
                existing = db.scalar(select(Order).where(Order.idempotency_hash == idem_hash))
                if existing:
                    if not hmac.compare_digest(existing.request_fingerprint, fingerprint):
                        raise HTTPException(409, "This retry key belongs to different order details")
                    return {"order": summary(existing, accounts), "access_token": token}
                record = Order(
                    id=str(uuid.uuid4()), code="PW-" + secrets.token_hex(12).upper(),
                    customer_name=item.customer_name, mobile_e164=item.mobile,
                    method=item.payment_method, amount_etb=PRICE_ETB, currency=CURRENCY,
                    status="AWAITING_PAYMENT", idempotency_hash=idem_hash,
                    request_fingerprint=fingerprint, access_hash=hmac_digest(token_secret, "stored:v1:" + token),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(record)
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    # Collision/failure never creates an independently accepted order.
                    raise HTTPException(503, "Order could not be saved; retry with the same key") from None
                return {"order": summary(record, accounts), "access_token": token}
        except HTTPException:
            raise
        except SQLAlchemyError:
            raise HTTPException(503, "Order storage is temporarily unavailable") from None

    @app.get("/api/v1/orders/{code}")
    def retrieve_order(code: str, authorization: str = Header(default="")):
        if not ORDER_PATTERN.fullmatch(code):
            raise HTTPException(404, "Order not found")
        if not authorization.startswith("Bearer "):
            raise HTTPException(404, "Order not found")
        token = authorization[7:]
        if not IDEMPOTENCY_PATTERN.fullmatch(token):
            raise HTTPException(404, "Order not found")
        try:
            with sessions() as db:
                record = db.scalar(select(Order).where(Order.code == code))
                digest = hmac_digest(token_secret, "stored:v1:" + token)
                if record is None or not hmac.compare_digest(record.access_hash, digest):
                    raise HTTPException(404, "Order not found")
                return {"order": summary(record)}
        except HTTPException:
            raise
        except SQLAlchemyError:
            raise HTTPException(503, "Order storage is temporarily unavailable") from None

    return app


def from_environment() -> FastAPI:
    if os.getenv("APP_MODE", "") != "production":
        raise RuntimeError("This independent API requires explicit APP_MODE=production")
    if os.getenv("PAYMENTS_ENABLED", "false").lower() != "false":
        raise RuntimeError("Payment verification is not implemented in this service")
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    accounts = {
        "telebirr": {"name":"Telebirr","number":os.getenv("TELEBIRR_ACCOUNT_NUMBER",""),
                     "holder":os.getenv("TELEBIRR_ACCOUNT_HOLDER","")},
        "bank": {"name":"Commercial Bank of Ethiopia","number":os.getenv("CBE_ACCOUNT_NUMBER",""),
                 "holder":os.getenv("CBE_ACCOUNT_HOLDER","")},
    }
    if any(not value for account in accounts.values() for value in account.values()):
        raise RuntimeError("Private settlement recipient configuration is required")
    app = build_app(
        database_url=database_url,
        token_secret=os.getenv("ORDER_TOKEN_KEY", ""),
        allowed_origins=[x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()],
        intake_enabled=os.getenv("ORDER_INTAKE_ENABLED", "false").lower() == "true",
        payment_accounts=accounts,
    )
    founder_auth_enabled = os.getenv("FOUNDER_AUTH_ENABLED", "false").lower() == "true"
    founder_approval_enabled = os.getenv("FOUNDER_APPROVAL_ENABLED", "false").lower() == "true"
    if founder_approval_enabled and not founder_auth_enabled:
        raise RuntimeError("Founder approval requires authenticated founder sessions")
    app.state.founder_auth_enabled = founder_auth_enabled
    app.state.founder_approval_enabled = False
    app.state.customer_claims_enabled = False
    app.state.secure_delivery_enabled = False
    founder_config = None
    if founder_auth_enabled:
        from .founder_security import FounderConfig, create_founder_router
        founder_config = FounderConfig.from_environment(payment_accounts=accounts)
        app.state.founder_config = founder_config
        app.include_router(create_founder_router(app.state.sessions, founder_config))
        app.state.founder_approval_enabled = founder_config.approvals_enabled

    # The production customer workflow is fail-closed. It is mounted only when
    # every independently controlled gate is explicitly enabled and the founder
    # workflow is authenticated and approval-capable. No QA settlement adapter
    # or credentials are imported here.
    claims_enabled = os.getenv("CUSTOMER_PAYMENT_CLAIMS_ENABLED", "false").lower() == "true"
    delivery_enabled = os.getenv("SECURE_PDF_DELIVERY_ENABLED", "false").lower() == "true"
    if claims_enabled or delivery_enabled:
        if not (claims_enabled and delivery_enabled and founder_config
                and founder_config.approvals_enabled):
            raise RuntimeError("Customer claims and delivery require both gates and founder approval")
        from .customer_delivery import CustomerDeliveryConfig, create_customer_delivery_router
        from .private_storage import ProductManifest, R2PrivateObjectStore, R2Settings
        manifest_raw = os.getenv("PRODUCT_PDF_MANIFEST_JSON", "")
        manifest = ProductManifest.from_json(manifest_raw)
        r2_settings = R2Settings.from_environment()
        object_store = R2PrivateObjectStore.from_environment()
        app.include_router(create_customer_delivery_router(
            app.state.sessions,
            CustomerDeliveryConfig(
                token_secret=os.getenv("ORDER_TOKEN_KEY", ""),
                rate_key=os.getenv("CUSTOMER_RATE_LIMIT_KEY", ""),
                founder_config=founder_config,
                bucket=r2_settings.bucket,
                manifest=manifest,
                object_store=object_store,
                max_object_bytes=r2_settings.max_object_bytes,
            ),
        ))
        app.state.customer_claims_enabled = True
        app.state.secure_delivery_enabled = True
    return app
