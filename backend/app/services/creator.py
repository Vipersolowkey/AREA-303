"""Track 2, Đề 4 — Content & Creator Performance service.

Heuristic core (deterministic):
- per creator: total attributed sales, sales per 1k views (efficiency),
  engagement rate = engagements / views.
- best content type = the type with the highest sales-per-1k-views across items.
- recommended creator = highest sales-per-1k-views (ties broken by total sales).

The KOL/KOC recommendation narrative (`insight`) runs on the LLM with a
templated fallback.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import StatisticsError, correlation
from typing import cast

from app.schemas.creator import (
    ContentType,
    CorrelationRequest,
    CorrelationResponse,
    CreatorCorrelation,
    CreatorRequest,
    CreatorResponse,
    CreatorScore,
)
from app.services import commerce_store as store
from app.services.llm_reasoning import reason_json


def _rank(req: CreatorRequest) -> tuple[list[CreatorScore], str]:
    agg: dict[str, dict] = defaultdict(
        lambda: {"sales": 0, "views": 0, "eng": 0, "types": defaultdict(int)}
    )
    type_sales: dict[str, int] = defaultdict(int)
    type_views: dict[str, int] = defaultdict(int)

    for it in req.items:
        a = agg[it.creator]
        a["sales"] += it.attributed_sales_vnd
        a["views"] += it.views
        a["eng"] += it.engagements
        a["types"][it.content_type] += it.attributed_sales_vnd
        type_sales[it.content_type] += it.attributed_sales_vnd
        type_views[it.content_type] += it.views

    scores: list[CreatorScore] = []
    for creator, a in agg.items():
        views = max(a["views"], 1)
        top_type = max(a["types"].items(), key=lambda kv: kv[1])[0]
        scores.append(
            CreatorScore(
                creator=creator,
                content_type=cast(ContentType, top_type),
                total_sales_vnd=a["sales"],
                sales_per_1k_views=int(a["sales"] / views * 1000),
                engagement_rate_pct=round(a["eng"] / views * 100, 2),
            )
        )
    scores.sort(key=lambda s: (s.sales_per_1k_views, s.total_sales_vnd), reverse=True)

    # Best content type by sales efficiency (sales per 1k views).
    best_type = max(
        type_sales,
        key=lambda t: type_sales[t] / max(type_views[t], 1),
    )
    return scores, best_type


_SYSTEM = (
    "You are a creator-marketing analyst for a Vietnamese e-commerce seller. "
    "Given ranked creator performance (sales per 1k views) for a campaign "
    "category, recommend which KOL/KOC to partner with and why, in ONE short "
    "Vietnamese paragraph (2-3 sentences). Do not invent numbers. "
    'Reply as JSON: {"insight": "..."}'
)


def _fallback_insight(req: CreatorRequest, scores: list[CreatorScore], best_type: str) -> str:
    top = scores[0]
    return (
        f"Cho chiến dịch {req.campaign_category}: nên hợp tác với '{top.creator}' — "
        f"hiệu suất cao nhất với {top.sales_per_1k_views:,}₫ doanh số/1k view "
        f"(tổng {top.total_sales_vnd:,}₫). Định dạng '{best_type}' đang chuyển đổi "
        f"tốt nhất, nên ưu tiên loại nội dung này."
    )


async def analyze_creators(req: CreatorRequest) -> CreatorResponse:
    scores, best_type = _rank(req)
    top = scores[:5]
    ranked_txt = "; ".join(
        f"{s.creator} ({s.content_type}): {s.sales_per_1k_views:,}₫/1k views, "
        f"total {s.total_sales_vnd:,}₫"
        for s in top
    )
    data = await reason_json(
        _SYSTEM,
        f"Campaign category: {req.campaign_category}. Best content type: {best_type}.\n"
        f"Ranked creators: {ranked_txt}.",
        label="creator",
    )
    insight = (data or {}).get("insight") if data else None
    return CreatorResponse(
        best_content_type=cast(ContentType, best_type),
        recommended_creator=scores[0].creator,
        top_creators=top,
        insight=(insight or "").strip() or _fallback_insight(req, scores, best_type),
    )


# --------------------------------------------------------------------------- #
# Đề 4 — creator correlation over multi-campaign history (store-grounded)
# --------------------------------------------------------------------------- #
async def analyze_correlation(req: CorrelationRequest) -> CorrelationResponse:
    ranked: list[CreatorCorrelation] = []
    for c in store.creators_for_category(req.category):
        camps = c["campaigns"]
        views = [x["views"] for x in camps]
        sales = [x["attributed_sales_vnd"] for x in camps]
        try:
            corr = round(correlation(views, sales), 3)
        except (StatisticsError, ValueError):
            corr = 0.0
        total = sum(sales)
        tv = sum(views) or 1
        ranked.append(CreatorCorrelation(
            creator=c["creator"], content_type=camps[0]["content_type"], campaigns=len(camps),
            correlation=corr, avg_sales_per_1k_views=int(total / tv * 1000), total_sales_vnd=total,
        ))
    # Rank by correlation first (consistency of content→sales), then efficiency.
    ranked.sort(key=lambda r: (r.correlation, r.avg_sales_per_1k_views), reverse=True)
    best = ranked[0].creator if ranked else ""

    txt = "; ".join(
        f"{r.creator}: corr={r.correlation}, {r.avg_sales_per_1k_views:,}₫/1k views ({r.campaigns} campaigns)"
        for r in ranked
    )
    data = await reason_json(
        "You are a creator-marketing analyst for a Vietnamese e-commerce shop. Given "
        "creators ranked by the correlation between their content views and attributed "
        "sales, recommend who is most reliable to partner with, in ONE short Vietnamese "
        'paragraph (2-3 sentences). Reply as JSON: {"insight": "..."}',
        f"Category {req.category}. Ranked: {txt}.",
        label="creator_corr",
    )
    insight = (data or {}).get("insight") if data else None
    if not (insight and insight.strip()) and ranked:
        insight = (f"'{best}' có độ tương quan content↔doanh số cao nhất ({ranked[0].correlation}) "
                   f"trên {ranked[0].campaigns} chiến dịch — đáng tin cậy nhất để hợp tác cho "
                   f"ngành {req.category}.")
    return CorrelationResponse(
        category=req.category, ranked=ranked, best_creator=best,
        insight=(insight or "Chưa đủ dữ liệu creator cho danh mục này.").strip(),
    )
