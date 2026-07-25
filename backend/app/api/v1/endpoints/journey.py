"""Customer Journey Intelligence — Track 1, Đề 2 (not one of the original 17 ideas)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.schemas.journey import JourneyRequest
from app.services import journey as service
from app.services import portfolio

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict])
async def analyze(req: JourneyRequest) -> ApiResponse[dict]:
    data = await service.analyze_journey(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


@router.get("/sessions", response_model=ApiResponse[dict])
async def sessions() -> ApiResponse[dict]:
    """Pre-built real shopping sessions, each analysed — ready to test."""
    data = await portfolio.journey_sessions()
    return ApiResponse[dict](success=True, data=data, meta=PageMeta(), error=None)
