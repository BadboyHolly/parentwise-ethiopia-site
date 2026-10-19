"""Token, founder-session and audit helpers for the staging-only extension."""
import base64, hashlib, hmac, struct, time, uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from sqlalchemy import select
from production_checkout.app import Order, ORDER_PATTERN, IDEMPOTENCY_PATTERN, hmac_digest
from .models import FounderSession, AuditEvent

def utcnow():
    return datetime.now(timezone.utc)

def order_for_customer(db, code, authorization, token_secret):
    if not ORDER_PATTERN.fullmatch(code or "") or not (authorization or "").startswith("Bearer "):
        raise HTTPException(404, "Order not found")
    token = authorization[7:]
    if not IDEMPOTENCY_PATTERN.fullmatch(token):
        raise HTTPException(404, "Order not found")
    order = db.scalar(select(Order).where(Order.code == code))
    if order is None or not hmac.compare_digest(order.access_hash, hmac_digest(token_secret, "stored:v1:" + token)):
        raise HTTPException(404, "Order not found")
    return order

def totp_code(secret, timestamp=None):
    key = base64.b32decode(secret.upper() + "=" * ((8-len(secret) % 8) % 8))
    counter = int((timestamp if timestamp is not None else time.time()) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0f
    value = (struct.unpack(">I", digest[offset:offset+4])[0] & 0x7fffffff) % 1_000_000
    return f"{value:06d}"

def valid_totp(secret, submitted, timestamp=None):
    return any(hmac.compare_digest(totp_code(secret, (timestamp if timestamp is not None else time.time()) + drift*30), submitted or "")
               for drift in (-1, 0, 1))

def audit(db, order_id, actor, action, details="{}"):
    db.add(AuditEvent(id=str(uuid.uuid4()), order_id=order_id, actor=actor,
                      action=action, details=details, created_at=utcnow()))

def require_founder(request: Request, db, csrf_required=True):
    token = request.cookies.get("pw_stage_founder", "")
    csrf = request.headers.get("X-CSRF-Token", "")
    if not token:
        raise HTTPException(401, "Founder sign-in required")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = db.scalar(select(FounderSession).where(FounderSession.token_hash == token_hash))
    if session is None or session.revoked_at is not None or session.expires_at <= utcnow():
        raise HTTPException(401, "Founder session expired")
    if csrf_required:
        supplied = hashlib.sha256(csrf.encode()).hexdigest()
        if not csrf or not hmac.compare_digest(session.csrf_hash, supplied):
            raise HTTPException(403, "Founder request could not be verified")
    return "synthetic_founder"

def issue_founder_session(db, token, csrf):
    db.add(FounderSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),
                          csrf_hash=hashlib.sha256(csrf.encode()).hexdigest(),
                          expires_at=utcnow()+timedelta(minutes=15), revoked_at=None))
