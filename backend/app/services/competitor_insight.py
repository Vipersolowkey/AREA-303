"""Turn collected competitor snapshots into findings and suggested actions.

## What there is to work with

Live testing (Aug 2026) showed the marketplaces guard their product-listing
endpoints while leaving the shop profile open: Shopee's ``get_shop_base``
answers, but every item/search endpoint 403s, and Lazada serves a bot-check
page instead of JSON. So units sold, GMV, best sellers and vouchers are simply
not obtainable, and the analysis is built on the four fields that are:

    follower count · rating · product count · shop name

Four numbers is thin for a single reading, but a *time series* of them carries
real signal — especially in combination (rating falling while followers climb
says something neither number says alone).

Findings are computed deterministically; only the headline runs on the LLM, and
`ai_generated` is reported so the UI never credits AI for the fallback line.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.competitor import CompetitorSnapshot, TrackedCompetitor
from app.services.llm_reasoning import reason_json

_SYSTEM = (
    "You analyse Vietnamese e-commerce competitor tracking data for a seller "
    "dashboard. You are given, per competitor shop: follower count, rating, "
    "product count, their change over the tracked period, and share of "
    "followers within the watched set. Note that sales and revenue figures are "
    "NOT available and must never be mentioned or guessed. Write ONE short "
    "headline (max 25 words) naming the single most decision-relevant thing the "
    "seller should notice, citing an actual number. Do not invent data. The "
    "dashboard is Vietnamese-only — write IN VIETNAMESE. "
    'Reply as JSON: {"headline": "..."}'
)

#: Below this, a follower move is noise rather than momentum.
_FOLLOWER_MOVE_PCT = 2.0
#: A rating is a cumulative average, so even a small drop means a lot of recent
#: bad reviews.
_RATING_DROP = -0.05
_CATALOGUE_MOVE_PCT = 5.0


@dataclass
class CompetitorReading:
    """One competitor's latest state plus how it changed."""

    competitor: TrackedCompetitor
    latest: CompetitorSnapshot | None
    follower_trend_pct: float | None
    product_trend_pct: float | None
    rating_delta: float | None


def _n(value: int | None) -> str:
    return f"{value:,}".replace(",", ".") if value else "—"


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

    # Who's biggest, by the only scale measure available.
    leader = max(usable, key=lambda r: r.latest.follower_count or 0)  # type: ignore[union-attr]
    if leader.latest and leader.latest.follower_count:
        pct = share.get(leader.competitor.id)
        share_txt = f" — {pct}% lượng follower của nhóm" if pct else ""
        findings.append(
            f"{leader.competitor.display_name} lớn nhất nhóm: "
            f"{_n(leader.latest.follower_count)} follower{share_txt}."
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


async def build_insight(
    readings: list[CompetitorReading], share: dict[int, float]
) -> tuple[str, list[str], list[str], bool]:
    """Return (headline, findings, actions, ai_generated)."""
    findings, actions = build_findings(readings, share)

    facts = []
    for r in readings:
        if r.latest is None:
            facts.append(f"{r.competitor.display_name} ({r.competitor.platform}): chưa có dữ liệu")
            continue
        facts.append(
            f"{r.competitor.display_name} ({r.competitor.platform}): "
            f"follower={r.latest.follower_count}, rating={r.latest.rating}, "
            f"số sản phẩm={r.latest.product_count}, "
            f"thay đổi follower={r.follower_trend_pct}%, "
            f"thay đổi số SP={r.product_trend_pct}%, "
            f"thay đổi rating={r.rating_delta}, "
            f"share follower trong nhóm={share.get(r.competitor.id)}%"
        )

    data = await reason_json(_SYSTEM, "\n".join(facts), max_tokens=160, label="competitor")
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
