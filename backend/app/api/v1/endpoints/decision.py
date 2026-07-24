"""Track 2, Đề 5 — E-commerce Decision Intelligence."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.schemas.decision import DecisionRequest, PlaybookRequest
from app.services import decision as service

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict])
async def recommend(req: DecisionRequest) -> ApiResponse[dict]:
    data = await service.recommend_decision(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


@router.post("/playbook", response_model=ApiResponse[dict])
async def playbook(req: PlaybookRequest) -> ApiResponse[dict]:
    """Store-grounded playbook: normalized best decision + ad-timing seasonality."""
    data = await service.playbook(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)
