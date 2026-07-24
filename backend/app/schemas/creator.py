"""Track 2, Đề 4 — Content & Creator Performance.

Link content performance (video / livestream / post) to real sales, rank
creators by sales efficiency, and recommend a KOL/KOC for a campaign. Rankings
are deterministic; the KOL/KOC recommendation narrative is LLM.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["Thời trang", "Mỹ phẩm", "Phụ kiện"]
ContentType = Literal["video", "livestream", "post"]


class ContentItem(BaseModel):
    creator: str = Field(min_length=1, max_length=120)
    content_type: ContentType
    views: int = Field(ge=0, le=1_000_000_000)
    engagements: int = Field(ge=0, le=1_000_000_000)
    attributed_sales_vnd: int = Field(ge=0, le=100_000_000_000)


class CreatorRequest(BaseModel):
    campaign_category: Category
    items: list[ContentItem] = Field(min_length=1, max_length=200)


class CreatorScore(BaseModel):
    creator: str
    content_type: ContentType
    total_sales_vnd: int
    sales_per_1k_views: int
    engagement_rate_pct: float


class CreatorResponse(BaseModel):
    best_content_type: ContentType
    recommended_creator: str
    top_creators: list[CreatorScore]
    insight: str


# --- Creator correlation (store-grounded, multi-campaign) ------------------ #
class CorrelationRequest(BaseModel):
    category: Category


class CreatorCorrelation(BaseModel):
    creator: str
    content_type: str
    campaigns: int
    correlation: float  # views ↔ attributed_sales, -1..1
    avg_sales_per_1k_views: int
    total_sales_vnd: int


class CorrelationResponse(BaseModel):
    category: Category
    ranked: list[CreatorCorrelation]
    best_creator: str
    insight: str
