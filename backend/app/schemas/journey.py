"""Customer Journey Intelligence — Track 1, Đề 2.

Analyses the full behavioural sequence of a shopping session — search, click,
view, add-to-cart, purchase, livestream interaction — and predicts the
shopper's NEXT ACTION (per the brief's goal), plus purchase intent, the
category they care about, and the top-3 products to recommend.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.genai import ProductCard

# Full journey event vocabulary from the Đề 2 brief (search + click added).
EventType = Literal["search", "click", "view", "cart", "purchase", "livestream"]
Category = Literal["Thời trang", "Mỹ phẩm", "Phụ kiện"]
NextAction = Literal["checkout", "add_to_cart", "compare", "keep_browsing", "leave"]
FunnelStage = Literal["awareness", "consideration", "intent", "purchase"]


class JourneyEvent(BaseModel):
    type: EventType
    category: Category | None = None
    query: str | None = Field(default=None, max_length=120)  # for search events


class JourneyRequest(BaseModel):
    events: list[JourneyEvent] = Field(min_length=1, max_length=100)


class JourneyResponse(BaseModel):
    # Q1 — buy or leave?
    will_purchase: bool
    purchase_probability: float = Field(ge=0.0, le=1.0)
    # Goal — predict the next action
    predicted_next_action: NextAction
    next_action_label: str
    funnel_stage: FunnelStage
    engagement_score: float = Field(ge=0.0, le=1.0)
    nudge: str
    # Q3 — which category?
    top_category: Category | None
    category_breakdown: dict[str, int]
    # Q2 — top 3 products
    recommended_products: list[ProductCard]
    reasoning: str
