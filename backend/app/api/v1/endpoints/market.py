"""Track 2, Đề 3 — Market Intelligence.

Two related things live under this prefix:

* ``/`` and ``/scan`` — the original one-shot pricing calculator: you supply a
  competitor's price and get a margin-safe response.
* ``/competitors/*`` — a watchlist that tracks real Shopee shops over time.
  Paste a shop URL, the collector takes periodic readings, and the panel shows
  trends, in-set share, promotions and an insight.

  Readings come in two tiers: shop-level fields (followers, rating, product
  count) always, and sales fields only when a vendor feed or a logged-in session
  is configured — Shopee serves those exclusively to authenticated callers. Every
  response carries `sales_source` and `share_basis` so the client can label what
  it's showing rather than imply data it doesn't have. See
  :mod:`app.services.competitor.base`.

The whole router is admin-gated in :mod:`app.api.v1`.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_dep
from app.core import crypto
from app.core.exceptions import ValidationError
from app.core.responses import ApiResponse, PageMeta
from app.schemas.competitor import (
    AddCompetitorRequest,
    CollectRunOut,
    CompetitorDetail,
    CompetitorOut,
    ConnectShopeeRequest,
    InsightOut,
    PeriodSalesOut,
    ShopeeConnectionOut,
    SnapshotOut,
)
from app.schemas.market import MarketRequest, MarketScanRequest
from app.services import competitor_insight, competitor_service, shopee_session_service
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
        sales_source=snap.sales_source,
    )


def _period_out(period) -> PeriodSalesOut | None:  # noqa: ANN001
    if period is None:
        return None
    return PeriodSalesOut(
        units=period.units,
        revenue_vnd=period.revenue_vnd,
        days=max(1, (period.to_at - period.from_at).days),
        from_at=period.from_at.isoformat(),
        to_at=period.to_at.isoformat(),
    )


async def _build_rows(db: AsyncSession) -> list[dict]:
    """Gather (competitor, latest ok snapshot, trends, all snapshots) once."""
    competitors = await competitor_service.list_competitors(db)
    out: list[dict] = []
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
                "revenue_trend": competitor_service.trend_pct(snaps, "revenue_est_vnd"),
                "sold_trend": competitor_service.trend_pct(snaps, "items_sold_total"),
                "period": competitor_service.period_sales(snaps),
            }
        )
    return out


def _shares(rows: list[dict]) -> tuple[dict[int, float], str]:
    """In-set share, by revenue when a sales source supplied it.

    Falls back to followers rather than returning nothing, so the badge still
    means something before a sales source is configured — but the basis is
    returned alongside so the label can say which it is. Presenting a follower
    share as a revenue share would be the one genuinely misleading option.
    """
    latest = {r["row"].id: r["latest_ok"] for r in rows}
    by_revenue = competitor_service.revenue_share(latest)
    if by_revenue:
        return by_revenue, "revenue"
    return competitor_service.follower_share(latest), "follower"


def _competitor_out(
    row, *, snaps, latest_ok, last_attempt, share_pct, share_basis, **trends
) -> CompetitorOut:  # noqa: ANN001
    return CompetitorOut(
        id=row.id,
        platform=cast(Platform, row.platform),
        display_name=row.display_name,
        url=row.url,
        created_at=row.created_at.isoformat(),
        latest=_snapshot_out(latest_ok),
        last_attempt=_snapshot_out(last_attempt),
        follower_trend_pct=trends.get("follower_trend"),
        product_trend_pct=trends.get("product_trend"),
        rating_delta=trends.get("rating_delta"),
        revenue_trend_pct=trends.get("revenue_trend"),
        sold_trend_pct=trends.get("sold_trend"),
        share_pct=share_pct,
        share_basis=cast(Any, share_basis),
        period_sales=_period_out(trends.get("period")),
        snapshot_count=len(snaps),
    )


@router.get("/competitors", response_model=ApiResponse[list[dict]])
async def list_tracked(db: AsyncSession = Depends(get_db_dep)) -> ApiResponse[list[dict]]:
    rows = await _build_rows(db)
    share, basis = _shares(rows)
    items = [
        _competitor_out(
            r["row"],
            snaps=r["snaps"],
            latest_ok=r["latest_ok"],
            last_attempt=r["last_attempt"],
            share_pct=share.get(r["row"].id),
            share_basis=basis,
            follower_trend=r["follower_trend"],
            product_trend=r["product_trend"],
            rating_delta=r["rating_delta"],
            revenue_trend=r["revenue_trend"],
            sold_trend=r["sold_trend"],
            period=r["period"],
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
    snap = await competitor_service.collect_one(db, row, user_id=int(user["sub"]))
    return ApiResponse[dict](
        success=True,
        data=_competitor_out(
            row,
            snaps=[snap],
            latest_ok=snap if snap.ok else None,
            last_attempt=snap,
            # A single reading supports no trend and no share of anything.
            share_pct=None,
            share_basis="follower",
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
    share, _basis = _shares(rows)
    headline, findings, actions, ai = await competitor_insight.build_insight(
        [
            competitor_insight.CompetitorReading(
                competitor=r["row"],
                latest=r["latest_ok"],
                follower_trend_pct=r["follower_trend"],
                product_trend_pct=r["product_trend"],
                rating_delta=r["rating_delta"],
                revenue_trend_pct=r["revenue_trend"],
                sold_trend_pct=r["sold_trend"],
                period=r["period"],
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
        competitor=_competitor_out(
            row,
            snaps=snaps,
            latest_ok=ok_snaps[-1] if ok_snaps else None,
            last_attempt=snaps[-1] if snaps else None,
            # Share is relative to the watchlist, which a single-shop view has
            # no visibility of.
            share_pct=None,
            share_basis="follower",
            follower_trend=competitor_service.trend_pct(snaps, "follower_count"),
            product_trend=competitor_service.trend_pct(snaps, "product_count"),
            rating_delta=competitor_service.trend_abs(snaps, "rating"),
            revenue_trend=competitor_service.trend_pct(snaps, "revenue_est_vnd"),
            sold_trend=competitor_service.trend_pct(snaps, "items_sold_total"),
            period=competitor_service.period_sales(snaps),
        ),
        snapshots=[s for s in (_snapshot_out(x) for x in snaps) if s is not None],
    )
    return ApiResponse[dict](
        success=True, data=detail.model_dump(), meta=PageMeta(), error=None
    )


# --- The signed-in user's own Shopee connection ------------------------------


def _connection_out(row) -> ShopeeConnectionOut:  # noqa: ANN001
    can_connect = crypto.is_available()
    if row is None:
        return ShopeeConnectionOut(
            connected=False,
            expired=False,
            shopee_username=None,
            connected_at=None,
            last_ok_at=None,
            last_error=None,
            can_connect=can_connect,
        )
    return ShopeeConnectionOut(
        # A row that Shopee has started refusing is still a connection the user
        # made — reported as connected-but-expired so the UI says "kết nối lại"
        # rather than pretending it never happened.
        connected=True,
        expired=not row.active,
        shopee_username=row.shopee_username,
        connected_at=row.created_at.isoformat(),
        last_ok_at=row.last_ok_at.isoformat() if row.last_ok_at else None,
        last_error=row.last_error,
        can_connect=can_connect,
    )


@router.get("/shopee-connection", response_model=ApiResponse[dict])
async def shopee_connection_status(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse[dict]:
    row = await shopee_session_service.get_session(db, int(user["sub"]))
    return ApiResponse[dict](
        success=True, data=_connection_out(row).model_dump(), meta=PageMeta(), error=None
    )


@router.post("/shopee-connection", response_model=ApiResponse[dict])
async def connect_shopee(
    req: ConnectShopeeRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse[dict]:
    """Attach the caller's own Shopee login, after proving it works.

    The jar is narrowed to Shopee cookies and encrypted before storage, and a
    real shop read has to succeed first — see
    :mod:`app.services.shopee_session_service` for why both matter.
    """
    row = await shopee_session_service.connect(
        db,
        int(user["sub"]),
        storage_state=req.storage_state,
        shopee_username=req.shopee_username,
    )
    return ApiResponse[dict](
        success=True, data=_connection_out(row).model_dump(), meta=PageMeta(), error=None
    )


@router.delete("/shopee-connection", response_model=ApiResponse[dict])
async def disconnect_shopee(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse[dict]:
    """Delete the stored credential outright — not a soft delete."""
    await shopee_session_service.disconnect(db, int(user["sub"]))
    return ApiResponse[dict](
        success=True, data={"connected": False}, meta=PageMeta(), error=None
    )


@router.post("/competitors/collect", response_model=ApiResponse[dict])
async def collect_now(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_dep),
) -> ApiResponse[dict]:
    """Take a reading for every tracked shop right now.

    Sales figures are read with the caller's own Shopee connection when they have
    one. Marketplace endpoints are unofficial, so failures are normal — they're
    returned in `errors` rather than raised, and each is also persisted as a
    snapshot so the history shows the gap and its reason.
    """
    snaps = await competitor_service.collect_all(db, user_id=int(user["sub"]))
    # A message on a successful reading is a note (partial capture, or no sales
    # source configured), not a failure — keeping them apart stops the UI from
    # saying "0 thất bại" and then listing reasons.
    run = CollectRunOut(
        attempted=len(snaps),
        succeeded=sum(1 for s in snaps if s.ok),
        failed=sum(1 for s in snaps if not s.ok),
        errors=[s.error for s in snaps if s.error and not s.ok][:10],
        # Deduplicated: "chưa cấu hình nguồn" is identical for every shop, and
        # repeating it once per row buries anything shop-specific.
        notes=list(dict.fromkeys(s.error for s in snaps if s.error and s.ok))[:5],
    )
    return ApiResponse[dict](
        success=True, data=run.model_dump(), meta=PageMeta(), error=None
    )
