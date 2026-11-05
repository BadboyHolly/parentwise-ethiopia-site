"""Tests for the privacy-preserving visit analytics (SQLite; no external services)."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from production_checkout.analytics import (AnalyticsEvent, build_report, create_analytics_router,
                                           sid_digest)
from production_checkout.app import Base, build_app

SECRET = "DISPOSABLE-CI-NOT-A-REAL-TOKEN-" + "a" * 40
KEY = b"k" * 40
SID_A = "A" * 22
SID_B = "B" * 22
SID_C = "C" * 22


def make_app(tmp_path, per_minute=300):
    app = build_app(database_url="sqlite:///" + str(tmp_path / "analytics.db"), token_secret=SECRET,
                    allowed_origins=["http://localhost:3000"], allow_sqlite_for_tests=True)
    Base.metadata.create_all(app.state.engine)
    app.include_router(create_analytics_router(app.state.sessions, KEY, max_per_minute=per_minute))
    return app


@pytest.fixture
def client(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app) as c:
        yield c, app


def event(sid=SID_A, name="sales_view", **extra):
    return {"sid": sid, "event": name, **extra}


def count(app):
    with app.state.sessions() as db:
        return db.scalar(select(func.count()).select_from(AnalyticsEvent))


def test_records_event_and_stores_only_a_hash(client):
    c, app = client
    r = c.post("/api/v1/events", json=event(source="facebook", campaign="parents-demo", device="mobile",
                                            browser="facebook_in_app"))
    assert r.status_code == 204 and r.content == b""
    with app.state.sessions() as db:
        row = db.scalar(select(AnalyticsEvent))
    assert row.sid_hash == sid_digest(KEY, SID_A) and SID_A not in row.sid_hash and len(row.sid_hash) == 64
    assert (row.source, row.campaign, row.device, row.browser) == ("facebook", "parents-demo", "mobile", "facebook_in_app")


def test_table_has_no_personal_columns():
    cols = {c.name for c in AnalyticsEvent.__table__.columns}
    assert cols == {"id", "sid_hash", "event", "source", "campaign", "device", "browser", "created_at"}


def test_same_event_twice_is_idempotent(client):
    c, app = client
    assert c.post("/api/v1/events", json=event()).status_code == 204
    assert c.post("/api/v1/events", json=event()).status_code == 204
    assert count(app) == 1
    assert c.post("/api/v1/events", json=event(name="checkout_view")).status_code == 204
    assert count(app) == 2


@pytest.mark.parametrize("body", [
    {"sid": "short", "event": "sales_view"},
    {"sid": SID_A, "event": "purchase"},
    {"sid": SID_A, "event": "sales_view", "email": "a@b.c"},
    {"sid": SID_A, "event": "sales_view", "source": "Face Book!"},
    {"sid": SID_A, "event": "sales_view", "device": "toaster"},
    {"event": "sales_view"},
])
def test_rejects_invalid_or_extra_fields(client, body):
    c, app = client
    assert c.post("/api/v1/events", json=body).status_code == 422
    assert count(app) == 0


def test_global_per_minute_cap(tmp_path):
    app = make_app(tmp_path, per_minute=3)
    with TestClient(app) as c:
        codes = [c.post("/api/v1/events", json=event(sid=s * 22)).status_code for s in "ABCD"]
    assert codes == [204, 204, 204, 429]


def seed(app, rows):
    with app.state.sessions() as db:
        for sid, name, source, campaign, device, browser, when in rows:
            db.add(AnalyticsEvent(sid_hash=sid_digest(KEY, sid), event=name, source=source, campaign=campaign,
                                  device=device, browser=browser, created_at=when))
        db.commit()


def test_report_counts_cohort_funnel_sources_devices(tmp_path):
    app = make_app(tmp_path)
    now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    d = lambda n, h=0: now - timedelta(days=n, hours=h)
    seed(app, [
        (SID_A, "sales_view", "facebook", "parents-demo", "mobile", "facebook_in_app", d(1)),
        (SID_A, "checkout_view", "", "", "mobile", "facebook_in_app", d(1) + timedelta(minutes=2)),
        (SID_A, "payment_view", "", "", "mobile", "facebook_in_app", d(1) + timedelta(minutes=3)),
        (SID_B, "sales_view", "", "", "desktop", "other", d(2)),
        (SID_B, "checkout_view", "", "", "desktop", "other", d(2) + timedelta(minutes=1)),
        (SID_C, "sales_view", "instagram", "", "mobile", "instagram_in_app", d(40)),  # outside 30-day window
        (SID_C, "checkout_view", "", "", "mobile", "instagram_in_app", d(40) + timedelta(minutes=1)),
        ("D" * 22, "checkout_view", "", "", "mobile", "other", d(1)),  # no sales_view in window: not counted
    ])
    with app.state.sessions() as db:
        rep = build_report(db, 30, now=now)
    assert rep["metrics"]["sessions"] == 2
    assert {f["event"]: f["sessions"] for f in rep["funnel"]} == {
        "sales_view": 2, "checkout_view": 2, "payment_view": 1, "proof_view": 0, "telegram_open": 0}
    assert [(s["source"], s["campaign"], s["sessions"]) for s in rep["sources"]] == [
        ("direct", "", 1), ("facebook", "parents-demo", 1)]
    assert {r["label"]: r["sessions"] for r in rep["devices"]["viewport"]} == {"mobile": 1, "desktop": 1}
    assert len(rep["daily"]) == 30 and sum(x["sessions"] for x in rep["daily"]) == 2
    assert rep["daily"][-1]["day"] == "2026-11-10"
    assert all(s["orders"] == 0 and s["revenue_etb"] == 0 for s in rep["sources"])


def test_report_is_empty_but_well_formed_with_no_data(tmp_path):
    app = make_app(tmp_path)
    with app.state.sessions() as db:
        rep = build_report(db, 7, now=datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert rep["metrics"]["sessions"] == 0 and rep["sources"] == [] and len(rep["daily"]) == 7
    assert [f["sessions"] for f in rep["funnel"]] == [0, 0, 0, 0, 0]


def test_report_route_requires_founder_session(tmp_path):
    from production_checkout.founder_security import FounderConfig, create_founder_router
    app = make_app(tmp_path)
    cfg = FounderConfig(
        username="founder-primary", password_hash=PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2).hash("x" * 20),
        totp_secret=base64.b32encode(b"0123456789abcdef0123").decode().rstrip("="),
        session_key=b"s" * 32, rate_key=b"r" * 32, encryption_keys={"test-k1": b"t" * 32},
        active_encryption_key_id="test-k1", token_secret="t" * 48, reference_hash_secret="h" * 48,
        identity_hash_secret="i" * 48, recipient_hash_secret="p" * 48, telebirr_recipient="TEST-TEL-RECIPIENT",
        bank_recipient="TEST-BANK-RECIPIENT", allowed_origins=("https://founder.example",),
        auth_enabled=True, approvals_enabled=False, secure_cookie=True)
    app.include_router(create_founder_router(app.state.sessions, cfg))
    with TestClient(app) as c:
        # No sign-in cookie: refused before any database lookup. (A forged cookie needs the
        # PostgreSQL founder-session tables; that path is covered by test_founder_security.py.)
        assert c.get("/api/v1/founder/report").status_code == 401
        assert c.get("/api/v1/founder/report?days=30").status_code == 401


def test_intake_route_is_absent_unless_mounted(tmp_path):
    app = build_app(database_url="sqlite:///" + str(tmp_path / "off.db"), token_secret=SECRET,
                    allowed_origins=["http://localhost:3000"], allow_sqlite_for_tests=True)
    with TestClient(app) as c:
        assert c.post("/api/v1/events", json=event()).status_code in (404, 405)
