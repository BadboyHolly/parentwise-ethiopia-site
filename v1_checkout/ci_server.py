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
    allowed_origins=["http://127.0.0.1:8765"],
    allow_sqlite_for_tests=True,
    intake_enabled=True,  # Only this disposable CI fixture; production remains disabled.
    payment_accounts={
        "telebirr": {"name": "Telebirr", "number": "QA-TELEBIRR-ONLY", "holder": "DEMO RECIPIENT — NOT REAL"},
        "bank": {"name": "CBE Bank", "number": "QA-CBE-ONLY", "holder": "DEMO RECIPIENT — NOT REAL"},
    },
)
Base.metadata.create_all(app.state.engine)
app.mount("/v1_checkout/assets", StaticFiles(directory=str(ROOT / "assets")), name="ci_assets")

@app.get("/v1_checkout/ci-only-order.html")
def demo_checkout():
    response = FileResponse(ROOT / "v1_checkout" / "ci-only-order.html", media_type="text/html")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
