"""Founder-only Telegram delivery recording and non-PII operational metrics."""
from __future__ import annotations

import re
from sqlalchemy import text
from sqlalchemy.orm import Session


class ManualDeliveryError(RuntimeError):
    pass


_FOUNDER = re.compile(r"^[A-Za-z0-9._@-]{1,80}$")
_ORDER = re.compile(r"^PW-[0-9A-F]{24}$")
_TRANSITIONS = {
    "PENDING": {"PREPARING"},
    "PREPARING": {"SENT", "FAILED"},
    "SENT": {"DELIVERED", "FAILED"},
    "FAILED": {"PREPARING"},
    "DELIVERED": set(),
}


def record_manual_delivery(db: Session, *, actor_id: str, order_code: str, new_status: str) -> str:
    if not _FOUNDER.fullmatch(actor_id or "") or not _ORDER.fullmatch(order_code or ""):
        raise ManualDeliveryError("Invalid founder or order")
    if new_status not in _TRANSITIONS:
        raise ManualDeliveryError("Invalid delivery state")
    with db.begin():
        row = db.execute(text("""
            SELECT d.order_id, d.status, s.payment_status
              FROM production_manual_deliveries d
              JOIN production_payment_fulfillment_state s ON s.order_id=d.order_id
              JOIN production_orders o ON o.id=d.order_id
             WHERE o.code=:code FOR UPDATE OF d, s
        """), {"code": order_code}).mappings().first()
        if row is None:
            raise ManualDeliveryError("Manual delivery record not found")
        old_status = row["status"]
        if row["payment_status"] != "PAYMENT_CONFIRMED":
            raise ManualDeliveryError("Independent founder payment approval is required")
        if new_status not in _TRANSITIONS[old_status]:
            raise ManualDeliveryError("Invalid manual delivery transition")
        db.execute(text("""
            UPDATE production_manual_deliveries
               SET status=:status, updated_by=:actor,
                   sent_at=CASE WHEN :status='SENT' THEN now() ELSE sent_at END,
                   delivered_at=CASE WHEN :status='DELIVERED' THEN now() ELSE delivered_at END,
                   updated_at=now()
             WHERE order_id=:order_id
        """), {"status": new_status, "actor": actor_id, "order_id": row["order_id"]})
        db.execute(text("""
            INSERT INTO production_manual_delivery_events(order_id, old_status, new_status, actor_id)
            VALUES (:order_id, :old, :new, :actor)
        """), {"order_id": row["order_id"], "old": old_status,
               "new": new_status, "actor": actor_id})
    return new_status


def manual_delivery_report(db: Session) -> dict[str, int]:
    """Verified revenue counts only founder-approved payment states."""
    row = db.execute(text("""
        SELECT count(*)::integer AS orders_total,
               count(*) FILTER (WHERE s.payment_status='AWAITING_PAYMENT')::integer AS awaiting_payment,
               count(*) FILTER (WHERE s.payment_status='UNDER_REVIEW')::integer AS under_review,
               count(*) FILTER (WHERE s.payment_status='PAYMENT_REJECTED')::integer AS payment_rejected,
               count(*) FILTER (WHERE s.payment_status='PAYMENT_CONFIRMED')::integer AS payment_verified,
               coalesce(sum(o.amount_etb) FILTER (WHERE s.payment_status='PAYMENT_CONFIRMED'),0)::integer AS verified_revenue_etb,
               count(*) FILTER (WHERE d.status='PENDING')::integer AS delivery_pending,
               count(*) FILTER (WHERE d.status='PREPARING')::integer AS delivery_preparing,
               count(*) FILTER (WHERE d.status='SENT')::integer AS delivery_sent,
               count(*) FILTER (WHERE d.status='DELIVERED')::integer AS delivery_delivered,
               count(*) FILTER (WHERE d.status='FAILED')::integer AS delivery_failed
          FROM production_orders o
          JOIN production_payment_fulfillment_state s ON s.order_id=o.id
          LEFT JOIN production_manual_deliveries d ON d.order_id=o.id
    """)).mappings().one()
    return {key: int(value) for key, value in row.items()}
