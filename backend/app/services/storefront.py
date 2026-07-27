"""Storefront catalog service — buyer-facing view of the commerce store.

Exposes only buyer-safe fields (no cost), with a deterministic rating/reviews
derived from the product id so the catalog looks real and is stable across runs.
"""

from __future__ import annotations

from app.schemas.storefront import StoreDetailResponse, StoreListResponse, StoreProduct
from app.services import commerce_store as store
from app.services.genai.demo_data import get_product_image_url


def _to_product(p: dict) -> StoreProduct:
    h = abs(hash(p["id"]))
    return StoreProduct(
        id=p["id"], sku=p["sku"], name=p["name"], brand=p["brand"], category=p["category"],
        price_vnd=p["price_vnd"], rating=round(4.0 + (h % 10) / 10, 1), reviews=120 + (h % 4200),
        trend=p["trend"], image_url=get_product_image_url(p["name"]), attributes=p.get("attributes", {}),
    )


def list_products(q: str | None = None, category: str | None = None) -> StoreListResponse:
    items = store.all_products()
    if category:
        items = [p for p in items if p["category"] == category]
    if q:
        low = q.lower()
        items = [
            p for p in items
            if low in p["name"].lower() or low in p["brand"].lower()
            or any(low in v.lower() for v in p.get("attributes", {}).values())
        ]
    products = [_to_product(p) for p in items]
    return StoreListResponse(products=products, total=len(products))


def get_product(pid: str) -> StoreDetailResponse:
    p = next((x for x in store.all_products() if x["id"] == pid), None)
    if not p:
        return StoreDetailResponse(product=None, similar=[])
    similar = [_to_product(s) for s in store.similar_products(p, 4)]
    return StoreDetailResponse(product=_to_product(p), similar=similar)
