"""Privacy-preserving, first-party visit analytics for the ParentWise sales page.

What is stored per event: a keyed hash of a random per-tab session id, one of five
fixed event names, a normalised source/campaign label, a coarse device class and a
coarse in-app-browser class. Nothing else: no IP address, no user agent, no cookie,
no name, phone number, order code or payment data. Counts are anonymous browser
sessions, not people.

The intake route is mounted only when ``ANALYTICS_ENABLED=true`` and is fail-closed
by default. The read-only report is served through the authenticated founder router.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint,
                        func, select)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from .app import Base

EVENTS = ("sales_view", "checkout_view", "payment_view", "proof_view", "telegram_open")
DEVICES = ("mobile", "tablet", "desktop")
BROWSERS = ("facebook_in_app", "instagram_in_app", "telegram_in_app", "tiktok_in_app", "other")
ADDIS_OFFSET = timedelta(hours=3)  # East Africa Time, no daylight saving


class AnalyticsEvent(Base):
    __tablename__ = "production_analytics_events"
    __table_args__ = (
        UniqueConstraint("sid_hash", "event", name="uq_prod_analytics_sid_event"),
        CheckConstraint("event IN ('sales_view','checkout_view','payment_view','proof_view','telegram_open')",
                        name="ck_prod_analytics_event"),
        CheckConstraint("device IN ('mobile','tablet','desktop')", name="ck_prod_analytics_device"),
        CheckConstraint("browser IN ('facebook_in_app','instagram_in_app','telegram_in_app','tiktok_in_app','other')",
                        name="ck_prod_analytics_browser"),
        Index("ix_prod_analytics_created", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sid_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    campaign: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    device: Mapped[str] = mapped_column(String(8), nullable=False)
    browser: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sid: str = Field(pattern=r"^[A-Za-z0-9_-]{22,43}$")
    event: Literal["sales_view", "checkout_view", "payment_view", "proof_view", "telegram_open"]
    source: str = Field(default="", pattern=r"^[a-z0-9_-]{0,32}$")
    campaign: str = Field(default="", pattern=r"^[a-z0-9_.-]{0,48}$")
    device: Literal["mobile", "tablet", "desktop"] = "desktop"
    browser: Literal["facebook_in_app", "instagram_in_app", "telegram_in_app",
                     "tiktok_in_app", "other"] = "other"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def sid_digest(key: bytes, sid: str) -> str:
    return hmac.new(key, ("analytics-sid:v1:" + sid).encode(), hashlib.sha256).hexdigest()


def create_analytics_router(sessions: sessionmaker, hash_key: bytes, *, max_per_minute: int = 300) -> APIRouter:
    if len(hash_key) < 32:
        raise RuntimeError("ANALYTICS_HASH_KEY must be at least 32 bytes")
    router = APIRouter(tags=["analytics-public"])

    @router.post("/api/v1/events", status_code=204)
    def record_event(item: EventInput):
        now = datetime.now(timezone.utc)
        try:
            with sessions() as db:
                recent = db.scalar(select(func.count()).select_from(AnalyticsEvent)
                                   .where(AnalyticsEvent.created_at >= now - timedelta(seconds=60)))
                if (recent or 0) >= max_per_minute:
                    raise HTTPException(429, "Too many events right now")
                db.add(AnalyticsEvent(
                    sid_hash=sid_digest(hash_key, item.sid), event=item.event,
                    source=item.source, campaign=item.campaign, device=item.device,
                    browser=item.browser, created_at=now))
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()  # the same session already recorded this event: idempotent
        except HTTPException:
            raise
        except SQLAlchemyError:
            raise HTTPException(503, "Analytics storage is temporarily unavailable") from None
        return Response(status_code=204)

    return router


def build_report(db, days: int = 30, *, now: datetime | None = None) -> dict:
    """Aggregate anonymous sessions that STARTED in the window (sales page viewed)."""
    now = _utc(now or datetime.now(timezone.utc))
    start = now - timedelta(days=days)
    starts = db.execute(select(AnalyticsEvent.sid_hash, AnalyticsEvent.source, AnalyticsEvent.campaign,
                               AnalyticsEvent.device, AnalyticsEvent.browser, AnalyticsEvent.created_at)
                        .where(AnalyticsEvent.event == "sales_view", AnalyticsEvent.created_at >= start,
                               AnalyticsEvent.created_at <= now).limit(500_000)).all()
    cohort = {r.sid_hash for r in starts}
    reached = {e: set() for e in EVENTS}
    reached["sales_view"] = set(cohort)
    if cohort:
        later = db.execute(select(AnalyticsEvent.sid_hash, AnalyticsEvent.event)
                           .where(AnalyticsEvent.event != "sales_view", AnalyticsEvent.created_at >= start)
                           .limit(2_000_000)).all()
        for sid, event in later:
            if sid in cohort and event in reached:
                reached[event].add(sid)
    funnel = [{"event": e, "sessions": len(reached[e])} for e in EVENTS]

    groups: dict[tuple[str, str], int] = {}
    daily: dict[str, int] = {}
    viewport: dict[str, int] = {}
    browser_kind: dict[str, int] = {}
    for r in starts:
        key = (r.source or "direct", r.campaign or "")
        groups[key] = groups.get(key, 0) + 1
        day = (_utc(r.created_at) + ADDIS_OFFSET).date().isoformat()
        daily[day] = daily.get(day, 0) + 1
        viewport[r.device] = viewport.get(r.device, 0) + 1
        browser_kind[r.browser] = browser_kind.get(r.browser, 0) + 1
    sources = [{"source": s, "campaign": c, "sessions": n, "orders": 0, "verified": 0, "revenue_etb": 0}
               for (s, c), n in sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))]
    today = (now + ADDIS_OFFSET).date()
    series = [{"day": (today - timedelta(days=i)).isoformat(),
               "sessions": daily.get((today - timedelta(days=i)).isoformat(), 0)}
              for i in range(days - 1, -1, -1)]
    as_rows = lambda d: [{"label": k, "sessions": v} for k, v in sorted(d.items(), key=lambda kv: -kv[1])]
    return {
        "mode": "live", "generated_at": now.isoformat(), "window_days": days,
        "metrics": {"sessions": len(cohort)},
        "funnel": funnel, "sources": sources, "daily": series,
        "devices": {"viewport": as_rows(viewport), "browser_kind": as_rows(browser_kind)},
        "notes": ["Anonymous browser sessions, not people.",
                  "Orders and verified revenue per source are not attributed yet (sessions only)."],
    }
