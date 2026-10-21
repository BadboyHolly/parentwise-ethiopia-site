"""Disposable CI web server only: buyer form -> pending order in isolated SQLite.

Never deploy. Refuses to import unless the explicit synthetic acceptance gate is on.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from production_checkout.app import Base, build_app

if os.getenv("V1_SYNTHETIC_CI") != "true":
    raise RuntimeError("CI-only isolated V1 checkout server is not deployable")
if os.getenv("APP_MODE") != "staging" or os.getenv("PAYMENTS_ENABLED") != "false":
    raise RuntimeError("Synthetic demo requires APP_MODE=staging, PAYMENTS_ENABLED=false")
if os.getenv("ORDER_INTAKE_ENABLED") == "true":
    raise RuntimeError("Production order intake gate must stay disabled")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "v1_checkout" / "temporary-ci-v1-orders.sqlite3"

app = build_app(
    database_url="sqlite:///" + str(DB),
    token_secret="SYNTHETIC-CI-ONLY-KEY-" + ("n" * 45),
    allowed_origins=["http://localhost:8765"],
    allow_sqlite_for_tests=True,
    intake_enabled=True,  # Only this disposable CI fixture; production remains disabled.
    payment_accounts={
        "telebirr": {"name": "Telebirr", "number": "QA-TELEBIRR-ONLY", "holder": "DEMO RECIPIENT — NOT REAL"},
        "bank": {"name": "CBE Bank", "number": "QA-CBE-ONLY", "holder": "DEMO RECIPIENT — NOT REAL"},
    },
)
Base.metadata.create_all(app.state.engine)

# The independent order API intentionally uses CSP default-src 'none'.
# The isolated CI HTML fixture alone needs scripts and local assets.
# Never weaken the /api or production response policy.
@app.middleware("http")
async def ci_html_only_content_policy(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/v1_checkout/") or request.url.path in ("/index.html", "/order.html"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; frame-ancestors 'none'"
        )
    return response

app.mount("/v1_checkout/assets", StaticFiles(directory=str(ROOT / "assets")), name="ci_assets")

# Explicit localhost-only sales-to-checkout test routes.
# /order.html is the integrated CI buyer screen, not the static non-payable
# review file in the repository root. No public/production deployment may use
# this server or its synthetic SQLite records.
app.mount("/assets", StaticFiles(directory=str(ROOT / "assets")), name="ci_root_assets")

@app.get("/index.html")
def reviewed_sales_page():
    response = FileResponse(ROOT / "index.html", media_type="text/html")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response

@app.get("/order.html")
def integrated_checkout():
    return demo_checkout()


@app.get("/v1_checkout/ci-only-order.html")
def demo_checkout():
    response = FileResponse(ROOT / "v1_checkout" / "ci-only-order.html", media_type="text/html")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
