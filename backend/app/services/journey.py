"""Customer Journey Intelligence service — Track 1, Đề 2.

Turns a session's full event sequence (search / click / view / cart / purchase /
livestream) into: a funnel-weighted purchase-intent score, the current funnel
stage, an engagement score, the dominant category, the top-3 product picks, and
— per the brief's goal — the predicted NEXT ACTION plus a concrete seller nudge
to move the shopper forward. The numeric scoring is deterministic; the narrative
reasoning runs on the LLM with a templated fallback.
"""

from __future__ import annotations

import math
from collections import Counter

from app.schemas.journey import (
    FunnelStage,
    JourneyRequest,
    JourneyResponse,
    NextAction,
)
from app.services.genai.demo_data import DEMO_CATALOG
from app.services.llm_reasoning import reason_json
from app.services.personal_shopper import _card


def _funnel_stage(counts: dict[str, int]) -> FunnelStage:
    if counts["purchase"]:
        return "purchase"
    if counts["cart"]:
        return "intent"
    if counts["view"] or counts["click"] or counts["livestream"]:
        return "consideration"
    return "awareness"


def _next_action(stage: FunnelStage, prob: float, engagement: float,
                 has_search: bool) -> tuple[NextAction, str, str]:
    """Return (action_key, vietnamese_label, seller_nudge)."""
    if stage == "purchase":
        return ("checkout", "Đã mua trong phiên — có thể mua thêm",
                "Cross-sell sản phẩm bổ sung + mời tích điểm/thành viên để tăng giá trị đơn.")
    if stage == "intent":
        if prob >= 0.6:
            return ("checkout", "Sắp thanh toán",
                    "Làm nổi bật nút thanh toán + freeship/quà nhỏ để chốt đơn ngay.")
        return ("compare", "Đang phân vân (đã thêm giỏ nhưng chưa mua)",
                "Gửi mã giảm giá giới hạn thời gian + đánh giá tốt để thúc đẩy chốt đơn.")
    # Leave risk = a low-engagement bounce with no active search intent. An
    # explicit search means the shopper is hunting for something, so treat that
    # as early-funnel browsing to nurture, not a bounce.
    if engagement < 0.2 and prob < 0.35 and not has_search:
        return ("leave", "Nguy cơ rời đi",
                "Bật popup ưu đãi/mã giảm ngay để giữ chân trước khi thoát.")
    if stage == "consideration":
        if prob >= 0.5:
            return ("add_to_cart", "Có khả năng thêm vào giỏ",
                    "Nhắc 'chỉ còn ít hàng' + hiển thị review nổi bật để tạo động lực thêm giỏ.")
        return ("keep_browsing", "Còn xem tiếp, chưa quyết",
                "Đề xuất sản phẩm liên quan cùng danh mục để giữ chân và dẫn dắt.")
    # awareness (mostly searching)
    return ("keep_browsing", "Mới bắt đầu tìm hiểu",
            "Hiển thị sản phẩm bán chạy khớp từ khoá tìm kiếm để dẫn vào phễu.")


async def analyze_journey(req: JourneyRequest) -> JourneyResponse:
    counts = {t: 0 for t in ("search", "click", "view", "cart", "purchase", "livestream")}
    for e in req.events:
        counts[e.type] += 1

    cat_counts = Counter(e.category for e in req.events if e.category)
    top_category = cat_counts.most_common(1)[0][0] if cat_counts else None

    # Funnel-weighted intent: later-funnel actions weigh far more; early actions
    # (search/click/view) are capped so idle browsing alone can't dominate.
    z = (0.10 * min(counts["search"], 10)
         + 0.15 * min(counts["click"], 15)
         + 0.15 * min(counts["view"], 10)
         + 0.40 * counts["livestream"]
         + 0.70 * counts["cart"]
         + 1.50 * counts["purchase"]
         - 1.0)
    prob = 1 / (1 + math.exp(-z))
    will_purchase = prob >= 0.5

    eng_raw = (0.5 * counts["search"] + 0.7 * counts["click"] + 0.7 * counts["view"]
               + 1.5 * counts["livestream"] + 2.0 * counts["cart"] + 2.5 * counts["purchase"])
    engagement = round(min(1.0, eng_raw / 12.0), 2)

    stage = _funnel_stage(counts)
    action, label, nudge = _next_action(stage, prob, engagement, has_search=counts["search"] > 0)

    pool = ([it for it in DEMO_CATALOG if it["metadata"].get("category") == top_category]
            if top_category else list(DEMO_CATALOG))
    picks = (pool + [it for it in DEMO_CATALOG if it not in pool])[:3]
    products = [_card(it, round(0.9 - i * 0.08, 2)) for i, it in enumerate(picks)]

    reasoning = await _reason(counts, top_category, prob, stage, label)

    return JourneyResponse(
        will_purchase=will_purchase,
        purchase_probability=round(prob, 2),
        predicted_next_action=action,
        next_action_label=label,
        funnel_stage=stage,
        engagement_score=engagement,
        nudge=nudge,
        top_category=top_category,
        category_breakdown={str(k): v for k, v in cat_counts.items()},
        recommended_products=products,
        reasoning=reasoning,
    )


_SYSTEM = (
    "You are a customer-journey analyst for a Vietnamese e-commerce shop. Given a "
    "session's event counts, funnel stage, purchase probability and the predicted "
    "next action, explain in ONE short Vietnamese paragraph (2-3 sentences) what the "
    "shopper is doing and why the next action is likely. Do not invent data. "
    'Reply as JSON: {"reasoning": "..."}'
)


def _fallback_reasoning(counts: dict[str, int], top_category: str | None, label: str) -> str:
    parts = []
    order = [("search", "tìm kiếm {n} lần"), ("click", "click {n} lần"),
             ("view", "xem {n} sản phẩm"), ("livestream", "tương tác livestream {n} lần"),
             ("cart", "thêm {n} sản phẩm vào giỏ"), ("purchase", "mua {n} lần")]
    for key, tmpl in order:
        if counts[key]:
            parts.append(tmpl.format(n=counts[key]))
    if top_category:
        parts.append(f"quan tâm nhiều nhất tới {top_category}")
    base = ("Trong phiên, khách " + ", ".join(parts) + ".") if parts else "Chưa có hành vi rõ ràng."
    return f"{base} Dự đoán bước tiếp theo: {label.lower()}."


async def _reason(counts: dict[str, int], top_category: str | None,
                  prob: float, stage: FunnelStage, label: str) -> str:
    data = await reason_json(
        _SYSTEM,
        f"Event counts: {counts}. Top category: {top_category}. Funnel stage: {stage}. "
        f"Purchase probability: {prob:.2f}. Predicted next action: {label}.",
        label="journey",
    )
    r = (data or {}).get("reasoning") if data else None
    return (r or "").strip() or _fallback_reasoning(counts, top_category, label)
