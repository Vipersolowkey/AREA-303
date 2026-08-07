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
    image_urls: list[str]
    attributes: dict[str, str]
    # Live stock. `None` means "unknown" (the stock table wasn't reachable), which
    # the UI must treat as buyable rather than out of stock — a DB blip should not
    # make the whole catalogue look sold out.
    stock: int | None = None


class ReviewItem(BaseModel):
    author: str
    rating: int
    text: str
    days_ago: int

class StoreListResponse(BaseModel):
    products: list[StoreProduct]
    total: int


class StoreDetailResponse(BaseModel):
    product: StoreProduct | None
    similar: list[StoreProduct]
    review_items: list[ReviewItem] = []
