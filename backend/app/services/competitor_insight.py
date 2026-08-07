"""Turn collected competitor snapshots into findings and suggested actions.

## What there is to work with — and why it varies

Two tiers of data, because Shopee gates them differently (measured Aug 2026):

* **Always available**, anonymously: follower count · rating · product count.
  Thin for a single reading, but a *time series* carries real signal, especially
  in combination — rating falling while followers climb says something neither
  number says alone.
* **Only when a sales source is configured** (a licensed vendor feed or a
  logged-in session): units sold · estimated GMV · best sellers · promotions,
  and the derived per-period sales velocity. See :mod:`.competitor.base`.

So the analysis has to work at both levels, and must never imply it has the
second when it doesn't. Findings are computed deterministically; only the
headline runs on the LLM, and the prompt is told exactly which fields it was
given so it can't fill the gaps with plausible-sounding revenue. `ai_generated`
is reported so the UI never credits AI for the fallback line.

## Why period sales beats cumulative GMV

`historical_sold` counts everything since the shop opened, so a shop that sold
500k units in 2019 and nothing since reports the same figure as one selling that
much now. The difference between two readings is current velocity, which is the
number that actually informs a decision — so when it's available, it leads.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.competitor import CompetitorSnapshot, TrackedCompetitor
from app.services.competitor_service import PeriodSales
from app.services.llm_reasoning import reason_json

_SYSTEM_BASE = (
    "You analyse Vietnamese e-commerce competitor tracking data for a seller "
    "dashboard. Write ONE short headline (max 25 words) naming the single most "
    "decision-relevant thing the seller should notice, citing an actual number "
    "from the data given. Never invent or estimate a figure that is not in the "
    "data. The dashboard is Vietnamese-only — write IN VIETNAMESE. "
    'Reply as JSON: {"headline": "..."}'
)

#: Appended when no snapshot in the set has a sales source. Without this the
#: model reliably invents revenue figures, because a competitor-analysis prompt
#: reads like one that should have them.
_NO_SALES_NOTE = (
    " You are given ONLY: follower count, rating, product count, their change "
    "over the tracked period, and share of followers within the watched set. "
    "Sales, revenue, units sold and best-seller data are NOT available for these "
    "shops and must never be mentioned, estimated, or implied."
)

#: Appended when sales figures are present.
_SALES_NOTE = (
    " Sales figures are included for some shops. 'bán trong kỳ' is units sold "
    "BETWEEN the last two readings — actual current velocity — and is more "
    "meaningful than the cumulative total, so prefer it. GMV figures are "
    "estimates from price × units, not reported by the marketplace: never state "
    "one as an official figure. For shops with no sales figures, say nothing "
    "about their sales."
)

#: Below this, a follower move is noise rather than momentum.
_FOLLOWER_MOVE_PCT = 2.0
#: A rating is a cumulative average, so even a small drop means a lot of recent
#: bad reviews.
_RATING_DROP = -0.05
_CATALOGUE_MOVE_PCT = 5.0


#: A period-over-period sales move below this is noise.
_SALES_MOVE_PCT = 10.0


@dataclass
class CompetitorReading:
    """One competitor's latest state plus how it changed.

    The `revenue_*` / `sold_*` / `period` fields are None whenever no sales
    source was configured for that reading, which is the default. Every consumer
    has to handle that, so they're typed as optional rather than defaulted to 0 —
    a zero would read as "sold nothing", which is a different claim.
    """

    competitor: TrackedCompetitor
    latest: CompetitorSnapshot | None
    follower_trend_pct: float | None
    product_trend_pct: float | None
    rating_delta: float | None
    revenue_trend_pct: float | None = None
    sold_trend_pct: float | None = None
    period: PeriodSales | None = None

    @property
    def has_sales(self) -> bool:
        return self.latest is not None and self.latest.sales_source is not None


def _n(value: int | None) -> str:
    return f"{value:,}".replace(",", ".") if value else "—"


def _vnd(value: int | None) -> str:
    """Round to a unit a person reads at a glance, not to the dong."""
    if not value:
        return "—"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f} tỷ₫"
    if value >= 1_000_000:
        return f"{round(value / 1_000_000)} triệu₫"
    return f"{_n(value)}₫"


def build_findings(
    readings: list[CompetitorReading], share: dict[int, float]
) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    actions: list[str] = []

    usable = [r for r in readings if r.latest is not None]
    if not usable:
        return (
            ["Chưa thu được dữ liệu nào từ các cửa hàng đang theo dõi."],
            [
                "Kiểm tra lại link cửa hàng, hoặc chạy lại thu thập — "
                "sàn có thể đang chặn truy cập tự động."
            ],
        )

    # Who's biggest. Revenue is the better scale measure, so it leads when a
    # sales source supplied it; followers are the fallback.
    with_sales = [r for r in usable if r.has_sales]
    if with_sales:
        top = max(with_sales, key=lambda r: r.latest.revenue_est_vnd or 0)  # type: ignore[union-attr]
        if top.latest and top.latest.revenue_est_vnd:
            pct = share.get(top.competitor.id)
            share_txt = f" — {pct}% doanh thu của nhóm" if pct else ""
            findings.append(
                f"{top.competitor.display_name} dẫn đầu nhóm: GMV ước tính "
                f"{_vnd(top.latest.revenue_est_vnd)}{share_txt}."
            )
    else:
        leader = max(usable, key=lambda r: r.latest.follower_count or 0)  # type: ignore[union-attr]
        if leader.latest and leader.latest.follower_count:
            pct = share.get(leader.competitor.id)
            share_txt = f" — {pct}% lượng follower của nhóm" if pct else ""
            findings.append(
                f"{leader.competitor.display_name} lớn nhất nhóm: "
                f"{_n(leader.latest.follower_count)} follower{share_txt}."
            )

    # Current selling velocity — the strongest signal in the whole feature when
    # it's available, so it goes near the top.
    for r in sorted(
        (r for r in usable if r.period is not None),
        key=lambda r: r.period.units,  # type: ignore[union-attr]
        reverse=True,
    )[:2]:
        assert r.period is not None
        days = max(1, (r.period.to_at - r.period.from_at).days)
        per_day = r.period.units // days
        findings.append(
            f"{r.competitor.display_name} bán {_n(r.period.units)} sản phẩm trong "
            f"{days} ngày qua (~{_n(per_day)}/ngày, ≈{_vnd(r.period.revenue_vnd)})."
        )

    # A sales jump means something changed — a campaign, a price cut, a new hit.
    for r in usable:
        move = r.sold_trend_pct
        if move is None or abs(move) < _SALES_MOVE_PCT:
            continue
        if move > 0:
            findings.append(
                f"{r.competitor.display_name} tăng {move}% số đã bán trong kỳ theo dõi."
            )
            actions.append(
                f"{r.competitor.display_name} đang bán nhanh hơn — xem họ vừa đổi giá, "
                "chạy voucher hay lên sản phẩm mới nào."
            )
        else:
            findings.append(
                f"{r.competitor.display_name} giảm {abs(move)}% số đã bán — đang chậm lại."
            )
            actions.append(
                f"{r.competitor.display_name} chững lại — thời điểm tốt để đẩy quảng cáo "
                "vào đúng nhóm sản phẩm họ đang yếu."
            )

    # What they discount tells you where their margin is.
    for r in usable:
        promos = r.latest.promotions if r.latest else None
        if not isinstance(promos, list) or not promos:
            continue
        deepest = max(
            promos,
            key=lambda p: (p or {}).get("discount_pct") or 0 if isinstance(p, dict) else 0,
        )
        if isinstance(deepest, dict) and deepest.get("discount_pct"):
            findings.append(
                f"{r.competitor.display_name} đang giảm giá {len(promos)} sản phẩm, "
                f"sâu nhất −{round(float(deepest['discount_pct']))}% "
                f"({str(deepest.get('name') or '')[:40]})."
            )
            actions.append(
                f"Đối chiếu giá của m với {len(promos)} sản phẩm đang giảm của "
                f"{r.competitor.display_name} — đừng để bị so sánh trực tiếp mà thua giá."
            )

    # Momentum: follower growth is the best available proxy for traffic spend.
    growing = [r for r in usable if (r.follower_trend_pct or 0) >= _FOLLOWER_MOVE_PCT]
    for r in sorted(growing, key=lambda r: r.follower_trend_pct or 0, reverse=True)[:2]:
        findings.append(
            f"{r.competitor.display_name} tăng {r.follower_trend_pct}% follower trong kỳ theo dõi."
        )
        actions.append(
            f"{r.competitor.display_name} đang hút người theo dõi nhanh — "
            "xem họ chạy campaign hay nội dung gì."
        )

    # Catalogue velocity: new SKUs usually precede a push.
    for r in usable:
        move = r.product_trend_pct
        if move is None:
            continue
        if move >= _CATALOGUE_MOVE_PCT:
            findings.append(
                f"{r.competitor.display_name} mở rộng danh mục {move}% "
                f"(hiện {_n(r.latest.product_count)} sản phẩm)."  # type: ignore[union-attr]
            )
            actions.append(
                f"Danh mục {r.competitor.display_name} phình ra — thường là dấu hiệu "
                "sắp có đợt đẩy hàng, chuẩn bị phương án giữ khách."
            )
        elif move <= -_CATALOGUE_MOVE_PCT:
            findings.append(
                f"{r.competitor.display_name} giảm {abs(move)}% số sản phẩm — "
                "có thể cắt SKU hoặc đang hết hàng."
            )
            actions.append(
                f"{r.competitor.display_name} thu hẹp danh mục — cơ hội giành khách "
                "ở những sản phẩm họ vừa bỏ."
            )

    # Rating drift, and the combination that matters most.
    for r in usable:
        if r.rating_delta is None or r.rating_delta > _RATING_DROP:
            continue
        findings.append(
            f"{r.competitor.display_name} tụt {abs(r.rating_delta)} điểm đánh giá "
            f"(còn {r.latest.rating})."  # type: ignore[union-attr]
        )
        if (r.follower_trend_pct or 0) >= _FOLLOWER_MOVE_PCT:
            # The most actionable pattern available from these four fields.
            findings.append(
                f"{r.competitor.display_name} vừa tăng follower vừa tụt đánh giá — "
                "dấu hiệu lớn nhanh hơn khả năng phục vụ."
            )
            actions.append(
                f"Khách của {r.competitor.display_name} đang bớt hài lòng trong khi shop "
                "vẫn hút người mới — cạnh tranh bằng độ tin cậy (giao nhanh, đổi trả dễ) "
                "sẽ hiệu quả hơn là hạ giá."
            )
        else:
            actions.append(
                f"Đọc review mới của {r.competitor.display_name} để biết họ đang bị "
                "phàn nàn điều gì — và tránh đúng lỗi đó."
            )

    # Surface collector breakage as a finding rather than a silent gap.
    broken = [r.competitor.display_name for r in readings if r.latest is None]
    if broken:
        findings.append(
            f"Chưa có dữ liệu hợp lệ cho: {', '.join(str(b) for b in broken)}."
        )

    if len(usable) >= 2 and not any("tăng" in f or "giảm" in f or "tụt" in f for f in findings):
        findings.append(
            "Các cửa hàng theo dõi đang đi ngang — chưa có chuyển động đáng chú ý."
        )
    if not actions:
        actions.append("Tiếp tục theo dõi — cần thêm vài kỳ dữ liệu để thấy xu hướng rõ.")
    return findings, actions


def _facts_for(r: CompetitorReading, share: dict[int, float]) -> str:
    if r.latest is None:
        return f"{r.competitor.display_name} ({r.competitor.platform}): chưa có dữ liệu"

    parts = [
        f"follower={r.latest.follower_count}",
        f"rating={r.latest.rating}",
        f"số sản phẩm={r.latest.product_count}",
        f"thay đổi follower={r.follower_trend_pct}%",
        f"thay đổi số SP={r.product_trend_pct}%",
        f"thay đổi rating={r.rating_delta}",
        f"share trong nhóm={share.get(r.competitor.id)}%",
    ]
    if r.has_sales:
        parts += [
            f"đã bán tích luỹ={r.latest.items_sold_total}",
            f"GMV ước tính={r.latest.revenue_est_vnd}",
            f"thay đổi số đã bán={r.sold_trend_pct}%",
            f"thay đổi GMV={r.revenue_trend_pct}%",
            f"số SP đang giảm giá={len(r.latest.promotions or [])}",
        ]
        if r.period is not None:
            days = max(1, (r.period.to_at - r.period.from_at).days)
            parts.append(
                f"bán trong kỳ={r.period.units} sản phẩm/{days} ngày "
                f"(≈{r.period.revenue_vnd}₫)"
            )
    else:
        # Stated explicitly rather than omitted: a missing field invites the model
        # to fill it, a declared absence does not.
        parts.append("số liệu bán hàng=KHÔNG CÓ")
    return f"{r.competitor.display_name} ({r.competitor.platform}): " + ", ".join(parts)


async def build_insight(
    readings: list[CompetitorReading], share: dict[int, float]
) -> tuple[str, list[str], list[str], bool]:
    """Return (headline, findings, actions, ai_generated)."""
    findings, actions = build_findings(readings, share)

    any_sales = any(r.has_sales for r in readings)
    system = _SYSTEM_BASE + (_SALES_NOTE if any_sales else _NO_SALES_NOTE)
    facts = [_facts_for(r, share) for r in readings]

    data = await reason_json(system, "\n".join(facts), max_tokens=160, label="competitor")
    headline = ((data or {}).get("headline") or "").strip() if data else ""
    if headline:
        return headline, findings, actions, True

    # Deterministic fallback — the first finding is already the most salient one.
    return (
        findings[0] if findings else "Chưa đủ dữ liệu để kết luận.",
        findings,
        actions,
        False,
    )
