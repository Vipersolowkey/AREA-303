"""Turn collected competitor snapshots into findings and suggested actions.

Same split as the rest of the project: the findings are computed
deterministically from the data, and only the narrative headline runs on the
LLM — with a templated fallback. `ai_generated` is reported honestly so the UI
never claims AI wrote a line it didn't.
"""

from __future__ import annotations

from app.models.competitor import CompetitorSnapshot, TrackedCompetitor
from app.services.llm_reasoning import reason_json

_SYSTEM = (
    "You analyse Vietnamese e-commerce competitor tracking data for a seller "
    "dashboard. Given per-shop readings (estimated cumulative GMV, units sold, "
    "follower count, rating, number of discounted items) and their percent "
    "change over the tracked period, write ONE short headline (max 25 words) "
    "naming the single most decision-relevant thing the seller should notice. "
    "Cite an actual number. Do not invent data you were not given. The "
    "dashboard is Vietnamese-only — write IN VIETNAMESE. "
    'Reply as JSON: {"headline": "..."}'
)


def _fmt_vnd(value: int | None) -> str:
    if not value:
        return "—"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f} tỷ₫"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.0f} triệu₫"
    return f"{value:,}₫".replace(",", ".")


def build_findings(
    rows: list[tuple[TrackedCompetitor, CompetitorSnapshot | None, float | None, float | None]],
    share: dict[int, float],
) -> tuple[list[str], list[str]]:
    """Deterministic findings + actions from the tracked set.

    `rows` is (competitor, latest_ok_snapshot, revenue_trend_pct, sold_trend_pct).
    """
    findings: list[str] = []
    actions: list[str] = []

    usable = [(c, s, rt, st) for c, s, rt, st in rows if s is not None]
    if not usable:
        return (
            ["Chưa thu được dữ liệu nào từ các cửa hàng đang theo dõi."],
            [
                "Kiểm tra lại link cửa hàng, hoặc chạy lại thu thập — "
                "sàn có thể đang chặn truy cập tự động."
            ],
        )

    # Biggest shop by estimated GMV.
    leader = max(usable, key=lambda r: r[1].revenue_est_vnd or 0)
    lc, ls = leader[0], leader[1]
    if ls.revenue_est_vnd:
        pct = share.get(lc.id)
        share_txt = f", chiếm {pct}% trong nhóm đang theo dõi" if pct else ""
        findings.append(
            f"{lc.display_name} dẫn đầu với GMV ước tính {_fmt_vnd(ls.revenue_est_vnd)}{share_txt}."
        )

    # Fastest riser / faller by revenue trend.
    trended = [(c, s, rt) for c, s, rt, _ in usable if rt is not None]
    if trended:
        riser = max(trended, key=lambda r: r[2])
        faller = min(trended, key=lambda r: r[2])
        if riser[2] > 5:
            findings.append(
                f"{riser[0].display_name} tăng {riser[2]}% GMV ước tính trong kỳ theo dõi."
            )
            actions.append(
                f"Xem {riser[0].display_name} đang đẩy sản phẩm nào — họ đang thắng ở đâu đó."
            )
        if faller[2] < -5:
            findings.append(
                f"{faller[0].display_name} giảm {abs(faller[2])}% GMV ước tính."
            )
            actions.append(
                f"{faller[0].display_name} đang chậm lại — cơ hội giành thị phần ở nhóm sản phẩm của họ."
            )

    # Discounting pressure.
    discounters = [
        (c, len(s.promotions or []))
        for c, s, _, _ in usable
        if s.promotions
    ]
    if discounters:
        top = max(discounters, key=lambda d: d[1])
        if top[1] >= 3:
            findings.append(
                f"{top[0].display_name} đang giảm giá {top[1]} sản phẩm cùng lúc."
            )
            actions.append(
                "Đối thủ đang chạy khuyến mãi diện rộng — cân nhắc phản ứng bằng "
                "giá trị (freeship, combo) thay vì hạ giá theo."
            )

    # Best seller worth studying.
    with_products = [(c, s) for c, s, _, _ in usable if s.top_products]
    if with_products:
        c, s = with_products[0]
        best = max(
            (p for p in (s.top_products or []) if isinstance(p, dict)),
            key=lambda p: p.get("sold") or 0,
            default=None,
        )
        if best and best.get("sold"):
            findings.append(
                f"Sản phẩm bán chạy nhất của {c.display_name}: "
                f"{best.get('name')} — {best['sold']:,} đã bán.".replace(",", ".")
            )

    # Surface collector breakage as a finding, not a silent gap.
    broken = [c.display_name for c, s, _, _ in rows if s is None]
    if broken:
        findings.append(
            f"Chưa có dữ liệu hợp lệ cho: {', '.join(str(b) for b in broken)}."
        )

    if not actions:
        actions.append("Tiếp tục theo dõi — cần thêm vài kỳ dữ liệu để thấy xu hướng rõ.")
    return findings, actions


async def build_insight(
    rows: list[tuple[TrackedCompetitor, CompetitorSnapshot | None, float | None, float | None]],
    share: dict[int, float],
) -> tuple[str, list[str], list[str], bool]:
    """Return (headline, findings, actions, ai_generated)."""
    findings, actions = build_findings(rows, share)

    facts = []
    for c, s, rt, st in rows:
        if s is None:
            facts.append(f"{c.display_name} ({c.platform}): chưa có dữ liệu")
            continue
        facts.append(
            f"{c.display_name} ({c.platform}): GMV ước tính={s.revenue_est_vnd}, "
            f"đã bán={s.items_sold_total}, follower={s.follower_count}, "
            f"rating={s.rating}, SP giảm giá={len(s.promotions or [])}, "
            f"thay đổi GMV={rt}%, thay đổi đã bán={st}%, "
            f"share trong nhóm={share.get(c.id)}%"
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
