"""Buyer storefront catalog — list + detail from the commerce store."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import ApiResponse, PageMeta
from app.services import storefront as service

router = APIRouter()


@router.get("/products", response_model=ApiResponse[dict])
async def products(q: str | None = None, category: str | None = None) -> ApiResponse[dict]:
    data = service.list_products(q=q, category=category)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)


@router.get("/products/{pid}", response_model=ApiResponse[dict])
async def product_detail(pid: str) -> ApiResponse[dict]:
    data = service.get_product(pid)
    return ApiResponse[dict](success=True, data=data.model_dump(), meta=PageMeta(), error=None)
