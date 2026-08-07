"""Competitor tracking request/response shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AddCompetitorRequest(BaseModel):
    #: A Shopee or Lazada shop URL, pasted as-is.
    url: str = Field(min_length=4, max_length=512)


class SnapshotOut(BaseModel):
    """One reading.

    The sales fields — `items_sold_total`, `revenue_est_vnd`, `voucher_count`,
    `top_products`, `promotions` — are only populated when a sales source was
    configured, because Shopee serves them exclusively to authenticated
    sessions. `sales_source` says which source produced them ("vendor" or
    "session"); None means this reading is shop-level only, and the UI should say
    so rather than show a pending-looking blank.
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
    sales_source: Literal["vendor", "session"] | None


class PeriodSalesOut(BaseModel):
    """Sales between the two most recent readings — current velocity.

    Distinct from `items_sold_total`, which is cumulative since the shop opened
    and therefore says nothing about whether they're selling *now*.
    """

    units: int
    revenue_vnd: int
    days: int
    from_at: str
    to_at: str


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
    #: Both None unless a sales source is configured.
    revenue_trend_pct: float | None
    sold_trend_pct: float | None
    #: Share within the TRACKED SET, not the market — total category size isn't
    #: knowable from shop pages. By revenue when sales data exists, else by
    #: followers; `share_basis` says which, so the UI can label it honestly.
    share_pct: float | None
    share_basis: Literal["revenue", "follower"]
    #: Sales velocity between the last two readings. None without a sales source
    #: or with fewer than two readings that have one.
    period_sales: PeriodSalesOut | None
    #: Number of readings collected so far.
    snapshot_count: int


class CompetitorDetail(BaseModel):
    competitor: CompetitorOut
    snapshots: list[SnapshotOut]


class CollectRunOut(BaseModel):
    attempted: int
    succeeded: int
    failed: int
    #: Reasons from readings that actually failed, so a broken endpoint is
    #: visible rather than silent.
    errors: list[str]
    #: Messages attached to *successful* readings — a partial capture, or "no
    #: sales source configured". Separate from `errors` because reporting
    #: "0 thất bại. Lý do: …" reads as a contradiction.
    notes: list[str]


class InsightOut(BaseModel):
    headline: str
    findings: list[str]
    actions: list[str]
    #: True when the narrative came from the LLM; False for the deterministic
    #: fallback, so the UI never implies AI wrote something it didn't.
    ai_generated: bool
