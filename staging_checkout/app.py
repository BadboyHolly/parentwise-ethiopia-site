"""Staging-only composition of independent order intake and isolated review/delivery."""
from __future__ import annotations
import hashlib, os, secrets
from datetime import datetime, timedelta, timezone
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from argon2 import PasswordHasher
from production_checkout.app import build_app
from .models import RateWindow
from .payment_claims import mount_payment_claims
from .founder_verification import mount_founder_verification
from .downloads import mount_downloads

FICTIONAL_RECIPIENTS = {
    "telebirr": {"name":"Telebirr QA simulator","number":"QA-TELEBIRR-ONLY","holder":"FICTIONAL QA"},
    "bank": {"name":"CBE QA simulator","number":"QA-CBE-ONLY","holder":"FICTIONAL QA"},
}

def reserve_rate(engine, bucket_key: str, limit: int, window_seconds: int = 600) -> bool:
    now = datetime.now(timezone.utc)
    reset = now + timedelta(seconds=window_seconds)
    stmt = pg_insert(RateWindow).values(bucket_key=bucket_key, count=1, reset_at=reset)
    stmt = stmt.on_conflict_do_update(
        index_elements=[RateWindow.bucket_key],
        set_={
            "count": case((RateWindow.reset_at <= now, 1), else_=RateWindow.count + 1),
            "reset_at": case((RateWindow.reset_at <= now, reset), else_=RateWindow.reset_at),
        },
    ).returning(RateWindow.count)
    with engine.begin() as connection:
        count = connection.execute(stmt).scalar_one()
    return count <= limit

def build_staging_app(*, database_url: str, order_token_secret: str,
                      founder_username: str, founder_password_hash: str,
                      founder_totp_secret: str, allowed_origins: list[str],
                      order_intake_enabled: bool, customer_rate_limit: int = 30):
    if os.getenv("APP_MODE") != "staging":
        raise RuntimeError("Staging integration requires APP_MODE=staging")
    if os.getenv("PAYMENTS_ENABLED", "true").lower() != "false":
        raise RuntimeError("Staging integration requires PAYMENTS_ENABLED=false")
    if not order_intake_enabled or os.getenv("STAGING_ORDER_INTAKE_ENABLED") != "true":
        raise RuntimeError("Staging order intake must be explicitly enabled for isolated tests")
    if not database_url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Staging integration requires its disposable PostgreSQL database")
    if len(order_token_secret) < 32 or len(founder_totp_secret) < 16 or customer_rate_limit < 1:
        raise RuntimeError("Staging credentials or rate limits are invalid")
    if not founder_username or not founder_password_hash:
        raise RuntimeError("Synthetic founder credentials are required")
    app = build_app(database_url=database_url, token_secret=order_token_secret,
        allowed_origins=allowed_origins, intake_enabled=True,
        payment_accounts=FICTIONAL_RECIPIENTS)
    @app.middleware("http")
    async def staging_checkout_policy(request: Request, call_next):
        nonce = secrets.token_urlsafe(18) if request.url.path == "/staging/checkout" else ""
        if nonce:
            request.state.staging_csp_nonce = nonce
        response = await call_next(request)
        if nonce:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; "
                "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data:; "
                "font-src https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
            )
        return response

    app.state.order_sessions = app.state.sessions
    app.state.order_token_secret = order_token_secret
    app.state.founder_username = founder_username
    app.state.founder_password_hash = founder_password_hash
    app.state.founder_totp_secret = founder_totp_secret
    app.state.password_hasher = PasswordHasher()
    app.state.customer_rate_limit = customer_rate_limit

    @app.middleware("http")
    async def customer_abuse_limit(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/orders/") or path == "/api/v1/orders" or path == "/founder/session":
            client = request.client.host if request.client else "unknown"
            group = ("founder-login" if path == "/founder/session" else
                     "order-create" if path == "/api/v1/orders" else
                     "claim" if path.endswith("/payment-claims") else
                     "download" if "/downloads/" in path else "recovery")
            cap = 5 if group == "founder-login" else app.state.customer_rate_limit
            bucket = hashlib.sha256((group + ":" + client).encode()).hexdigest()
            try:
                allowed = reserve_rate(app.state.engine, bucket, cap)
            except SQLAlchemyError:
                return JSONResponse({"detail":"Request protection is unavailable"}, status_code=503,
                                    headers={"Cache-Control":"no-store"})
            if not allowed:
                return JSONResponse({"detail":"Too many requests; wait before trying again"}, status_code=429,
                                    headers={"Cache-Control":"no-store","Retry-After":"600"})
        return await call_next(request)

    mount_payment_claims(app)
    mount_founder_verification(app)
    mount_downloads(app)

    app.mount("/staging/assets", StaticFiles(directory=str(Path(__file__).parent.parent / "assets")), name="staging-public-brand-assets")

    @app.get("/staging/checkout", include_in_schema=False)
    def staging_checkout_ui(request: Request):
        html = (Path(__file__).parent / "ui" / "checkout.html").read_text(encoding="utf-8")
        if html.count("<script>") != 1:
            raise RuntimeError("Staging checkout script markup changed; refusing to serve without a CSP nonce")
        nonce = request.state.staging_csp_nonce
        html = html.replace("<script>", f'<script nonce="{nonce}">', 1)
        return HTMLResponse(html, headers={"Cache-Control":"no-store", "X-Robots-Tag":"noindex, nofollow"})

    @app.get("/staging/healthz")
    def stage_health():
        return {"environment":"isolated-staging","payments_enabled":False,
                "live_order_intake_enabled":False,"qa_backend_connected":False}
    return app

def from_environment():
    origins = [x.strip() for x in os.getenv("STAGING_ALLOWED_ORIGINS","").split(",") if x.strip()]
    if not origins or any(not x.startswith("https://") or x == "https://" for x in origins):
        raise RuntimeError("A staging HTTPS origin allowlist is required")
    return build_staging_app(
        database_url=os.getenv("STAGING_DATABASE_URL",""),
        order_token_secret=os.getenv("STAGING_ORDER_TOKEN_KEY",""),
        founder_username=os.getenv("STAGING_FOUNDER_USERNAME",""),
        founder_password_hash=os.getenv("STAGING_FOUNDER_PASSWORD_HASH",""),
        founder_totp_secret=os.getenv("STAGING_FOUNDER_TOTP_SECRET",""),
        allowed_origins=origins,
        order_intake_enabled=os.getenv("STAGING_ORDER_INTAKE_ENABLED") == "true",
        customer_rate_limit=int(os.getenv("STAGING_CUSTOMER_RATE_LIMIT","30")),
    )
