"""Ideas endpoints — the 17 candidate product ideas from the dataset plan."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.responses import ApiResponse, PageMeta

router = APIRouter()

# Static registry. Replace with DB-backed metadata when the registry is live.
IDEAS: list[dict] = [
    {"id": 1,  "slug": "review-sentiment",      "category": "NLP"},
    {"id": 2,  "slug": "dynamic-pricing",       "category": "Time Series"},
    {"id": 3,  "slug": "personal-shopper",      "category": "Generative AI"},
    {"id": 4,  "slug": "customer-churn",        "category": "Behavioral AI"},
    {"id": 5,  "slug": "fake-review",           "category": "NLP"},
    {"id": 6,  "slug": "demand-forecasting",    "category": "Time Series"},
    {"id": 7,  "slug": "visual-search",         "category": "Computer Vision"},
    {"id": 8,  "slug": "social-trend",          "category": "NLP"},
    {"id": 9,  "slug": "content-generator",     "category": "NLP"},
    {"id": 10, "slug": "return-prediction",     "category": "Behavioral AI"},
    {"id": 11, "slug": "recsys",                "category": "Generative AI"},
    {"id": 12, "slug": "virtual-tryon",         "category": "Computer Vision"},
    {"id": 13, "slug": "segmentation",          "category": "Behavioral AI"},
    {"id": 15, "slug": "price-sensitivity",     "category": "Time Series"},
    {"id": 16, "slug": "supply-chain",          "category": "Time Series"},
    {"id": 17, "slug": "seller-intelligence",   "category": "Generative AI"},
]


@router.get("/", response_model=ApiResponse[list[dict]])
async def list_ideas(
    category: str | None = Query(default=None, description="Filter by category"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[list[dict]]:
    items = IDEAS
    if category:
        items = [i for i in items if i["category"].lower() == category.lower()]
    total = len(items)
    start, end = (page - 1) * page_size, page * page_size
    return ApiResponse[list[dict]](
        success=True,
        data=items[start:end],
        meta=PageMeta(page=page, page_size=page_size, total=total),
        error=None,
    )


@router.get("/{idea_id}", response_model=ApiResponse[dict])
async def get_idea(idea_id: int) -> ApiResponse[dict]:
    match = next((i for i in IDEAS if i["id"] == idea_id), None)
    if match is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Idea {idea_id} not found.")
    return ApiResponse[dict](
        success=True, data=match, meta=PageMeta(), error=None
    )
