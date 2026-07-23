"""Customer Journey Intelligence service — Track 1, Đề 2.

Key-free heuristic: turns a session's event sequence into a purchase-intent
score, the shopper's dominant category interest, and top-3 product picks —
answering the brief's three example questions directly.
"""

from __future__ import annotations

import math
from collections import Counter

from app.schemas.journey import JourneyRequest, JourneyResponse
from app.services.genai.demo_data import DEMO_CATALOG
from app.services.personal_shopper import _card


def analyze_journey(req: JourneyRequest) -> JourneyResponse:
    n_view = sum(1 for e in req.events if e.type == "view")
    n_cart = sum(1 for e in req.events if e.type == "cart")
    n_purchase = sum(1 for e in req.events if e.type == "purchase")
    n_livestream = sum(1 for e in req.events if e.type == "livestream")

    cat_counts = Counter(e.category for e in req.events if e.category)
    top_category = cat_counts.most_common(1)[0][0] if cat_counts else None

    # Funnel-weighted purchase-intent score: cart adds and past purchases in
    # this session are strong signals; views/livestream contribute less and
    # views are capped so idle browsing alone doesn't dominate the score.
    z = 0.7 * n_cart + 1.5 * n_purchase + 0.15 * min(n_view, 10) + 0.4 * n_livestream - 1.0
    prob = 1 / (1 + math.exp(-z))
    will_purchase = prob >= 0.5

    pool = [it for it in DEMO_CATALOG if it["metadata"].get("category") == top_category] if top_category else list(DEMO_CATALOG)
    picks = (pool + [it for it in DEMO_CATALOG if it not in pool])[:3]
    products = [_card(it, round(0.9 - i * 0.08, 2)) for i, it in enumerate(picks)]

    parts = []
    if n_cart:
        parts.append(f"đã thêm {n_cart} sản phẩm vào giỏ")
    if n_purchase:
        parts.append(f"đã mua {n_purchase} lần trong phiên này")
    if n_livestream:
        parts.append(f"tương tác {n_livestream} lần với livestream")
    if n_view:
        parts.append(f"xem {n_view} sản phẩm")
    if top_category:
        parts.append(f"quan tâm nhiều nhất tới {top_category}")
    reasoning = ("Dựa trên " + ", ".join(parts) + ".") if parts else "Chưa có hành vi rõ ràng trong phiên."

    return JourneyResponse(
        will_purchase=will_purchase,
        purchase_probability=round(prob, 2),
        top_category=top_category,
        category_breakdown={str(k): v for k, v in cat_counts.items()},
        recommended_products=products,
        reasoning=reasoning,
    )
