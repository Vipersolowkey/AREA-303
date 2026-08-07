"""Competitor tracking request/response shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AddCompetitorRequest(BaseModel):
    #: A Shopee or Lazada shop URL, pasted as-is.
    url: str = Field(min_length=4, max_length=512)


class SnapshotOut(BaseModel):
    captured_at: str
    ok: bool
    error: str | None
    follower_count: int | None
    rating: float | None
    product_count: int | None
    items_sold_total: int | None
    revenue_est_vnd: int | None
    voucher_count: int | None
    top_products: Any | None
    promotions: Any | None


class CompetitorOut(BaseModel):
    id: int
    platform: Literal["shopee", "lazada"]
    display_name: str | None
    url: str
    created_at: str
    #: Most recent successful reading, if any.
    latest: SnapshotOut | None
    #: Most recent attempt regardless of outcome — surfaces a broken collector.
    last_attempt: SnapshotOut | None
    #: Percent change between first and last successful reading.
    revenue_trend_pct: float | None
    sold_trend_pct: float | None
    #: Share of estimated revenue *across the tracked set* (not the whole market).
    share_pct: float | None
    #: Number of readings collected so far.
    snapshot_count: int


class CompetitorDetail(BaseModel):
    competitor: CompetitorOut
    snapshots: list[SnapshotOut]


class CollectRunOut(BaseModel):
    attempted: int
    succeeded: int
    failed: int
    #: Failure reasons, so a broken endpoint is visible rather than silent.
    errors: list[str]


class InsightOut(BaseModel):
    headline: str
    findings: list[str]
    actions: list[str]
    #: True when the narrative came from the LLM; False for the deterministic
    #: fallback, so the UI never implies AI wrote something it didn't.
    ai_generated: bool
