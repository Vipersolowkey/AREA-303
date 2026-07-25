"""#16 Supply Chain Disruption Early Warning."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.schemas.supply_chain import SupplyChainRequest
from app.services import supply_chain as service

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict])
async def check(req: SupplyChainRequest) -> ApiResponse[dict]:
    data = await service.check_supply_chain(req)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)
