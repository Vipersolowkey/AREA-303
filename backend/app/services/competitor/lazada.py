"""Lazada collector.

Lazada's shop pages render server-side but also answer with JSON when asked
with ``?ajax=true``, which is what its own pagination uses. Same caveats as
Shopee: undocumented, unversioned, bot-protected. See :mod:`.base`.

Shape notes (as of writing, Aug 2026):
* ``/shop/<slug>?ajax=true`` → ``{"mods": {"listItems": [...], "filterItems": ...}}``
* Each list item carries ``name``, ``price`` (string VND), ``originalPrice``,
  ``discount`` ("-20%"), ``itemSoldCntShow`` ("1.2k đã bán"), ``ratingScore``.
* Lazada does not expose a follower count on this payload, so that stays None.
"""

from __future__ import annotations

import re

from app.services.competitor.base import (
    CollectorResult,
    ProductObservation,
    polite_get_json,
)
from app.services.competitor.urls import ParsedCompetitor

_BASE = "https://www.lazada.vn"

#: "1.2k đã bán" / "350 sold" → 1200 / 350
_SOLD_RE = re.compile(r"([\d.,]+)\s*([km])?", re.I)
_DISCOUNT_RE = re.compile(r"(\d+)\s*%")


def _shop_url(target: ParsedCompetitor) -> str:
    slug = target.shop_slug or target.shop_id or ""
    return f"{_BASE}/shop/{slug}/?ajax=true&isFirst=yes"


class LazadaCollector:
    async def collect(self, target: ParsedCompetitor) -> CollectorResult:
        if not target.shop_slug:
            # A product-only Lazada link doesn't tell us the shop, and resolving
            # it means scraping the product page's HTML for the seller — more
            # fragile than it's worth. Ask for the shop URL instead.
            return CollectorResult.failed(
                "Link Lazada này là link sản phẩm, chưa xác định được cửa hàng. "
                "Hãy dán link trang cửa hàng (lazada.vn/shop/tên-shop)."
            )

        payload, err = await polite_get_json(
            _shop_url(target), headers={"Referer": target.url}
        )
        if err:
            return CollectorResult.failed(err)
        assert payload is not None

        mods = payload.get("mods")
        if not isinstance(mods, dict):
            return CollectorResult.failed(
                "Lazada không trả về danh sách sản phẩm (endpoint có thể đã đổi)."
            )

        raw_items = mods.get("listItems")
        if not isinstance(raw_items, list) or not raw_items:
            return CollectorResult.failed(
                "Không thấy sản phẩm nào trong trang cửa hàng Lazada này."
            )

        observed: list[ProductObservation] = []
        sold_total = 0
        revenue_est = 0
        ratings: list[float] = []

        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            price = _as_price(entry.get("price"))
            sold = _as_sold(entry.get("itemSoldCntShow")) or 0
            rating = _as_float(entry.get("ratingScore"))
            if rating:
                ratings.append(rating)
            observed.append(
                ProductObservation(
                    name=str(entry.get("name") or "")[:200],
                    price_vnd=price,
                    sold=sold,
                    discount_pct=_as_discount(entry.get("discount")),
                )
            )
            sold_total += sold
            if price:
                revenue_est += price * sold

        return CollectorResult(
            ok=True,
            display_name=_shop_name(mods) or target.shop_slug,
            # Lazada's shop payload has no follower count.
            follower_count=None,
            rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
            product_count=len(observed) or None,
            items_sold_total=sold_total or None,
            revenue_est_vnd=revenue_est or None,
            voucher_count=None,
            top_products=observed,
            promotions=[
                {"name": p.name, "discount_pct": p.discount_pct, "price_vnd": p.price_vnd}
                for p in observed
                if p.discount_pct
            ],
        )


def _shop_name(mods: dict) -> str | None:
    for key in ("shopInfo", "seller", "storeInfo"):
        block = mods.get(key)
        if isinstance(block, dict):
            name = block.get("name") or block.get("shopName")
            if name:
                return str(name)[:200]
    return None


def _as_float(raw: object) -> float | None:
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def _as_price(raw: object) -> int | None:
    """Lazada sends price as a string like "199000" or "199,000"."""
    if raw is None:
        return None
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


def _as_sold(raw: object) -> int | None:
    """Parse the human-formatted sold count ("1.2k đã bán")."""
    if raw is None:
        return None
    m = _SOLD_RE.search(str(raw))
    if not m:
        return None
    number, suffix = m.group(1), (m.group(2) or "").lower()
    # "1.2" is one-point-two here, but "1,200" is twelve hundred — treat a comma
    # as a thousands separator and a dot as a decimal point.
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return int(value)


def _as_discount(raw: object) -> float | None:
    if raw is None:
        return None
    m = _DISCOUNT_RE.search(str(raw))
    return float(m.group(1)) if m else None
