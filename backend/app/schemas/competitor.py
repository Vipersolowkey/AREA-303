"""Competitor tracking request/response shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AddCompetitorRequest(BaseModel):
    #: A Shopee or Lazada shop URL, pasted as-is.
    url: str = Field(min_length=4, max_length=512)


class SnapshotOut(BaseModel):
    """One reading.

    `items_sold_total`, `revenue_est_vnd`, `voucher_count`, `top_products` and
    `promotions` are kept in the shape because the collector still parses them
    if a marketplace ever answers — but both Shopee and Lazada currently block
    the endpoints that carry them, so expect None. The UI must not present them
    as pending data.
    """

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
    follower_trend_pct: float | None
    product_trend_pct: float | None
    #: Absolute rating change (a % of a 4.9 average would be meaningless).
    rating_delta: float | None
    #: Share of FOLLOWERS across the tracked set. Not revenue share — the
    #: marketplaces block their listing endpoints, so sales are unobtainable —
    #: and not market share either, since total category size is unknowable.
    follower_share_pct: float | None
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
