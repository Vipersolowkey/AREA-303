"""Đề 1 — Product Knowledge as an entity graph.

Given a product (by name or SKU), resolves its relationships across the commerce
graph — similar SKUs, same-brand siblings, category peers, promotions — and a
grounded causal explanation of its sales movement. Answers the brief's example
questions ("sản phẩm nào tương tự SKU này?", "vì sao doanh số đổi?", "promotion
nào hiệu quả?") from the shop's own data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.knowledge import Driver


class ProductGraphRequest(BaseModel):
    query: str  # product name or SKU
    question: str | None = None  # optional natural-language relationship question


class ProductEntity(BaseModel):
    id: str
    sku: str
    name: str
    brand: str
    category: str
    price_vnd: int
    cost_vnd: int
    trend: str
    stock_status: str


class RelatedProduct(BaseModel):
    id: str
    sku: str
    name: str
    brand: str
    price_vnd: int
    relation: str  # why it's related


class SalesBlock(BaseModel):
    sales_prev: int
    sales_curr: int
    change_pct: float
    direction: Literal["up", "down", "flat"]
    drivers: list[Driver]


class PromotionInfo(BaseModel):
    name: str
    discount_pct: int
    lift_pct: int
    effectiveness: str


class ProductGraphResponse(BaseModel):
    found: bool
    product: ProductEntity | None
    sales: SalesBlock | None
    similar_products: list[RelatedProduct]
    brand_siblings: list[str]
    category_peers: int
    promotions: list[PromotionInfo]
    summary: str
