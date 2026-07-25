"""Track 2, Đề 4 — Content & Creator Performance."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.schemas.creator import CorrelationRequest, CreatorRequest
from app.services import creator as service

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict])
async def analyze(req: CreatorRequest) -> ApiResponse[dict]:
    data = await service.analyze_creators(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


@router.post("/correlation", response_model=ApiResponse[dict])
async def corr(req: CorrelationRequest) -> ApiResponse[dict]:
    """Rank a category's creators by content↔sales correlation (store history)."""
    data = await service.analyze_correlation(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)
