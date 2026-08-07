"""Competitor watchlist, collection runs, and trend/share analysis."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.competitor import CompetitorSnapshot, TrackedCompetitor
from app.services import shopee_session_service
from app.services.competitor import parse_competitor_url
from app.services.competitor import session as session_mod
from app.services.competitor.registry import collect as run_collector
from app.services.competitor.session import ShopeeSessionReader
from app.services.competitor.urls import ParsedCompetitor

log = get_logger("app.services.competitor_service")


async def add_competitor(
    db: AsyncSession, url: str, *, added_by: str | None = None
) -> TrackedCompetitor:
    """Track a shop from a pasted URL. Raises InvalidCompetitorUrl / ConflictError."""
    parsed = parse_competitor_url(url)

    existing = await db.execute(
        select(TrackedCompetitor).where(
            TrackedCompetitor.platform == parsed.platform,
            TrackedCompetitor.shop_ref == parsed.ref,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Cửa hàng này đã có trong danh sách theo dõi.")

    row = TrackedCompetitor(
        platform=parsed.platform,
        shop_ref=parsed.ref,
        shop_id=parsed.shop_id,
        shop_slug=parsed.shop_slug,
        url=parsed.url,
        # Replaced by the real shop name on the first successful collection.
        display_name=parsed.shop_slug or f"{parsed.platform}:{parsed.ref}",
        added_by=added_by,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Cửa hàng này đã có trong danh sách theo dõi.") from exc
    await db.refresh(row)
    return row


async def list_competitors(db: AsyncSession) -> list[TrackedCompetitor]:
    result = await db.execute(
        select(TrackedCompetitor)
        .where(TrackedCompetitor.active.is_(True))
        .order_by(TrackedCompetitor.created_at.asc())
    )
    return list(result.scalars().all())


async def get_competitor(db: AsyncSession, competitor_id: int) -> TrackedCompetitor:
    row = await db.get(TrackedCompetitor, competitor_id)
    if row is None:
        raise NotFoundError(f"Không tìm thấy cửa hàng theo dõi #{competitor_id}.")
    return row


async def remove_competitor(db: AsyncSession, competitor_id: int) -> None:
    """Soft-delete: keeps the collected history rather than dropping the series."""
    row = await get_competitor(db, competitor_id)
    row.active = False
    await db.commit()


async def snapshots_for(
    db: AsyncSession, competitor_id: int, limit: int = 60
) -> list[CompetitorSnapshot]:
    result = await db.execute(
        select(CompetitorSnapshot)
        .where(CompetitorSnapshot.competitor_id == competitor_id)
        .order_by(CompetitorSnapshot.captured_at.desc())
        .limit(limit)
    )
    # Oldest first, so charts read left-to-right.
    return list(reversed(result.scalars().all()))


async def latest_snapshot(
    db: AsyncSession, competitor_id: int, *, only_ok: bool = True
) -> CompetitorSnapshot | None:
    stmt = select(CompetitorSnapshot).where(
        CompetitorSnapshot.competitor_id == competitor_id
    )
    if only_ok:
        stmt = stmt.where(CompetitorSnapshot.ok.is_(True))
    result = await db.execute(stmt.order_by(CompetitorSnapshot.captured_at.desc()).limit(1))
    return result.scalar_one_or_none()


def _to_parsed(row: TrackedCompetitor) -> ParsedCompetitor:
    return ParsedCompetitor(
        platform=row.platform,  # type: ignore[arg-type]
        shop_id=row.shop_id,
        shop_slug=row.shop_slug,
        url=row.url,
    )


@asynccontextmanager
async def _sales_reader(
    db: AsyncSession, user_id: int | None
) -> AsyncIterator[ShopeeSessionReader | None]:
    """Own one browser for a collection run, or none if no session is available.

    Two sources, in order:

    1. The signed-in user's own connected Shopee account. This is the product
       path — each user connects their own login, so no shared credential exists.
    2. `COMPETITOR_SESSION_PATH`, an operator-wide file. Single-tenant dev only.

    On exit, a credential-level failure during the run deactivates that user's
    connection, so the UI can ask for a reconnect instead of launching a browser
    every run to be refused again.

    Yielding None rather than a disabled reader keeps the "not available" check in
    one place: the collector treats None as "no session", so there is no second
    code path for the disabled case.
    """
    state = await shopee_session_service.storage_state_for(db, user_id) if user_id else None

    if state is None:
        usable, reason = session_mod.is_configured()
        if not usable:
            if reason:
                # Enabled but unusable is a misconfiguration, and silence here is
                # what makes it look like the feature is merely empty.
                log.warning("competitor.session.unavailable", reason=reason)
            yield None
            return
        async with ShopeeSessionReader() as reader:
            yield reader
        return

    reader = ShopeeSessionReader(state)
    try:
        async with reader:
            yield reader
    finally:
        if reader.session_expired and user_id is not None:
            await shopee_session_service.mark_result(
                db,
                user_id,
                ok=False,
                expired=True,
                error="Shopee từ chối phiên khi thu thập — cần kết nối lại.",
            )


async def collect_one(
    db: AsyncSession,
    row: TrackedCompetitor,
    *,
    user_id: int | None = None,
    sales_reader: ShopeeSessionReader | None = None,
) -> CompetitorSnapshot:
    """Collect a shop and store the reading — including a failed one.

    A failure is persisted rather than skipped: an unofficial marketplace
    endpoint breaking is exactly what the operator needs to see, and a hole in
    the series would otherwise look like the competitor going quiet.

    `sales_reader` is passed in by :func:`collect_all` so one browser serves the
    whole run. Called on its own, it opens and closes its own.
    """
    if sales_reader is None:
        async with _sales_reader(db, user_id) as reader:
            return await _collect_and_store(db, row, reader)
    return await _collect_and_store(db, row, sales_reader)


async def _collect_and_store(
    db: AsyncSession,
    row: TrackedCompetitor,
    sales_reader: ShopeeSessionReader | None,
) -> CompetitorSnapshot:
    result = await run_collector(_to_parsed(row), sales_reader=sales_reader)

    snapshot = CompetitorSnapshot(
        competitor_id=row.id,
        captured_at=datetime.now(UTC),
        ok=result.ok,
        error=result.error,
        follower_count=result.follower_count,
        rating=result.rating,
        product_count=result.product_count,
        items_sold_total=result.items_sold_total,
        revenue_est_vnd=result.revenue_est_vnd,
        voucher_count=result.voucher_count,
        top_products=[
            {
                "name": p.name,
                "price_vnd": p.price_vnd,
                "sold": p.sold,
                "discount_pct": p.discount_pct,
            }
            for p in result.top_products
        ]
        or None,
        promotions=result.promotions or None,
        sales_source=result.sales_source,
    )
    db.add(snapshot)

    # Adopt the real shop name once we learn it.
    if result.ok and result.display_name:
        row.display_name = result.display_name

    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def collect_all(
    db: AsyncSession, *, user_id: int | None = None
) -> list[CompetitorSnapshot]:
    """Collect every active competitor. Failures are stored, not skipped.

    `user_id` selects whose Shopee connection to read sales with — the signed-in
    user for an on-demand run. None means shop-level fields only (plus the
    operator-wide dev file, if one is configured).
    """
    rows = await list_competitors(db)
    if not rows:
        return []

    # Sequential: the rows share one AsyncSession, which is not safe to use
    # concurrently. The network wait dominates anyway, and both the per-host
    # throttle and the session reader's own lock would serialise same-marketplace
    # calls regardless.
    async with _sales_reader(db, user_id) as reader:
        out: list[CompetitorSnapshot] = []
        for row in rows:
            out.append(await _collect_and_store(db, row, reader))
        return out


def trend_pct(snapshots: list[CompetitorSnapshot], field: str) -> float | None:
    """Percent change in a field between the first and last successful reading."""
    values = [
        getattr(s, field) for s in snapshots if s.ok and getattr(s, field) is not None
    ]
    if len(values) < 2:
        return None
    first, last = values[0], values[-1]
    if not first:
        return None
    return round((last - first) / first * 100, 1)


def trend_abs(snapshots: list[CompetitorSnapshot], field: str) -> float | None:
    """Absolute change first→last. Used for rating, where a percentage of a
    4.9-out-of-5 average is meaningless but a −0.12 drop is not."""
    values = [
        getattr(s, field) for s in snapshots if s.ok and getattr(s, field) is not None
    ]
    if len(values) < 2:
        return None
    return round(values[-1] - values[0], 2)


def _share(latest: dict[int, CompetitorSnapshot | None], field: str) -> dict[int, float]:
    totals = {
        cid: (getattr(snap, field) or 0)
        for cid, snap in latest.items()
        if snap is not None
    }
    grand = sum(totals.values())
    if not grand:
        return {}
    return {cid: round(v / grand * 100, 1) for cid, v in totals.items()}


def follower_share(latest: dict[int, CompetitorSnapshot | None]) -> dict[int, float]:
    """Share of follower count across the tracked set.

    Always available, since follower count needs no privileged source. Note this
    is share *of the shops being watched* — total category size isn't knowable
    from shop pages, so calling it "market share" would overclaim.
    """
    return _share(latest, "follower_count")


def revenue_share(latest: dict[int, CompetitorSnapshot | None]) -> dict[int, float]:
    """Share of estimated revenue across the tracked set.

    Only non-empty when a sales source is configured, since GMV is unobtainable
    anonymously. Same caveat as :func:`follower_share`: share of the watchlist,
    not of the market.
    """
    return _share(latest, "revenue_est_vnd")


@dataclass(frozen=True)
class PeriodSales:
    """Units and revenue moved *between* the last two readings.

    This is the number `historical_sold` can't give you. `historical_sold` is
    cumulative since the shop opened, so a shop that sold 500k units in 2019 and
    nothing since still reports 500k — indistinguishable from one selling that
    much now. The difference between two readings is actual current velocity.

    `revenue_vnd` is priced at the later snapshot's average selling price, so a
    mid-period price change is approximated, not modelled.
    """

    units: int
    revenue_vnd: int
    from_at: datetime
    to_at: datetime


def period_sales(snapshots: list[CompetitorSnapshot]) -> PeriodSales | None:
    """Sales between the two most recent readings that both carry sales data.

    Returns None with fewer than two such readings, or if the count went
    backwards — which happens when Shopee resets a counter or when the two
    readings sampled different product sets, and a negative "sold this period"
    is worse than no figure at all.
    """
    usable = [
        s
        for s in snapshots
        if s.ok and s.items_sold_total is not None and s.sales_source is not None
    ]
    if len(usable) < 2:
        return None
    prev, curr = usable[-2], usable[-1]
    units = (curr.items_sold_total or 0) - (prev.items_sold_total or 0)
    if units < 0:
        return None

    # Price the period's units at the later reading's average selling price.
    # Deriving it from that snapshot's own totals keeps the two figures
    # consistent even when the sampled product set changed.
    avg_price = 0
    if curr.items_sold_total and curr.revenue_est_vnd:
        avg_price = curr.revenue_est_vnd // curr.items_sold_total
    return PeriodSales(
        units=units,
        revenue_vnd=units * avg_price,
        from_at=prev.captured_at,
        to_at=curr.captured_at,
    )
