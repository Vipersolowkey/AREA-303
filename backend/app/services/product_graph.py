"""Đề 1 — Product Knowledge graph service.

Resolves a product's relationships from the commerce store and reuses the
deterministic causal driver attribution (knowledge._drivers) grounded in the
store's data. The relationship/answer narrative runs on the LLM with a fallback.
"""

from __future__ import annotations

from typing import Any, cast

from app.schemas.knowledge import ProductKnowledgeRequest
from app.schemas.product_graph import (
    ProductEntity,
    ProductGraphRequest,
    ProductGraphResponse,
    PromotionInfo,
    RelatedProduct,
    SalesBlock,
)
from app.services import commerce_store as store
from app.services import knowledge as knowledge_svc
from app.services.llm_reasoning import reason_json

# Map the store's trend to a plausible traffic delta so the causal driver
# attribution has a meaningful signal to work with.
_TREND_TRAFFIC = {"rising": 28.0, "cooling": -22.0, "stable": 3.0}


def _relation(product: dict, q: dict) -> str:
    bits = []
    if q["brand"] == product["brand"]:
        bits.append(f"cùng brand {q['brand']}")
    if q["category"] == product["category"]:
        bits.append("cùng danh mục")
    shared = set(product.get("attributes", {}).values()) & set(q.get("attributes", {}).values())
    if shared:
        bits.append("chung thuộc tính: " + ", ".join(sorted(shared)))
    if abs(q["price_vnd"] - product["price_vnd"]) / max(product["price_vnd"], 1) <= 0.2:
        bits.append("giá tương đương")
    return "; ".join(bits) or "liên quan theo hành vi mua"


def _sales_block(p: dict) -> tuple[SalesBlock, dict]:
    change = (p["sales_curr"] - p["sales_prev"]) / p["sales_prev"] * 100.0 if p["sales_prev"] else 0.0
    change = round(change, 1)
    direction = "up" if change > 3 else ("down" if change < -3 else "flat")
    # Reuse the deterministic driver attribution from the knowledge service.
    req = ProductKnowledgeRequest(
        product=p["name"], category=cast(Any, p["category"]),
        sales_prev=p["sales_prev"], sales_curr=p["sales_curr"],
        price_change_pct=0.0,
        promotion_active=p["promotion"] is not None,
        competitor_promo=any(c["discount_pct"] > 0 for c in p["competitors"]),
        stock_status=cast(Any, p["stock_status"]),
        traffic_change_pct=_TREND_TRAFFIC.get(p["trend"], 0.0),
    )
    drivers = knowledge_svc._drivers(req)
    return SalesBlock(
        sales_prev=p["sales_prev"], sales_curr=p["sales_curr"],
        change_pct=change, direction=cast(Any, direction), drivers=drivers,
    ), {"change": change, "direction": direction}


def _promotions(p: dict) -> list[PromotionInfo]:
    promo = p.get("promotion")
    if not promo:
        return []
    lift = promo["lift_pct"]
    eff = ("HIỆU QUẢ CAO" if lift >= 20 else "hiệu quả" if lift >= 10 else "hiệu quả thấp")
    return [PromotionInfo(name=promo["name"], discount_pct=promo["discount_pct"],
                          lift_pct=lift, effectiveness=eff)]


async def explore(req: ProductGraphRequest) -> ProductGraphResponse:
    p = store.find_product(req.query)
    if not p:
        return ProductGraphResponse(
            found=False, product=None, sales=None, similar_products=[],
            brand_siblings=[], category_peers=0, promotions=[],
            summary=f"Không tìm thấy sản phẩm khớp với '{req.query}'.",
        )

    entity = ProductEntity(
        id=p["id"], sku=p["sku"], name=p["name"], brand=p["brand"], category=p["category"],
        price_vnd=p["price_vnd"], cost_vnd=p["cost_vnd"], trend=p["trend"], stock_status=p["stock_status"],
    )
    sales, sales_meta = _sales_block(p)
    similar = [
        RelatedProduct(id=q["id"], sku=q["sku"], name=q["name"], brand=q["brand"],
                       price_vnd=q["price_vnd"], relation=_relation(p, q))
        for q in store.similar_products(p, 5)
    ]
    brand_siblings = [q["name"] for q in store.products_by_brand(p["brand"]) if q["id"] != p["id"]]
    category_peers = len(store.products_by_category(p["category"]))
    promos = _promotions(p)

    summary = await _summarize(p, sales_meta, similar, promos, req.question)
    return ProductGraphResponse(
        found=True, product=entity, sales=sales, similar_products=similar,
        brand_siblings=brand_siblings, category_peers=category_peers,
        promotions=promos, summary=summary,
    )


_SYSTEM = (
    "You are a product-knowledge agent for a Vietnamese e-commerce shop that "
    "understands relationships between products, SKUs, brands, categories, "
    "promotions and sales. Given a product's graph context, answer the seller's "
    "question (or give a relationship overview) in ONE short Vietnamese paragraph "
    "(2-3 sentences), grounded in the data. Reply as JSON: {\"summary\": \"...\"}"
)


def _fallback_summary(p: dict, meta: dict, similar: list[RelatedProduct]) -> str:
    dirtxt = {"up": "tăng", "down": "giảm", "flat": "đi ngang"}[meta["direction"]]
    sim = ", ".join(s.name for s in similar[:3])
    return (f"{p['name']} ({p['sku']}, brand {p['brand']}) đang có doanh số {dirtxt} "
            f"{abs(meta['change']):.0f}%. Sản phẩm tương tự nên tham khảo: {sim}.")


async def _summarize(p: dict, meta: dict, similar: list[RelatedProduct],
                     promos: list[PromotionInfo], question: str | None) -> str:
    ctx = (
        f"Product: {p['name']} (SKU {p['sku']}, brand {p['brand']}, {p['category']}, "
        f"{p['price_vnd']:,}₫, trend {p['trend']}). Sales {p['sales_prev']}→{p['sales_curr']} "
        f"({meta['direction']} {meta['change']}%). Similar: "
        f"{[s.name for s in similar[:4]]}. Promotions: "
        f"{[(pr.name, pr.lift_pct) for pr in promos] or 'none'}."
    )
    user = (f"Question: {question}\n{ctx}" if question else f"Give a relationship overview.\n{ctx}")
    data = await reason_json(_SYSTEM, user, label="product_graph")
    s = (data or {}).get("summary") if data else None
    return (s or "").strip() or _fallback_summary(p, meta, similar)
