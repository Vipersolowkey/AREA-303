"""Sales figures from a licensed market-data vendor.

Vendors like Metric.vn and BeeCost already crawl Shopee/Lazada at scale and sell
the result. Buying the data is the only route to sales figures that carries no
account risk and no terms violation, so this source is tried before the browser
session.

## Why the response mapping is alias-based

Every vendor names these fields differently (`gmv` vs `revenue` vs `estimated_revenue`,
`sold` vs `units_sold` vs `order_count`), and the concrete contract can't be
verified without a paid key. Rather than hard-code one vendor's field names and
have the adapter silently return None against another's, each field is read
through a list of accepted aliases. Adding a vendor is usually a matter of
appending an alias, not writing a new adapter.

The request shape assumed is the common one::

    GET {COMPETITOR_VENDOR_BASE_URL}/shops/{platform}/{shop_ref}
    Authorization: Bearer {COMPETITOR_VENDOR_API_KEY}

If a vendor differs structurally (POST, GraphQL, a job-and-poll flow), that
belongs in a sibling module implementing the same `fetch_sales` signature — not
in more branches here.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.services.competitor.base import (
    ProductObservation,
    SalesReading,
    polite_get_json,
)

log = get_logger("app.services.competitor.vendor")

#: Accepted spellings per field, most specific first.
_REVENUE_KEYS = ("revenue_vnd", "revenue", "gmv_vnd", "gmv", "estimated_revenue")
_SOLD_KEYS = ("items_sold", "units_sold", "sold", "sold_count", "order_count")
_VOUCHER_KEYS = ("voucher_count", "vouchers", "promotion_count")
_PRODUCT_KEYS = ("products", "top_products", "items", "best_sellers")
_NAME_KEYS = ("name", "title", "product_name")
_PRICE_KEYS = ("price_vnd", "price", "current_price")
_DISCOUNT_KEYS = ("discount_pct", "discount", "discount_percent")


def is_configured() -> bool:
    return bool(settings.COMPETITOR_VENDOR_BASE_URL and settings.COMPETITOR_VENDOR_API_KEY)


async def fetch_sales(platform: str, shop_ref: str) -> tuple[SalesReading | None, str | None]:
    """Ask the vendor for one shop's sales figures.

    Returns ``(reading, error)``. ``(None, None)`` means "not configured" — a
    normal state, not a failure, so the caller falls through to the next source.
    """
    if not is_configured():
        return None, None

    base = (settings.COMPETITOR_VENDOR_BASE_URL or "").rstrip("/")
    url = f"{base}/shops/{platform}/{shop_ref}"
    payload, err = await polite_get_json(
        url,
        headers={"Authorization": f"Bearer {settings.COMPETITOR_VENDOR_API_KEY}"},
    )
    if err:
        return None, f"Nguồn dữ liệu thị trường lỗi: {err}"
    assert payload is not None

    # Vendors wrap the useful part in `data` about half the time.
    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(body, dict):
        return None, "Nguồn dữ liệu thị trường trả về cấu trúc không đọc được."

    products = _products(body)
    reading = SalesReading(
        source="vendor",
        items_sold_total=_int(body, _SOLD_KEYS) or _sum_sold(products),
        revenue_est_vnd=_int(body, _REVENUE_KEYS) or _sum_revenue(products),
        voucher_count=_int(body, _VOUCHER_KEYS),
        top_products=products,
        promotions=[
            {"name": p.name, "discount_pct": p.discount_pct, "price_vnd": p.price_vnd}
            for p in products
            if p.discount_pct
        ],
    )
    if reading.items_sold_total is None and reading.revenue_est_vnd is None:
        # A 200 with none of the fields we came for is a mapping problem, and
        # silently recording an empty snapshot would hide it.
        return None, (
            "Nguồn dữ liệu thị trường trả 200 nhưng không có chỉ số bán hàng nào "
            f"nhận ra được (các khoá nhận được: {sorted(body)[:8]})."
        )
    return reading, None


def _products(body: dict[str, Any]) -> list[ProductObservation]:
    raw: list[Any] = next(
        (body[k] for k in _PRODUCT_KEYS if isinstance(body.get(k), list)), []
    )
    out: list[ProductObservation] = []
    for entry in raw[: settings.COMPETITOR_TOP_N]:
        if not isinstance(entry, dict):
            continue
        out.append(
            ProductObservation(
                name=str(_first(entry, _NAME_KEYS) or "")[:200],
                price_vnd=_int(entry, _PRICE_KEYS),
                sold=_int(entry, _SOLD_KEYS),
                discount_pct=_float(entry, _DISCOUNT_KEYS),
            )
        )
    return out


def _sum_sold(products: list[ProductObservation]) -> int | None:
    total = sum(p.sold or 0 for p in products)
    return total or None


def _sum_revenue(products: list[ProductObservation]) -> int | None:
    total = sum((p.price_vnd or 0) * (p.sold or 0) for p in products)
    return total or None


def _first(d: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def _int(d: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    raw = _first(d, keys)
    if raw is None:
        return None
    # `"vouchers": [...]` is a count expressed as a list — a real shape some
    # vendors use, and the alias list can't tell them apart by name.
    if isinstance(raw, list):
        return len(raw) or None
    if isinstance(raw, dict):
        return None
    try:
        # Vendors send "1.234.567₫" as often as 1234567.
        return int(float(str(raw).replace(",", "").replace(".", "").replace("₫", "").strip()))
    except (TypeError, ValueError):
        return None


def _float(d: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    raw = _first(d, keys)
    if raw is None or isinstance(raw, (list, dict)):
        return None
    try:
        return abs(float(str(raw).replace("%", "").replace(",", ".").strip()))
    except (TypeError, ValueError):
        return None
