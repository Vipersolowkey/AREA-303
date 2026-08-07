"""Competitor watchlist + the time series collected for each entry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class TrackedCompetitor(Base, TimestampMixin):
    """A shop someone pasted a URL for. Collection runs against these."""

    __tablename__ = "tracked_competitors"
    # One row per shop per platform, so pasting the same shop twice (or the same
    # shop via a product link and a shop link) doesn't create a second series.
    __table_args__ = (UniqueConstraint("platform", "shop_ref", name="uq_competitor_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    #: Stable identity — numeric shop id when available, else the slug.
    shop_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    shop_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shop_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    #: Filled in by the first successful collection; the pasted URL until then.
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Which account added it (nullable — the seller portal is single-tenant today).
    added_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    snapshots: Mapped[list[CompetitorSnapshot]] = relationship(
        back_populates="competitor", cascade="all, delete-orphan"
    )


class CompetitorSnapshot(Base, TimestampMixin):
    """One collection attempt.

    Failures are stored as rows too (``ok=False`` + ``error``) rather than
    dropped: an unofficial marketplace endpoint breaking is exactly the thing
    the operator needs to see, and a gap in the series would otherwise look
    like the competitor went quiet.
    """

    __tablename__ = "competitor_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(
        ForeignKey("tracked_competitors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Everything below is nullable: a marketplace may expose some fields and not
    # others, and a partial capture is more useful than none.
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_sold_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Derived: sum(price × historical units sold) over the products we saw.
    #: An estimate of cumulative GMV, not a reported figure. BigInteger because
    #: a mid-size shop clears 2.1 billion VND — the int4 ceiling — easily.
    revenue_est_vnd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    voucher_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Which source produced the sales fields above: "vendor" (licensed data
    #: feed) or "session" (logged-in browser). None means shop-level fields only,
    #: which is what an anonymous read can get. Stored per snapshot because the
    #: available source changes over a series, and a chart that silently mixes a
    #: vendor's figures with a scraper's is a chart that lies.
    sales_source: Mapped[str | None] = mapped_column(String(16), nullable=True)

    #: [{name, price_vnd, sold, discount_pct}] for the best sellers we saw.
    top_products: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    #: Promotions/vouchers visible at capture time.
    promotions: Mapped[Any | None] = mapped_column(JSONB, nullable=True)

    competitor: Mapped[TrackedCompetitor] = relationship(back_populates="snapshots")
