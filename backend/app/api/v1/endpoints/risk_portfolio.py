"""Customer Risk Intelligence — combined churn/return/regret portfolio.

Gộp #04 Churn + #10 Return Predict + #15 Regret Predict thành 1 view:
mỗi khách 1 dòng, kèm cả 3 điểm rủi ro, để phát hiện khách "rủi ro chồng"
mà 3 trang riêng không cho thấy được.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.services import portfolio

router = APIRouter()


@router.get("/", response_model=ApiResponse[dict])
async def combined_portfolio() -> ApiResponse[dict]:
    return ApiResponse[dict](
        success=True, data=portfolio.risk_portfolio(), meta=PageMeta(), error=None
    )
