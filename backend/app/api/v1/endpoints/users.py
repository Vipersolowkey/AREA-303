"""User listing — admin-only (gated at the router level in app.api.v1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_dep
from app.core.responses import ApiResponse, PageMeta
from app.schemas.auth import UserOut
from app.services import user_service

router = APIRouter()


@router.get("/", response_model=ApiResponse[list[dict]])
async def list_users(db: AsyncSession = Depends(get_db_dep)) -> ApiResponse[list[dict]]:
    rows = await user_service.list_users(db)
    items = [UserOut.model_validate(r, from_attributes=True).model_dump() for r in rows]
    return ApiResponse[list[dict]](
        success=True,
        data=items,
        meta=PageMeta(page=1, page_size=len(items), total=len(items)),
        error=None,
    )
