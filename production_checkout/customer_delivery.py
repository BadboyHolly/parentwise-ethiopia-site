"""Feature-gated customer claim, status, and private PDF download routes.

All customer access uses the original private order token. Claims are claims
only; they never mark settlement as paid. Downloads are authenticated backend
responses and reauthorize payment plus grant on every file request.
"""
from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from .app import hmac_digest
from .founder_encryption import encrypt_claim_reference
from .founder_security import FounderConfig
from .payment_state import (
    DownloadDenied, DuplicateReference, InvalidTransition, OrderNotFound,
    submit_payment_claim, authorize_download,
)
from .private_storage import ProductManifest, StorageUnavailable, fetch_verified_part


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    transaction_reference: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_ -]{2,127}$")


@dataclass(frozen=True)
class CustomerDeliveryConfig:
    token_secret: str
    rate_key: str
    founder_config: FounderConfig
    bucket: str
    manifest: ProductManifest
    object_store: object
    rate_limit: int = 20
    max_object_bytes: int = 25 * 1024 * 1024


def create_customer_delivery_router(
    sessions: sessionmaker,
    cfg: CustomerDeliveryConfig,
) -> APIRouter:
    if len(cfg.token_secret) < 32 or len(cfg.rate_key) < 32:
        raise RuntimeError("Customer delivery keys are not configured")
    if set(cfg.manifest._files) != {1, 2, 3, 4, 5}:
        raise RuntimeError("Customer delivery requires exactly five product files")
    router = APIRouter(prefix="/api/v1/orders/{code}", tags=["customer-private"])

    def authorize_token(code: str, authorization: str) -> str:
        if (not re.fullmatch(r"PW-[0-9A-F]{24}", code or "") or
                not authorization.startswith("Bearer ")):
            raise HTTPException(404, "Order not found")
        token = authorization[7:]
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise HTTPException(404, "Order not found")
        return token

    def consume_limit(db, request: Request, code: str, scope: str) -> None:
        ip = request.client.host if request.client else "unknown"
        # No raw IP, token or order authorization is stored.
        key = hmac_digest(cfg.rate_key, "customer:" + scope + ":" + code + ":" + ip)
        row = db.execute(text("""
            INSERT INTO production_customer_rate_limits (bucket_hash, window_started_at, attempts)
            VALUES (:key, date_trunc('minute', now()), 1)
            ON CONFLICT (bucket_hash) DO UPDATE SET
              attempts = CASE
                WHEN production_customer_rate_limits.window_started_at < date_trunc('minute', now()) THEN 1
                ELSE production_customer_rate_limits.attempts + 1 END,
              window_started_at = CASE
                WHEN production_customer_rate_limits.window_started_at < date_trunc('minute', now())
                THEN date_trunc('minute', now())
                ELSE production_customer_rate_limits.window_started_at END,
              updated_at = now()
            RETURNING attempts
        """), {"key": key}).scalar_one()
        if row > cfg.rate_limit:
            raise HTTPException(429, "Too many requests. Try again shortly.", headers={"Retry-After":"60"})

    def order_status(db, code: str, token: str) -> tuple[str, str]:
        record = db.execute(text("""
            SELECT o.access_hash, s.payment_status, s.fulfillment_status
              FROM production_orders o
              JOIN production_payment_fulfillment_state s ON s.order_id=o.id
             WHERE o.code=:code
        """), {"code": code}).mappings().first()
        presented = hmac_digest(cfg.token_secret, "stored:v1:" + token)
        if record is None or not hmac.compare_digest(record["access_hash"], presented):
            raise HTTPException(404, "Order not found")
        payment, delivery = record["payment_status"], record["fulfillment_status"]
        if payment == "AWAITING_PAYMENT":
            return ("Awaiting Payment", "Complete your transfer, then submit its reference.")
        if payment == "PAYMENT_REJECTED":
            return ("Awaiting Payment", "We could not match the submitted claim. Check your transfer details and submit a new reference.")
        if payment == "UNDER_REVIEW":
            return ("Under Review", "Your reference is a claim only. Payment remains unconfirmed while it is reviewed.")
        if payment == "PAYMENT_CONFIRMED" and delivery == "READY_TO_DOWNLOAD":
            return ("Ready to Download", "Your payment is confirmed. Your five downloads are available.")
        return ("Payment Confirmed", "Payment is confirmed, but download access is currently unavailable. Contact ParentWise support.")

    @router.post("/payment-claims", status_code=202)
    def submit_claim(code: str, request: Request, body: ClaimInput = Body(...),
                     authorization: str = Header(default="")):
        token = authorize_token(code, authorization)
        try:
            with sessions.begin() as db:
                consume_limit(db, request, code, "claim")
            ciphertext = encrypt_claim_reference(
                body.transaction_reference, cfg.founder_config, code)
            with sessions() as db:
                claim_id = submit_payment_claim(
                    db, order_code=code, access_token=token,
                    token_secret=cfg.token_secret,
                    reference_hash_secret=cfg.founder_config.reference_hash_secret,
                    transaction_reference=body.transaction_reference,
                    reference_ciphertext=ciphertext,
                )
            return {"claim_id": claim_id, "status": "Under Review",
                    "message": "Your reference was submitted as a payment claim. Payment is not confirmed yet."}
        except HTTPException:
            raise
        except DuplicateReference:
            raise HTTPException(409, "This transaction reference has already been submitted") from None
        except (DownloadDenied, OrderNotFound):
            raise HTTPException(404, "Order not found") from None
        except InvalidTransition:
            raise HTTPException(409, "This order cannot accept another payment claim") from None
        except Exception:
            raise HTTPException(503, "Payment claim could not be saved. Please retry shortly.") from None

    @router.get("/checkout-status")
    def checkout_status(code: str, request: Request, authorization: str = Header(default="")):
        token = authorize_token(code, authorization)
        try:
            with sessions.begin() as db:
                consume_limit(db, request, code, "status")
            with sessions() as db:
                status, message = order_status(db, code, token)
            return {"order_id": code, "status": status, "message": message}
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Order status is temporarily unavailable") from None

    for part in range(1, 6):
        def download(code: str, request: Request, authorization: str = Header(default=""), file_part: int = part):
            token = authorize_token(code, authorization)
            try:
                with sessions.begin() as db:
                    consume_limit(db, request, code, "download")
                with sessions() as db:
                    authorize_download(db, order_code=code, access_token=token,
                                       token_secret=cfg.token_secret)
                item, content = fetch_verified_part(
                    cfg.object_store, bucket=cfg.bucket, manifest=cfg.manifest,
                    part=file_part, max_bytes=cfg.max_object_bytes)
                return Response(
                    content=content, media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="parentwise-part-{file_part}.pdf"',
                        "Cache-Control": "private, no-store, max-age=0",
                        "Pragma": "no-cache",
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            except HTTPException:
                raise
            except (DownloadDenied, OrderNotFound):
                raise HTTPException(404, "Download not available") from None
            except StorageUnavailable:
                raise HTTPException(503, "Download is temporarily unavailable. Please retry.") from None
            except Exception:
                raise HTTPException(503, "Download is temporarily unavailable. Please retry.") from None
        router.add_api_route(
            f"/downloads/part-{part}.pdf", download, methods=["GET"],
            name=f"download_private_product_part_{part}",
            responses={200: {"content": {"application/pdf": {}}}},
        )
    return router
