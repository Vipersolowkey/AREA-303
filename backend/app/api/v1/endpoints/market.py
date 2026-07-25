"""Track 2, Đề 3 — Market Intelligence (competitor pricing & response)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.schemas.market import MarketRequest, MarketScanRequest
from app.services import market as service

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict])
async def analyze(req: MarketRequest) -> ApiResponse[dict]:
    data = await service.analyze_market(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


@router.post("/scan", response_model=ApiResponse[dict])
async def scan(req: MarketScanRequest) -> ApiResponse[dict]:
    """Multi-competitor market scan for a product from the store."""
    data = await service.scan_market(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)
