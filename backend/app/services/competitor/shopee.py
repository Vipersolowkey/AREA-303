"""Shopee collector.

Endpoints are Shopee's own internal web API (`/api/v4/...`) — undocumented and
unversioned. See :mod:`.base` for why that's expected to break and why we don't
fight the bot protection.

Shape notes (as of writing, Aug 2026):
* ``get_shop_base`` accepts either ``username`` or ``shopid`` and returns
  ``{"data": {"name", "follower_count", "rating_star", "item_count", ...}}``.
* ``search_items`` with ``page_type=shop`` and ``by=sales`` returns the shop's
  best sellers in ``{"items": [{"item_basic": {...}}]}``.
* Prices come back scaled by 100_000 (Shopee stores VND × 100k).
"""

from __future__ import annotations

from app.services.competitor.base import (
    CollectorResult,
    ProductObservation,
    polite_get_json,
)
from app.services.competitor.urls import ParsedCompetitor

_BASE = "https://shopee.vn"
#: How many best sellers to read per capture. Deliberately small — this is a
#: daily trend reading, not a catalogue crawl.
_TOP_N = 20

#: Shopee returns VND multiplied by 100_000.
_PRICE_SCALE = 100_000


def _shop_base_url(target: ParsedCompetitor) -> str:
    if target.shop_id:
        return f"{_BASE}/api/v4/shop/get_shop_base?shopid={target.shop_id}"
    return f"{_BASE}/api/v4/shop/get_shop_base?username={target.shop_slug}"


def _search_url(shop_id: str) -> str:
    return (
        f"{_BASE}/api/v4/search/search_items"
        f"?by=sales&limit={_TOP_N}&match_id={shop_id}"
        "&newest=0&order=desc&page_type=shop&version=2"
    )


def _price(raw: object) -> int | None:
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return None
    return value // _PRICE_SCALE if value else None


class ShopeeCollector:
    async def collect(self, target: ParsedCompetitor) -> CollectorResult:
        base, err = await polite_get_json(
            _shop_base_url(target),
            # Shopee rejects API calls without a plausible referer.
            headers={"Referer": target.url},
        )
        if err:
            return CollectorResult.failed(err)
        assert base is not None

        data = base.get("data")
        if not isinstance(data, dict):
            return CollectorResult.failed(
                "Shopee không trả về thông tin cửa hàng (có thể shop không tồn tại "
                "hoặc endpoint đã đổi)."
            )

        shop_id = str(data.get("shopid") or target.shop_id or "")
        result = CollectorResult(
            ok=True,
            display_name=data.get("name") or target.shop_slug,
            follower_count=_as_int(data.get("follower_count")),
            rating=_as_rating(data),
            product_count=_as_int(data.get("item_count")),
        )

        if not shop_id:
            # Shop identity resolved but no id to query products with — still a
            # usable partial reading.
            return result

        items, items_err = await polite_get_json(
            _search_url(shop_id), headers={"Referer": target.url}
        )
        if items_err or items is None:
            result.error = f"Đã lấy được thông tin shop nhưng không lấy được sản phẩm: {items_err}"
            return result

        observed: list[ProductObservation] = []
        sold_total = 0
        revenue_est = 0
        for entry in items.get("items") or []:
            basic = (entry or {}).get("item_basic") or {}
            price = _price(basic.get("price"))
            sold = _as_int(basic.get("historical_sold")) or 0
            observed.append(
                ProductObservation(
                    name=str(basic.get("name") or "")[:200],
                    price_vnd=price,
                    sold=sold,
                    discount_pct=_as_float(basic.get("raw_discount")),
                )
            )
            sold_total += sold
            if price:
                revenue_est += price * sold

        result.top_products = observed
        result.items_sold_total = sold_total or None
        # Cumulative GMV over the products we sampled — an estimate from
        # `price × historical_sold`, never a figure Shopee reports.
        result.revenue_est_vnd = revenue_est or None
        result.voucher_count = _count_vouchers(data)
        result.promotions = _promotions(observed)
        return result


def _as_int(raw: object) -> int | None:
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return None


def _as_float(raw: object) -> float | None:
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def _as_rating(data: dict) -> float | None:
    # Shopee nests the star rating differently across responses.
    star = data.get("rating_star")
    if star is None:
        star = (data.get("account") or {}).get("rating_star")
    return _as_float(star)


def _count_vouchers(data: dict) -> int | None:
    vouchers = data.get("vouchers") or data.get("shop_vouchers")
    return len(vouchers) if isinstance(vouchers, list) else None


def _promotions(products: list[ProductObservation]) -> list[dict]:
    """Discounted products, as the visible promotion signal for this capture."""
    return [
        {"name": p.name, "discount_pct": p.discount_pct, "price_vnd": p.price_vnd}
        for p in products
        if p.discount_pct
    ]
