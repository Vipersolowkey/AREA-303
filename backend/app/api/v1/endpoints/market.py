"""Track 2, Đề 3 — Market Intelligence.

Two related things live under this prefix:

* ``/`` and ``/scan`` — the original one-shot pricing calculator: you supply a
  competitor's price and get a margin-safe response.
* ``/competitors/*`` — a watchlist that tracks real Shopee/Lazada shops over
  time. Paste a shop URL, the collector takes periodic readings, and the panel
  shows trend, in-set revenue share, promotions and an insight.

The whole router is admin-gated in :mod:`app.api.v1`.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_dep
from app.core.exceptions import ValidationError
from app.core.responses import ApiResponse, PageMeta
from app.schemas.competitor import (
    AddCompetitorRequest,
    CollectRunOut,
    CompetitorDetail,
    CompetitorOut,
    InsightOut,
    SnapshotOut,
)
from app.schemas.market import MarketRequest, MarketScanRequest
from app.services import competitor_insight, competitor_service
from app.services import market as service
from app.services.competitor import InvalidCompetitorUrl, Platform

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict])
async def analyze(req: MarketRequest) -> ApiResponse[dict]:
    data = await service.analyze_market(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


@router.post("/scan", response_model=ApiResponse[dict])
async def scan(req: MarketScanRequest) -> ApiResponse[dict]:
    """Multi-competitor market scan for a product from the store."""
    data = await service.scan_market(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


# --- Competitor watchlist ---------------------------------------------------


def _snapshot_out(snap) -> SnapshotOut | None:  # noqa: ANN001
    if snap is None:
        return None
    return SnapshotOut(
        captured_at=snap.captured_at.isoformat(),
        ok=snap.ok,
        error=snap.error,
        follower_count=snap.follower_count,
        rating=snap.rating,
        product_count=snap.product_count,
        items_sold_total=snap.items_sold_total,
        revenue_est_vnd=snap.revenue_est_vnd,
        voucher_count=snap.voucher_count,
        top_products=snap.top_products,
        promotions=snap.promotions,
    )


async def _build_rows(db: AsyncSession):
    """Gather (competitor, latest ok snapshot, trends, all snapshots) once."""
    competitors = await competitor_service.list_competitors(db)
    out = []
    for row in competitors:
        snaps = await competitor_service.snapshots_for(db, row.id)
        ok_snaps = [s for s in snaps if s.ok]
        out.append(
            {
                "row": row,
                "snaps": snaps,
                "latest_ok": ok_snaps[-1] if ok_snaps else None,
                "last_attempt": snaps[-1] if snaps else None,
                "follower_trend": competitor_service.trend_pct(snaps, "follower_count"),
                "product_trend": competitor_service.trend_pct(snaps, "product_count"),
                "rating_delta": competitor_service.trend_abs(snaps, "rating"),
            }
        )
    return out


@router.get("/competitors", response_model=ApiResponse[list[dict]])
async def list_tracked(db: AsyncSession = Depends(get_db_dep)) -> ApiResponse[list[dict]]:
    rows = await _build_rows(db)
    share = competitor_service.follower_share(
        {r["row"].id: r["latest_ok"] for r in rows}
    )
    items = [
        CompetitorOut(
            id=r["row"].id,
            platform=r["row"].platform,
            display_name=r["row"].display_name,
            url=r["row"].url,
            created_at=r["row"].created_at.isoformat(),
            latest=_snapshot_out(r["latest_ok"]),
            last_attempt=_snapshot_out(r["last_attempt"]),
            follower_trend_pct=r["follower_trend"],
            product_trend_pct=r["product_trend"],
            rating_delta=r["rating_delta"],
            follower_share_pct=share.get(r["row"].id),
            snapshot_count=len(r["snaps"]),
        ).model_dump()
        for r in rows
    ]
    return ApiResponse[list[dict]](
        success=True, data=items, meta=PageMeta(total=len(items)), error=None
    )


@router.post("/competitors", response_model=ApiResponse[dict])
async def add_tracked(
    req: AddCompetitorRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse[dict]:
    try:
        row = await competitor_service.add_competitor(
            db, req.url, added_by=str(user.get("sub"))
        )
    except InvalidCompetitorUrl as exc:
        # A bad paste is a user error, not a server fault.
        raise ValidationError(str(exc)) from exc

    # Take a first reading immediately so the entry isn't blank until the next
    # scheduled run — and so a broken link shows up right away.
    snap = await competitor_service.collect_one(db, row)
    return ApiResponse[dict](
        success=True,
        data=CompetitorOut(
            id=row.id,
            platform=cast(Platform, row.platform),
            display_name=row.display_name,
            url=row.url,
            created_at=row.created_at.isoformat(),
            latest=_snapshot_out(snap) if snap.ok else None,
            last_attempt=_snapshot_out(snap),
            follower_trend_pct=None,
            product_trend_pct=None,
            rating_delta=None,
            follower_share_pct=None,
            snapshot_count=1,
        ).model_dump(),
        meta=PageMeta(),
        error=None,
    )


@router.delete("/competitors/{competitor_id}", response_model=ApiResponse[dict])
async def remove_tracked(
    competitor_id: int, db: AsyncSession = Depends(get_db_dep)
) -> ApiResponse[dict]:
    await competitor_service.remove_competitor(db, competitor_id)
    return ApiResponse[dict](
        success=True, data={"id": competitor_id, "active": False}, meta=PageMeta(), error=None
    )


# Registered before /competitors/{competitor_id}: FastAPI matches routes in
# declaration order, so a static segment must come first or "insight" would
# be parsed as a competitor id and 422.
@router.get("/competitors/insight", response_model=ApiResponse[dict])
async def competitor_insight_endpoint(
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse[dict]:
    rows = await _build_rows(db)
    share = competitor_service.follower_share(
        {r["row"].id: r["latest_ok"] for r in rows}
    )
    headline, findings, actions, ai = await competitor_insight.build_insight(
        [
            competitor_insight.CompetitorReading(
                competitor=r["row"],
                latest=r["latest_ok"],
                follower_trend_pct=r["follower_trend"],
                product_trend_pct=r["product_trend"],
                rating_delta=r["rating_delta"],
            )
            for r in rows
        ],
        share,
    )
    return ApiResponse[dict](
        success=True,
        data=InsightOut(
            headline=headline, findings=findings, actions=actions, ai_generated=ai
        ).model_dump(),
        meta=PageMeta(),
        error=None,
    )


@router.get("/competitors/{competitor_id}", response_model=ApiResponse[dict])
async def tracked_detail(
    competitor_id: int, db: AsyncSession = Depends(get_db_dep)
) -> ApiResponse[dict]:
    row = await competitor_service.get_competitor(db, competitor_id)
    snaps = await competitor_service.snapshots_for(db, competitor_id)
    ok_snaps = [s for s in snaps if s.ok]
    detail = CompetitorDetail(
        competitor=CompetitorOut(
            id=row.id,
            platform=cast(Platform, row.platform),
            display_name=row.display_name,
            url=row.url,
            created_at=row.created_at.isoformat(),
            latest=_snapshot_out(ok_snaps[-1] if ok_snaps else None),
            last_attempt=_snapshot_out(snaps[-1] if snaps else None),
            follower_trend_pct=competitor_service.trend_pct(snaps, "follower_count"),
            product_trend_pct=competitor_service.trend_pct(snaps, "product_count"),
            rating_delta=competitor_service.trend_abs(snaps, "rating"),
            follower_share_pct=None,
            snapshot_count=len(snaps),
        ),
        snapshots=[s for s in (_snapshot_out(x) for x in snaps) if s is not None],
    )
    return ApiResponse[dict](
        success=True, data=detail.model_dump(), meta=PageMeta(), error=None
    )


@router.post("/competitors/collect", response_model=ApiResponse[dict])
async def collect_now(db: AsyncSession = Depends(get_db_dep)) -> ApiResponse[dict]:
    """Take a reading for every tracked shop right now.

    Marketplace endpoints are unofficial and bot-protected, so failures are
    normal — they're returned in `errors` rather than raised, and each one is
    also persisted as a snapshot so the history shows the gap and its reason.
    """
    snaps = await competitor_service.collect_all(db)
    errors = [s.error for s in snaps if s.error]
    run = CollectRunOut(
        attempted=len(snaps),
        succeeded=sum(1 for s in snaps if s.ok),
        failed=sum(1 for s in snaps if not s.ok),
        errors=[e for e in errors if e][:10],
    )
    return ApiResponse[dict](
        success=True, data=run.model_dump(), meta=PageMeta(), error=None
    )
