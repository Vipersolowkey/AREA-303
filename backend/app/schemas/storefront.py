"""Buyer-facing storefront catalog (reads the commerce store)."""

from __future__ import annotations

from pydantic import BaseModel


class StoreProduct(BaseModel):
    id: str
    sku: str
    name: str
    brand: str
    category: str
    price_vnd: int
    rating: float
    reviews: int
    trend: str
    image_url: str
    attributes: dict[str, str]


class StoreListResponse(BaseModel):
    products: list[StoreProduct]
    total: int


class StoreDetailResponse(BaseModel):
    product: StoreProduct | None
    similar: list[StoreProduct]
