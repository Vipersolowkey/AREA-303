"""Dashboard KPIs derived from the coherent demo-shop fact tables."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.services import shop_analytics

router = APIRouter()


@router.get("/summary", response_model=ApiResponse[dict])
async def summary() -> ApiResponse[dict]:
    """Return the internally consistent bundled-shop snapshot."""
    data = shop_analytics.summary()
    return ApiResponse[dict](success=True, data=data, meta=PageMeta(), error=None)
