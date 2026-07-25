"""#04 Churn Prediction — score a customer's churn risk (seller insight)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.schemas.insights import ChurnRequest
from app.services import insights, portfolio

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict])
async def score(req: ChurnRequest) -> ApiResponse[dict]:
    data = insights.score_churn(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


@router.get("/portfolio", response_model=ApiResponse[dict])
async def portfolio_report() -> ApiResponse[dict]:
    """Auto-analyse the whole customer base — no manual input."""
    return ApiResponse[dict](success=True, data=portfolio.churn_portfolio(), meta=PageMeta(), error=None)
