"""Seller Copilot — conversational AI agent + daily action briefing."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.schemas.copilot import CopilotRequest
from app.services import copilot as service

router = APIRouter()


@router.post("/ask", response_model=ApiResponse[dict])
async def ask(req: CopilotRequest) -> ApiResponse[dict]:
    data = await service.ask(req.question)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


@router.get("/briefing", response_model=ApiResponse[dict])
async def briefing() -> ApiResponse[dict]:
    data = await service.briefing()
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)
