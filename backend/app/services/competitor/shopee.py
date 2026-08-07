"""Shopee collector.

Two tiers, because Shopee treats them completely differently:

**Shop-level** — `get_shop_base` answers an anonymous request with the shop's
name, follower count, rating and product count. Free, reliable, no session.

**Sales-level** — items sold, prices, best sellers, vouchers. Every endpoint
carrying these returns `error 90309999` to an anonymous caller, including from
inside a real headless browser, and the shop page renders a login wall. So they
come from whichever privileged source the operator configured:

1. :mod:`.vendor` — a licensed market-data feed. No account risk, tried first.
2. :mod:`.session` — a logged-in Shopee session in a real browser. Works, but
   risks the account; opt-in.

With neither configured the reading is shop-level only and `sales_source` stays
None. That's a complete, honest snapshot — not a failure — so `ok` is True.

Shape notes (verified Aug 2026):
* ``get_shop_base`` accepts either ``username`` or ``shopid`` and returns
  ``{"data": {"name", "follower_count", "rating_star", "item_count", ...}}``.
* ``search_items`` with ``page_type=shop`` and ``by=sales`` returns the shop's
  best sellers in ``{"items": [{"item_basic": {...}}]}``.
* Prices come back scaled by 100_000 (Shopee stores VND × 100k).
"""

from __future__ import annotations

from app.services.competitor import session as session_mod
from app.services.competitor import vendor as vendor_mod
from app.services.competitor.base import CollectorResult, polite_get_json
from app.services.competitor.urls import ParsedCompetitor

_BASE = "https://shopee.vn"

#: Shopee returns VND multiplied by 100_000.
_PRICE_SCALE = 100_000


def _shop_base_url(target: ParsedCompetitor) -> str:
    if target.shop_id:
        return f"{_BASE}/api/v4/shop/get_shop_base?shopid={target.shop_id}"
    return f"{_BASE}/api/v4/shop/get_shop_base?username={target.shop_slug}"


def _price(raw: object) -> int | None:
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return None
    return value // _PRICE_SCALE if value else None


class ShopeeCollector:
    """Collect one Shopee shop.

    `sales_reader` is an optional :class:`~.session.ShopeeSessionReader` owned by
    the caller, so one browser is shared across a whole collection run instead of
    launched per shop. None means "no session available", which is the default.
    """

    def __init__(self, sales_reader: session_mod.ShopeeSessionReader | None = None) -> None:
        self._sales_reader = sales_reader

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
            voucher_count=_count_vouchers(data),
        )

        if not shop_id:
            # Shop identity resolved but no id to query sales with — still a
            # usable partial reading.
            return result

        await self._add_sales(result, target, shop_id)
        return result

    async def _add_sales(
        self, result: CollectorResult, target: ParsedCompetitor, shop_id: str
    ) -> None:
        """Try each configured sales source in order of increasing risk."""
        reasons: list[str] = []

        reading, err = await vendor_mod.fetch_sales("shopee", shop_id)
        if reading is not None:
            result.apply(reading)
            return
        if err:
            reasons.append(err)

        if self._sales_reader is not None:
            reading, err = await self._sales_reader.fetch_sales(shop_id, target.url)
            if reading is not None:
                result.apply(reading)
                return
            if err:
                reasons.append(err)

        # Nothing configured is not an error — say so plainly, once, rather than
        # leaving the operator to guess why the sales cards are empty.
        if not reasons:
            reasons.append(
                "Chưa cấu hình nguồn số liệu bán hàng: Shopee chỉ trả số đã bán / "
                "giá / voucher cho phiên đã đăng nhập. Cấu hình "
                "COMPETITOR_VENDOR_* hoặc chạy scripts/shopee_login.py."
            )
        result.error = " | ".join(reasons)


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
