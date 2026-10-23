"""Founder password/TOTP sessions and authenticated encryption primitives.

No routes are mounted by default. Password hashes, TOTP seeds, session keys,
and encryption keys are supplied by a managed secret store at process start.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import time
from pathlib import Path as FilePath
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping
from urllib.parse import quote

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Path as PathParam, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

SESSION_COOKIE = "pw_founder_session"
SESSION_TTL = timedelta(hours=8)
_ARGON = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


class SecurityConfigurationError(RuntimeError):
    pass


class InvalidCiphertext(ValueError):
    pass


@dataclass(frozen=True)
class FounderConfig:
    username: str
    password_hash: str
    totp_secret: str
    session_key: bytes
    rate_key: bytes
    encryption_keys: Mapping[str, bytes]
    active_encryption_key_id: str
    token_secret: str
    reference_hash_secret: str
    identity_hash_secret: str
    recipient_hash_secret: str
    telebirr_recipient: str
    bank_recipient: str
    allowed_origins: tuple[str, ...]
    auth_enabled: bool = False
    approvals_enabled: bool = False
    secure_cookie: bool = True

    @classmethod
    def from_environment(cls, *, payment_accounts: Mapping[str, Mapping[str, str]] | None = None) -> "FounderConfig":
        def required(name: str) -> str:
            value = os.getenv(name, "")
            if not value:
                raise SecurityConfigurationError(f"{name} is required when founder auth is enabled")
            return value

        def key(name: str) -> bytes:
            try:
                encoded = required(name)
                value = base64.b64decode(encoded + "=" * ((4 - len(encoded) % 4) % 4), altchars=b"-_", validate=True)
            except Exception as exc:
                raise SecurityConfigurationError(f"{name} must be base64url") from exc
            if len(value) < 32:
                raise SecurityConfigurationError(f"{name} must decode to at least 32 bytes")
            return value

        enabled = os.getenv("FOUNDER_AUTH_ENABLED", "false").lower() == "true"
        approval_enabled = os.getenv("FOUNDER_APPROVAL_ENABLED", "false").lower() == "true"
        if not enabled:
            # Config is intentionally inert until explicitly enabled.
            raise SecurityConfigurationError("Founder authentication is disabled")
        raw_ring = json.loads(required("PAYMENT_DATA_KEYRING"))
        if not isinstance(raw_ring, dict) or not raw_ring:
            raise SecurityConfigurationError("PAYMENT_DATA_KEYRING must be a non-empty JSON key map")
        ring: dict[str, bytes] = {}
        for kid, encoded in raw_ring.items():
            encoded = str(encoded)
            decoded = base64.b64decode(encoded + "=" * ((4 - len(encoded) % 4) % 4), altchars=b"-_", validate=True)
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", str(kid)) or len(decoded) != 32:
                raise SecurityConfigurationError("Each AES-256-GCM key must have a valid id and 32 bytes")
            ring[kid] = decoded
        active = required("PAYMENT_DATA_ACTIVE_KEY_ID")
        if active not in ring:
            raise SecurityConfigurationError("Active payment-data key id is not in the keyring")
        origins = tuple(x.strip() for x in required("FOUNDER_ALLOWED_ORIGINS").split(",") if x.strip())
        if not origins or any(not x.startswith("https://") or x.endswith("*") for x in origins):
            raise SecurityConfigurationError("Founder origins must be explicit HTTPS origins")
        password_hash = required("FOUNDER_PASSWORD_HASH")
        try:
            password_parameters = extract_parameters(password_hash)
        except Exception as exc:
            raise SecurityConfigurationError("FOUNDER_PASSWORD_HASH must be a valid Argon2id PHC hash") from exc
        if (password_parameters.type is not Type.ID or password_parameters.time_cost < 2
                or password_parameters.memory_cost < 32768 or password_parameters.parallelism < 1):
            raise SecurityConfigurationError("Founder password hash must use Argon2id with minimum production costs")
        username = required("FOUNDER_USERNAME")
        if not re.fullmatch(r"[A-Za-z0-9._@-]{1,80}", username):
            raise SecurityConfigurationError("FOUNDER_USERNAME has an invalid format")
        totp_secret = required("FOUNDER_TOTP_SECRET")
        try:
            seed = base64.b32decode(totp_secret.upper() + "=" * ((8 - len(totp_secret) % 8) % 8), casefold=True)
        except Exception as exc:
            raise SecurityConfigurationError("FOUNDER_TOTP_SECRET must be a Base32 secret") from exc
        if len(seed) < 20:
            raise SecurityConfigurationError("FOUNDER_TOTP_SECRET must contain at least 160 bits")
        secret_values = {
            "ORDER_TOKEN_KEY": required("ORDER_TOKEN_KEY"),
            "PAYMENT_REFERENCE_HASH_KEY": required("PAYMENT_REFERENCE_HASH_KEY"),
            "PAYER_IDENTITY_HASH_KEY": required("PAYER_IDENTITY_HASH_KEY"),
            "PAYMENT_RECIPIENT_HASH_KEY": required("PAYMENT_RECIPIENT_HASH_KEY"),
        }
        if any(len(value) < 32 for value in secret_values.values()):
            raise SecurityConfigurationError("Order, reference, identity and recipient keys must each be at least 32 characters")
        if payment_accounts is None or set(payment_accounts) != {"telebirr", "bank"}:
            raise SecurityConfigurationError("Protected Telebirr and CBE recipient configuration is required")
        recipients = {}
        for method in ("telebirr", "bank"):
            account = payment_accounts[method]
            number, holder = account.get("number", "").strip(), account.get("holder", "").strip()
            if not number or not holder or number == "NOT-CONFIGURED" or holder == "NOT-CONFIGURED":
                raise SecurityConfigurationError("Protected payment recipient configuration is incomplete")
            recipients[method] = number + "\x1f" + holder
        return cls(
            username=username, password_hash=password_hash,
            totp_secret=totp_secret, session_key=key("FOUNDER_SESSION_KEY"),
            rate_key=key("FOUNDER_RATE_LIMIT_KEY"), encryption_keys=ring,
            active_encryption_key_id=active, token_secret=secret_values["ORDER_TOKEN_KEY"],
            reference_hash_secret=secret_values["PAYMENT_REFERENCE_HASH_KEY"],
            identity_hash_secret=secret_values["PAYER_IDENTITY_HASH_KEY"],
            recipient_hash_secret=secret_values["PAYMENT_RECIPIENT_HASH_KEY"],
            telebirr_recipient=recipients["telebirr"], bank_recipient=recipients["bank"],
            allowed_origins=origins,
            auth_enabled=True, approvals_enabled=approval_enabled,
        )


def _digest(key: bytes, purpose: str, value: str) -> str:
    return hmac.new(key, (purpose + ":v1:" + value).encode(), hashlib.sha256).hexdigest()


def _totp_counter(secret: str, code: str, now: int | None = None) -> int | None:
    if not (isinstance(code, str) and code.isascii() and code.isdigit() and len(code) == 6):
        return None
    try:
        seed = base64.b32decode(secret.upper() + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    except Exception:
        return None
    counter = int((time.time() if now is None else now) // 30)
    for step in (counter - 1, counter, counter + 1):
        digest = hmac.new(seed, struct.pack(">Q", step), hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
        expected = f"{binary % 1_000_000:06d}"
        if hmac.compare_digest(expected, code):
            return step
    return None


def totp_provisioning_uri(username: str, issuer: str, secret: str) -> str:
    label = quote(f"{issuer}:{username}", safe="")
    return f"otpauth://totp/{label}?secret={quote(secret)}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def encrypt_sensitive(plaintext: str, *, keyring: Mapping[str, bytes], key_id: str, aad: str) -> str:
    key = keyring.get(key_id)
    if key is None or len(key) != 32:
        raise SecurityConfigurationError("Active encryption key is unavailable")
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
    enc = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return f"enc:v1:{key_id}:{enc(nonce)}:{enc(ciphertext)}"


def decrypt_sensitive(envelope: str, *, keyring: Mapping[str, bytes], aad: str) -> str:
    try:
        prefix, version, key_id, nonce64, ciphertext64 = envelope.split(":", 4)
        if prefix != "enc" or version != "v1" or key_id not in keyring:
            raise ValueError
        decode = lambda s: base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4))
        nonce, ciphertext = decode(nonce64), decode(ciphertext64)
        if len(nonce) != 12 or len(ciphertext) < 16:
            raise ValueError
        return AESGCM(keyring[key_id]).decrypt(nonce, ciphertext, aad.encode()).decode("utf-8")
    except (ValueError, UnicodeError, InvalidTag, KeyError):
        raise InvalidCiphertext("Sensitive evidence could not be authenticated") from None


def _audit(db: Session, event_type: str, founder_id: str | None, source_hash: str | None = None,
           event_data: dict | None = None) -> None:
    db.execute(text("""INSERT INTO production_founder_security_events
        (event_type, founder_id, source_hash, event_data)
        VALUES (:event, :founder, :source, CAST(:data AS JSONB))"""), {
        "event": event_type, "founder": founder_id, "source": source_hash,
        "data": json.dumps(event_data or {}, separators=(",", ":")),
    })


def _consume_rate_limit(db: Session, cfg: FounderConfig, request: Request, username: str) -> tuple[str, int | None]:
    ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc)
    buckets = sorted((
        (_digest(cfg.rate_key, "founder-login-ip", ip), 5, timedelta(minutes=15)),
        (_digest(cfg.rate_key, "founder-login-user", username.lower()), 20, timedelta(hours=1)),
    ))
    # Lock both deterministic keys in sorted order to avoid deadlocks under concurrent attempts.
    for bucket, limit, window in buckets:
        db.execute(text("""INSERT INTO production_founder_rate_limits
           (bucket_hash, window_started_at, attempts) VALUES (:bucket, now(), 0)
           ON CONFLICT (bucket_hash) DO UPDATE SET bucket_hash=EXCLUDED.bucket_hash"""), {"bucket": bucket})
        current = db.execute(text("""SELECT window_started_at, attempts
           FROM production_founder_rate_limits WHERE bucket_hash=:bucket FOR UPDATE"""),
           {"bucket": bucket}).one()
        if current.attempts >= limit and current.window_started_at > now - window:
            source_hash = _digest(cfg.rate_key, "source", ip)
            _audit(db, "LOGIN_FAILED", None, source_hash, {"rate_limited": True})
            return source_hash, int(window.total_seconds())
        if current.window_started_at <= now - window:
            db.execute(text("UPDATE production_founder_rate_limits SET window_started_at=now(), attempts=1, updated_at=now() WHERE bucket_hash=:bucket"), {"bucket": bucket})
        else:
            db.execute(text("UPDATE production_founder_rate_limits SET attempts=attempts+1, updated_at=now() WHERE bucket_hash=:bucket"), {"bucket": bucket})
    return _digest(cfg.rate_key, "source", ip), None


def create_founder_router(sessions: sessionmaker, cfg: FounderConfig) -> APIRouter:
    """Create isolated founder routes; approval actions remain explicitly gated."""
    if not cfg.auth_enabled:
        raise SecurityConfigurationError("Founder routes cannot be built while disabled")
    router = APIRouter(prefix="/api/v1/founder", tags=["founder-private"])

    class LoginInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        username: str = Field(min_length=1, max_length=80)
        password: str = Field(min_length=12, max_length=256)
        totp: str = Field(pattern=r"^[0-9]{6}$")

    class SettlementInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        order_id: str = Field(pattern=r"^PW-[0-9A-F]{24}$")
        claim_id: str
        observed_reference: str = Field(min_length=3, max_length=128)
        payment_method: str = Field(pattern=r"^(telebirr|bank)$")
        amount_etb: int = Field(ge=0, le=10_000_000)
        currency: str = Field(min_length=3, max_length=3)
        recipient_confirmed: bool
        payer_mobile: str = Field(pattern=r"^\+251[97][0-9]{8}$")
        evidence_source: str = Field(pattern=r"^(TELEBIRR_PORTAL|BANK_STATEMENT)$")
        settled_at: datetime
        note: str = Field(default="", max_length=512)

        @field_validator("settled_at")
        @classmethod
        def validate_settled_at(cls, value: datetime) -> datetime:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Settlement time must include a timezone")
            if value > datetime.now(timezone.utc) + timedelta(minutes=5):
                raise ValueError("Settlement time cannot be in the future")
            return value

    class TelegramClaimInput(BaseModel):
        model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
        order_id: str = Field(pattern=r"^PW-[0-9A-F]{24}$")
        payment_method: str = Field(pattern=r"^(telebirr|bank)$")
        transaction_reference: str = Field(min_length=3, max_length=128)

    class ExceptionInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        order_id: str
        claim_id: str
        evidence_id: str
        relationship: str = Field(pattern=r"^(SPOUSE|RELATIVE|OTHER)$")
        rationale: str = Field(min_length=10, max_length=512)

    class DecisionInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        order_id: str
        claim_id: str
        evidence_id: str | None = None
        reason: str = Field(min_length=10, max_length=512)
        third_party_exception_id: str | None = None

    class DeliveryInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        order_id: str = Field(pattern=r"^PW-[0-9A-F]{24}$")
        status: str = Field(pattern=r"^(PREPARING|SENT|DELIVERED|FAILED)$")

    def get_session(session_cookie: str | None) -> dict:
        if not session_cookie or len(session_cookie) > 128:
            raise HTTPException(401, "Founder session required")
        digest = _digest(cfg.session_key, "session", session_cookie)
        with sessions() as db:
            row = db.execute(text("""SELECT founder_id, csrf_hash, expires_at
                FROM production_founder_sessions WHERE session_hash=:digest AND revoked_at IS NULL"""),
                {"digest": digest}).mappings().first()
        if row is None:
            raise HTTPException(401, "Founder session required")
        if row["expires_at"] <= datetime.now(timezone.utc):
            with sessions.begin() as db:
                db.execute(text("UPDATE production_founder_sessions SET revoked_at=now() WHERE session_hash=:digest AND revoked_at IS NULL"), {"digest": digest})
                _audit(db, "SESSION_EXPIRED", row["founder_id"])
            raise HTTPException(401, "Founder session expired")
        return {"founder_id": row["founder_id"], "csrf_hash": row["csrf_hash"], "session_hash": digest}

    def require_csrf(request: Request, identity: dict, token: str | None) -> None:
        if request.url.scheme != "https":
            raise HTTPException(403, "HTTPS is required")
        if not token or not hmac.compare_digest(_digest(cfg.session_key, "csrf", token), identity["csrf_hash"]):
            raise HTTPException(403, "CSRF validation failed")
        origin = request.headers.get("origin", "")
        if origin not in cfg.allowed_origins:
            raise HTTPException(403, "Request origin is not allowed")

    def identity(session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
        return get_session(session_cookie)

    def decision_enabled() -> None:
        if not cfg.approvals_enabled:
            raise HTTPException(503, "Founder payment decisions are disabled")

    @router.post("/session")
    def login(body: LoginInput, request: Request, response: Response):
        if request.url.scheme != "https" or request.headers.get("origin", "") not in cfg.allowed_origins:
            raise HTTPException(403, "Request origin is not allowed")
        # Persist the attempt before Argon2's deliberately expensive verification.
        with sessions.begin() as db:
            source_hash, retry_after = _consume_rate_limit(db, cfg, request, body.username)
        if retry_after is not None:
            raise HTTPException(429, "Too many sign-in attempts. Try again later.", headers={"Retry-After": str(retry_after)})
        now = int(time.time())
        candidate_step = _totp_counter(cfg.totp_secret, body.totp, now)
        password_ok = False
        try:
            password_ok = _ARGON.verify(cfg.password_hash, body.password)
        except (VerifyMismatchError, InvalidHashError, ValueError):
            pass
        username_ok = hmac.compare_digest(body.username.encode(), cfg.username.encode())
        with sessions.begin() as db:
            control = db.execute(text("SELECT last_totp_step FROM production_founder_auth_control WHERE singleton_id=1 FOR UPDATE")).one()
            valid = password_ok and username_ok and candidate_step is not None and candidate_step > control.last_totp_step
            if valid:
                db.execute(text("UPDATE production_founder_auth_control SET last_totp_step=:step, updated_at=now() WHERE singleton_id=1"), {"step": candidate_step})
                founder_id = cfg.username
                session_raw, csrf_raw = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                expires = datetime.now(timezone.utc) + SESSION_TTL
                db.execute(text("""INSERT INTO production_founder_sessions
                    (session_hash, founder_id, csrf_hash, expires_at)
                    VALUES (:session_hash,:founder,:csrf_hash,:expires)"""), {
                    "session_hash": _digest(cfg.session_key, "session", session_raw),
                    "founder": founder_id, "csrf_hash": _digest(cfg.session_key, "csrf", csrf_raw), "expires": expires,
                })
                _audit(db, "LOGIN_SUCCEEDED", founder_id, source_hash)
            else:
                _audit(db, "MFA_REPLAY_BLOCKED" if candidate_step is not None and candidate_step <= control.last_totp_step else "LOGIN_FAILED", None, source_hash)
        if not password_ok or not username_ok or candidate_step is None:
            raise HTTPException(401, "Invalid sign-in details")
        if candidate_step <= control.last_totp_step:
            raise HTTPException(401, "Invalid sign-in details")
        response.set_cookie(SESSION_COOKIE, session_raw, max_age=int(SESSION_TTL.total_seconds()),
                            httponly=True, secure=cfg.secure_cookie, samesite="strict", path="/api/v1/founder")
        response.headers["Cache-Control"] = "no-store"
        return {"csrf_token": csrf_raw, "expires_at": expires.isoformat()}

    @router.get("/session")
    def session_info(who: dict = Depends(identity), session_cookie: str = Cookie(default=None, alias=SESSION_COOKIE)):
        # Return a fresh CSRF token only via same-origin authenticated fetch. Rotate per read.
        token = secrets.token_urlsafe(32)
        with sessions.begin() as db:
            db.execute(text("UPDATE production_founder_sessions SET csrf_hash=:hash WHERE session_hash=:session_hash AND revoked_at IS NULL"), {
                "hash": _digest(cfg.session_key, "csrf", token), "session_hash": who["session_hash"]})
        return {"founder_id": who["founder_id"], "csrf_token": token}

    @router.delete("/session")
    def logout(request: Request, x_csrf_token: str | None = Header(default=None), who: dict = Depends(identity)):
        require_csrf(request, who, x_csrf_token)
        with sessions.begin() as db:
            db.execute(text("UPDATE production_founder_sessions SET revoked_at=now() WHERE session_hash=:hash AND revoked_at IS NULL"), {"hash": who["session_hash"]})
            _audit(db, "LOGOUT", who["founder_id"])
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/api/v1/founder", secure=cfg.secure_cookie, httponly=True, samesite="strict")
        return response

    @router.get("/ui/login", include_in_schema=False)
    def founder_login_page():
        return FileResponse(FilePath(__file__).with_name("founder_login.html"),
                            media_type="text/html", headers={"Cache-Control":"no-store"})

    @router.get("/ui", include_in_schema=False)
    def founder_dashboard_page(who: dict = Depends(identity)):
        return FileResponse(FilePath(__file__).with_name("founder_admin.html"),
                            media_type="text/html", headers={"Cache-Control":"no-store"})

    @router.get("/ui/admin.css", include_in_schema=False)
    def founder_admin_css():
        return FileResponse(FilePath(__file__).with_name("founder_admin.css"),
                            media_type="text/css", headers={"Cache-Control":"no-store"})

    @router.get("/ui/admin.js", include_in_schema=False)
    def founder_admin_js():
        return FileResponse(FilePath(__file__).with_name("founder_admin.js"),
                            media_type="application/javascript", headers={"Cache-Control":"no-store"})

    @router.get("/orders")
    def list_orders(
        limit: int = Query(default=25, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        q: str = Query(default="", max_length=100),
        status: str | None = Query(default=None, pattern=r"^(AWAITING_PAYMENT|UNDER_REVIEW|PAYMENT_REJECTED|PAYMENT_CONFIRMED)$"),
        payment_method: str | None = Query(default=None, pattern=r"^(telebirr|bank)$"),
        who: dict = Depends(identity),
    ):
        clauses = ["1=1"]
        params: dict[str, object] = {"limit": limit, "offset": offset}
        if q.strip():
            clauses.append("(o.code=:code OR position(lower(:query) in lower(o.customer_name))>0 OR (:digits<>'' AND position(:digits in regexp_replace(o.mobile_e164,'[^0-9]','','g'))>0))")
            params.update({"code": q.strip().upper(), "query": q.strip(), "digits": re.sub(r"[^0-9]", "", q)})
        if status:
            clauses.append("s.payment_status=:status")
            params["status"] = status
        if payment_method:
            clauses.append("o.method=:method")
            params["method"] = payment_method
        where = " AND ".join(clauses)
        with sessions() as db:
            total = db.execute(text(f"""
                SELECT count(*) FROM production_orders o
                JOIN production_payment_fulfillment_state s ON s.order_id=o.id
                WHERE {where}
            """), params).scalar_one()
            rows = db.execute(text(f"""
                SELECT o.code AS order_id,o.customer_name,o.mobile_e164,o.method AS payment_method,
                       o.amount_etb,o.currency,o.created_at,s.payment_status,s.fulfillment_status,
                       d.status AS delivery_status,
                       (SELECT c.claim_status FROM production_payment_claims c
                         WHERE c.order_id=o.id ORDER BY c.submitted_at DESC LIMIT 1) AS claim_status
                  FROM production_orders o
                  JOIN production_payment_fulfillment_state s ON s.order_id=o.id
                  LEFT JOIN production_manual_deliveries d ON d.order_id=o.id
                 WHERE {where}
                 ORDER BY o.created_at DESC,o.code DESC LIMIT :limit OFFSET :offset
            """), params).mappings().all()
        return {"orders":[dict(row) for row in rows],"total":int(total),
                "limit":limit,"offset":offset}

    @router.get("/claims/pending")
    def pending(who: dict = Depends(identity)):
        from .founder_encryption import decrypt_claim_reference
        with sessions() as db:
            rows = db.execute(text("""SELECT o.code,o.customer_name,o.mobile_e164,o.method,o.amount_etb,
                       c.id AS claim_id,c.claim_status,c.reference_ciphertext,c.submitted_at,e.id AS evidence_id,
                       e.payment_method AS evidence_method,e.amount_etb AS evidence_amount_etb,
                       e.currency AS evidence_currency,e.evidence_source,e.settled_at,e.observed_at,
                       e.payer_identity_digest,x.id AS exception_id
                  FROM production_payment_claims c JOIN production_orders o ON o.id=c.order_id
                  JOIN production_payment_fulfillment_state s ON s.order_id=o.id
                  LEFT JOIN production_settlement_evidence e ON e.claim_id=c.id AND e.order_id=c.order_id
                  LEFT JOIN production_third_party_payer_exceptions x ON x.evidence_id=e.id
                 WHERE c.claim_status IN ('SUBMITTED','EVIDENCE_RECORDED') AND s.payment_status='UNDER_REVIEW'
                 ORDER BY c.submitted_at ASC LIMIT 100""")).mappings().all()
        output = []
        for r in rows:
            ref = decrypt_claim_reference(r["reference_ciphertext"], cfg, r["code"])
            payer_digest = hmac.new(cfg.identity_hash_secret.encode(),
                ("payer-identity:v1:"+r["mobile_e164"]).encode(), hashlib.sha256).hexdigest()
            output.append({"order_id":r["code"],"customer_name":r["customer_name"],"mobile":r["mobile_e164"],
                           "payment_method":r["method"],"amount_etb":r["amount_etb"],"claim_id":str(r["claim_id"]),
                           "claim_status":r["claim_status"],"evidence_id":str(r["evidence_id"]) if r["evidence_id"] else None,
                           "exception_id":str(r["exception_id"]) if r["exception_id"] else None,
                           "claimed_reference":ref,"submitted_at":r["submitted_at"].isoformat(),
                           "evidence":({"payment_method":r["evidence_method"],"amount_etb":r["evidence_amount_etb"],
                               "currency":r["evidence_currency"],"source":r["evidence_source"],
                               "settled_at":r["settled_at"].isoformat(),"observed_at":r["observed_at"].isoformat(),
                               "payer_matches_customer":hmac.compare_digest(r["payer_identity_digest"],payer_digest)}
                               if r["evidence_id"] else None)})
        return {"claims":output}

    @router.get("/orders/search")
    def search_orders(q: str = Query(min_length=3, max_length=32),
                      who: dict = Depends(identity)):
        """Exact founder-only lookup for matching a Telegram claim to an order."""
        if not re.fullmatch(r"PW-[0-9A-F]{24}", q):
            raise HTTPException(404, "Order not found")
        with sessions() as db:
            row = db.execute(text("""
                SELECT o.code AS order_id, o.customer_name, o.mobile_e164,
                       o.method AS payment_method, o.amount_etb, o.currency,
                       s.payment_status, s.fulfillment_status
                  FROM production_orders o
                  JOIN production_payment_fulfillment_state s ON s.order_id=o.id
                 WHERE o.code=:code
            """), {"code": q}).mappings().first()
        if row is None:
            raise HTTPException(404, "Order not found")
        return {"order": dict(row)}

    @router.post("/claims/telegram", status_code=201)
    def record_telegram_claim(body: TelegramClaimInput, request: Request,
                              x_csrf_token: str | None = Header(default=None),
                              who: dict = Depends(identity)):
        require_csrf(request, who, x_csrf_token)
        decision_enabled()
        from .founder_encryption import encrypt_claim_reference
        from .payment_state import record_founder_telegram_claim
        try:
            ciphertext = encrypt_claim_reference(
                body.transaction_reference, cfg, body.order_id)
            with sessions() as db:
                claim_id = record_founder_telegram_claim(
                    db, actor_id=who["founder_id"], order_code=body.order_id,
                    payment_method=body.payment_method,
                    reference_hash_secret=cfg.reference_hash_secret,
                    transaction_reference=body.transaction_reference,
                    reference_ciphertext=ciphertext,
                )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except Exception as exc:
            _domain_error(exc)
        return {"order_id": body.order_id, "claim_id": claim_id,
                "status": "UNDER_REVIEW_NOT_PAYMENT_CONFIRMATION"}

    @router.get("/metrics")
    def metrics(who: dict = Depends(identity)):
        from .manual_fulfillment import manual_delivery_report, verified_revenue_trend
        with sessions() as db:
            report = manual_delivery_report(db)
            report["revenue_trend"] = verified_revenue_trend(db, months=6)
            return report

    @router.get("/deliveries/pending")
    def pending_deliveries(who: dict = Depends(identity)):
        with sessions() as db:
            rows = db.execute(text("""
                SELECT o.code AS order_id, o.customer_name, o.mobile_e164,
                       d.status, d.created_at, d.updated_at
                  FROM production_manual_deliveries d
                  JOIN production_orders o ON o.id=d.order_id
                 WHERE d.status IN ('PENDING','PREPARING','SENT','FAILED')
                 ORDER BY d.created_at ASC
            """)).mappings().all()
            return {"deliveries": [dict(row) for row in rows]}

    @router.get("/deliveries/{order_id}/history")
    def delivery_history(order_id: str = PathParam(..., pattern=r"^PW-[0-9A-F]{24}$"),
                         who: dict = Depends(identity)):
        with sessions() as db:
            exists = db.scalar(text("SELECT 1 FROM production_orders WHERE code=:code"), {"code":order_id})
            if not exists:
                raise HTTPException(404, "Order not found")
            rows = db.execute(text("""
                SELECT e.old_status,e.new_status,e.actor_id,e.occurred_at
                  FROM production_manual_delivery_events e
                  JOIN production_orders o ON o.id=e.order_id
                 WHERE o.code=:code ORDER BY e.occurred_at,e.id
            """), {"code":order_id}).mappings().all()
        return {"order_id":order_id,"history":[dict(row) for row in rows]}

    @router.post("/deliveries/status")
    def delivery_status(body: DeliveryInput, request: Request,
                        x_csrf_token: str | None = Header(default=None),
                        who: dict = Depends(identity)):
        require_csrf(request, who, x_csrf_token)
        decision_enabled()
        from .manual_fulfillment import ManualDeliveryError, record_manual_delivery
        with sessions() as db:
            try:
                state = record_manual_delivery(
                    db, actor_id=who["founder_id"], order_code=body.order_id,
                    new_status=body.status,
                )
            except ManualDeliveryError as exc:
                raise HTTPException(409, str(exc)) from None
        return {"order_id": body.order_id, "delivery_status": state}

    @router.post("/settlements")
    def settlement(body: SettlementInput, request: Request, x_csrf_token: str | None = Header(default=None), who: dict = Depends(identity)):
        require_csrf(request, who, x_csrf_token); decision_enabled()
        from .payment_state import record_settlement_evidence, transaction_reference_digest
        if not body.recipient_confirmed:
            raise HTTPException(409, "Recipient must be independently confirmed")
        canonical_recipient = cfg.telebirr_recipient if body.payment_method == "telebirr" else cfg.bank_recipient
        recipient_digest = hmac.new(cfg.recipient_hash_secret.encode(), ("recipient:v1:"+canonical_recipient).encode(), hashlib.sha256).hexdigest()
        ref_digest = transaction_reference_digest(cfg.reference_hash_secret, body.observed_reference)
        payer_digest = hmac.new(cfg.identity_hash_secret.encode(), ("payer-identity:v1:"+body.payer_mobile).encode(), hashlib.sha256).hexdigest()
        from .founder_encryption import encrypt_evidence_note
        note = encrypt_evidence_note(body.note, cfg, body.order_id, body.claim_id)
        with sessions() as db:
            try:
                evidence_id = record_settlement_evidence(db, actor_id=who["founder_id"], order_code=body.order_id,
                    claim_id=body.claim_id, reference_digest=ref_digest, payment_method=body.payment_method,
                    amount_etb=body.amount_etb, currency=body.currency.upper(), recipient_digest=recipient_digest,
                    payer_identity_digest=payer_digest, evidence_source=body.evidence_source,
                    settled_at=body.settled_at.astimezone(timezone.utc), evidence_note_ciphertext=note)
            except Exception as exc:
                _domain_error(exc)
        buyer_digest = hmac.new(cfg.identity_hash_secret.encode(), ("payer-identity:v1:"+body.payer_mobile).encode(), hashlib.sha256).hexdigest()
        with sessions() as db:
            buyer_mobile = db.execute(text("SELECT o.mobile_e164 FROM production_orders o WHERE o.code=:code"),
                                      {"code":body.order_id}).scalar_one_or_none()
        payer_matches_customer = bool(buyer_mobile) and hmac.compare_digest(buyer_digest,
            hmac.new(cfg.identity_hash_secret.encode(), ("payer-identity:v1:"+buyer_mobile).encode(), hashlib.sha256).hexdigest())
        return {"evidence_id": evidence_id, "payer_matches_customer": payer_matches_customer,
                "status": "EVIDENCE_RECORDED_NOT_APPROVED"}

    @router.post("/third-party-exceptions")
    def exception(body: ExceptionInput, request: Request, x_csrf_token: str | None = Header(default=None), who: dict = Depends(identity)):
        require_csrf(request, who, x_csrf_token); decision_enabled()
        from .payment_state import document_third_party_exception
        from .founder_encryption import encrypt_exception_note
        note = encrypt_exception_note(body.rationale, cfg, body.order_id, body.claim_id)
        with sessions() as db:
            try:
                result = document_third_party_exception(db, actor_id=who["founder_id"], order_code=body.order_id,
                    claim_id=body.claim_id, evidence_id=body.evidence_id, relationship=body.relationship,
                    rationale=note, identity_hash_secret=cfg.identity_hash_secret)
            except Exception as exc:
                _domain_error(exc)
        return {"exception_id": result, "status": "DOCUMENTED"}

    @router.post("/approve")
    def approve(body: DecisionInput, request: Request, x_csrf_token: str | None = Header(default=None), who: dict = Depends(identity)):
        require_csrf(request, who, x_csrf_token); decision_enabled()
        if not body.evidence_id: raise HTTPException(422, "Settlement evidence is required")
        from .payment_state import approve_payment
        with sessions() as db:
            method = db.execute(text("SELECT method FROM production_orders WHERE code=:code"), {"code": body.order_id}).scalar_one_or_none()
        if method not in {"telebirr", "bank"}:
            raise HTTPException(404, "Order not found")
        recipient = cfg.telebirr_recipient if method == "telebirr" else cfg.bank_recipient
        recipient_digest = hmac.new(cfg.recipient_hash_secret.encode(), ("recipient:v1:"+recipient).encode(), hashlib.sha256).hexdigest()
        with sessions() as db:
            try:
                grant = approve_payment(db, actor_id=who["founder_id"], order_code=body.order_id, claim_id=body.claim_id,
                    evidence_id=body.evidence_id, reason=body.reason, token_secret=cfg.token_secret,
                    reference_hash_secret=cfg.reference_hash_secret, identity_hash_secret=cfg.identity_hash_secret,
                    expected_recipient_digest=recipient_digest, third_party_exception_id=body.third_party_exception_id,
                    fulfillment_mode="manual_telegram")
            except Exception as exc: _domain_error(exc)
        return {"grant_id": grant, "status": "PAYMENT_CONFIRMED",
                "fulfillment_mode": "manual_telegram", "delivery_status": "PENDING"}

    @router.post("/reject")
    def reject(body: DecisionInput, request: Request, x_csrf_token: str | None = Header(default=None), who: dict = Depends(identity)):
        require_csrf(request, who, x_csrf_token); decision_enabled()
        from .payment_state import reject_payment
        with sessions() as db:
            try: reject_payment(db, actor_id=who["founder_id"], order_code=body.order_id, claim_id=body.claim_id, reason=body.reason, evidence_id=body.evidence_id)
            except Exception as exc: _domain_error(exc)
        return {"status": "PAYMENT_REJECTED"}

    @router.post("/grants/revoke")
    def revoke(body: DecisionInput, request: Request, x_csrf_token: str | None = Header(default=None), who: dict = Depends(identity)):
        require_csrf(request, who, x_csrf_token); decision_enabled()
        from .payment_state import revoke_download_grant
        with sessions() as db:
            try: revoke_download_grant(db, actor_id=who["founder_id"], order_code=body.order_id, reason=body.reason)
            except Exception as exc: _domain_error(exc)
        return {"status": "REVOKED"}

    return router


def _domain_error(exc: Exception) -> None:
    from .payment_state import DuplicateReference, DownloadDenied, InvalidTransition, OrderNotFound, UnauthorizedFounder
    if isinstance(exc, DuplicateReference): raise HTTPException(409, "Settlement reference was already used") from None
    if isinstance(exc, (DownloadDenied, OrderNotFound, UnauthorizedFounder)): raise HTTPException(404, "Order or founder authorization not found") from None
    if isinstance(exc, InvalidTransition): raise HTTPException(409, "Payment review cannot be completed in the current state") from None
    raise HTTPException(503, "Payment review is temporarily unavailable") from None

