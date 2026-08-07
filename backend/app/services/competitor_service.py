"""Competitor watchlist, collection runs, and trend/share analysis."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.competitor import CompetitorSnapshot, TrackedCompetitor
from app.services.competitor import parse_competitor_url
from app.services.competitor.registry import collect as run_collector
from app.services.competitor.urls import ParsedCompetitor

#: Cap on concurrent collections — the per-host throttle in competitor.base
#: already serialises same-host traffic, this just bounds total work.
_MAX_CONCURRENT = 4


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


async def collect_one(db: AsyncSession, row: TrackedCompetitor) -> CompetitorSnapshot:
    """Collect a shop and store the reading — including a failed one.

    A failure is persisted rather than skipped: an unofficial marketplace
    endpoint breaking is exactly what the operator needs to see, and a hole in
    the series would otherwise look like the competitor going quiet.
    """
    result = await run_collector(_to_parsed(row))

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
    )
    db.add(snapshot)

    # Adopt the real shop name once we learn it.
    if result.ok and result.display_name:
        row.display_name = result.display_name

    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def collect_all(db: AsyncSession) -> list[CompetitorSnapshot]:
    """Collect every active competitor. Bounded concurrency; failures included."""
    rows = await list_competitors(db)
    if not rows:
        return []

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    async def one(row: TrackedCompetitor) -> CompetitorSnapshot:
        async with semaphore:
            return await collect_one(db, row)

    # Sequential commits: they share one AsyncSession, which is not safe to use
    # concurrently. The network wait is what dominates anyway, and the per-host
    # throttle would serialise same-marketplace calls regardless.
    out: list[CompetitorSnapshot] = []
    for row in rows:
        out.append(await one(row))
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


def follower_share(latest: dict[int, CompetitorSnapshot | None]) -> dict[int, float]:
    """Share of follower count across the tracked set.

    Follower count, not revenue: the marketplaces block their product-listing
    endpoints, so units sold and GMV aren't obtainable and any revenue share
    would be invented. This is also explicitly share *of the shops being
    watched* — total category size isn't knowable from shop pages, so calling it
    "market share" would overclaim.
    """
    totals = {
        cid: (snap.follower_count or 0)
        for cid, snap in latest.items()
        if snap is not None
    }
    grand = sum(totals.values())
    if not grand:
        return {}
    return {cid: round(v / grand * 100, 1) for cid, v in totals.items()}
