"""Collector parsing + trend maths.

The network call itself can't be tested here (and the marketplace endpoints are
unofficial, so they'd be flaky even with network). What IS testable — and what
actually breaks in practice — is the parsing of a payload into a snapshot, and
the failure path when the marketplace says no. Both are covered by mocking the
one HTTP seam, `polite_get_json`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.competitor import CompetitorSnapshot
from app.services import competitor_service
from app.services.competitor import lazada as lazada_mod
from app.services.competitor import shopee as shopee_mod
from app.services.competitor.lazada import LazadaCollector
from app.services.competitor.shopee import ShopeeCollector
from app.services.competitor.urls import ParsedCompetitor

SHOPEE_TARGET = ParsedCompetitor("shopee", "123456789", None, "https://shopee.vn/shop/123456789")
LAZADA_TARGET = ParsedCompetitor("lazada", None, "ten-shop", "https://www.lazada.vn/shop/ten-shop")


# --- Shopee -----------------------------------------------------------------


def _shopee_payloads():
    shop = {
        "data": {
            "shopid": 123456789,
            "name": "Coolmate Official",
            "follower_count": 250_000,
            "rating_star": 4.8,
            "item_count": 320,
            "vouchers": [{"id": 1}, {"id": 2}],
        }
    }
    items = {
        "items": [
            {
                "item_basic": {
                    # Shopee sends VND × 100_000.
                    "name": "Áo thun cotton",
                    "price": 199_000 * 100_000,
                    "historical_sold": 1_200,
                    "raw_discount": 20,
                }
            },
            {
                "item_basic": {
                    "name": "Quần jean",
                    "price": 450_000 * 100_000,
                    "historical_sold": 300,
                    "raw_discount": 0,
                }
            },
        ]
    }
    return shop, items


@pytest.mark.asyncio
async def test_shopee_collector_parses_a_realistic_payload(monkeypatch):
    shop, items = _shopee_payloads()
    calls: list[str] = []

    async def fake_get(url, *, headers=None):  # noqa: ANN001, ARG001
        calls.append(url)
        return (shop, None) if "get_shop_base" in url else (items, None)

    monkeypatch.setattr(shopee_mod, "polite_get_json", fake_get)

    got = await ShopeeCollector().collect(SHOPEE_TARGET)

    assert got.ok
    assert got.display_name == "Coolmate Official"
    assert got.follower_count == 250_000
    assert got.rating == 4.8
    assert got.product_count == 320
    assert got.voucher_count == 2
    # Prices de-scaled from Shopee's ×100_000 representation.
    assert got.top_products[0].price_vnd == 199_000
    assert got.items_sold_total == 1_500
    # Estimated GMV = Σ price × historical_sold.
    assert got.revenue_est_vnd == 199_000 * 1_200 + 450_000 * 300
    # Only the discounted item counts as a promotion.
    assert len(got.promotions) == 1
    assert got.promotions[0]["name"] == "Áo thun cotton"
    # Two calls: shop base, then best sellers.
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_shopee_blocked_is_a_recorded_failure_not_a_crash(monkeypatch):
    async def blocked(url, *, headers=None):  # noqa: ANN001, ARG001
        return None, "shopee.vn chặn yêu cầu (HTTP 403) — sàn đang giới hạn truy cập tự động."

    monkeypatch.setattr(shopee_mod, "polite_get_json", blocked)
    got = await ShopeeCollector().collect(SHOPEE_TARGET)

    assert got.ok is False
    assert "403" in (got.error or "")


@pytest.mark.asyncio
async def test_shopee_partial_capture_keeps_shop_data(monkeypatch):
    """Shop info succeeded, product listing failed — keep what we got."""
    shop, _ = _shopee_payloads()

    async def half(url, *, headers=None):  # noqa: ANN001, ARG001
        if "get_shop_base" in url:
            return shop, None
        return None, "shopee.vn trả về HTTP 500."

    monkeypatch.setattr(shopee_mod, "polite_get_json", half)
    got = await ShopeeCollector().collect(SHOPEE_TARGET)

    assert got.ok is True
    assert got.follower_count == 250_000
    assert got.top_products == []
    assert "không lấy được sản phẩm" in (got.error or "")


def test_shopee_price_descaling():
    assert shopee_mod._price(199_000 * 100_000) == 199_000
    assert shopee_mod._price(0) is None
    assert shopee_mod._price(None) is None
    assert shopee_mod._price("garbage") is None


# --- Lazada -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_lazada_collector_parses_a_realistic_payload(monkeypatch):
    payload = {
        "mods": {
            "shopInfo": {"name": "Shop Thời Trang"},
            "listItems": [
                {
                    "name": "Váy hoa nhí",
                    "price": "299000",
                    "itemSoldCntShow": "1.2k đã bán",
                    "discount": "-25%",
                    "ratingScore": "4.6",
                },
                {
                    "name": "Áo sơ mi",
                    "price": "199,000",
                    "itemSoldCntShow": "350 đã bán",
                    "discount": "",
                    "ratingScore": "4.4",
                },
            ],
        }
    }

    async def fake_get(url, *, headers=None):  # noqa: ANN001, ARG001
        return payload, None

    monkeypatch.setattr(lazada_mod, "polite_get_json", fake_get)
    got = await LazadaCollector().collect(LAZADA_TARGET)

    assert got.ok
    assert got.display_name == "Shop Thời Trang"
    assert got.product_count == 2
    assert got.items_sold_total == 1_550          # 1200 + 350
    assert got.revenue_est_vnd == 299_000 * 1_200 + 199_000 * 350
    assert got.rating == 4.5                      # mean of 4.6 / 4.4
    assert len(got.promotions) == 1               # only the -25% item
    # Lazada's payload carries no follower count.
    assert got.follower_count is None


@pytest.mark.asyncio
async def test_lazada_product_link_asks_for_the_shop_link():
    target = ParsedCompetitor("lazada", "1234567890", None, "https://www.lazada.vn/products/x-i1234567890.html")
    got = await LazadaCollector().collect(target)

    assert got.ok is False
    assert "trang cửa hàng" in (got.error or "")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2k đã bán", 1_200),
        ("2.5k sold", 2_500),
        ("350 đã bán", 350),
        ("1,200 đã bán", 1_200),   # comma = thousands separator
        ("1m sold", 1_000_000),
        ("", None),
        (None, None),
    ],
)
def test_lazada_sold_count_parsing(raw, expected):
    assert lazada_mod._as_sold(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("299000", 299_000), ("199,000", 199_000), ("₫ 89.000", 89_000), (None, None), ("", None)],
)
def test_lazada_price_parsing(raw, expected):
    assert lazada_mod._as_price(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [("-25%", 25.0), ("50% off", 50.0), ("", None)])
def test_lazada_discount_parsing(raw, expected):
    assert lazada_mod._as_discount(raw) == expected


# --- Trend + share maths ----------------------------------------------------


def _snap(
    revenue: int | None = None,
    *,
    followers: int | None = None,
    rating: float | None = None,
    ok: bool = True,
    minutes: int = 0,
) -> CompetitorSnapshot:
    return CompetitorSnapshot(
        competitor_id=1,
        captured_at=datetime.now(UTC) + timedelta(minutes=minutes),
        ok=ok,
        revenue_est_vnd=revenue,
        follower_count=followers,
        rating=rating,
    )


def test_trend_pct_needs_two_successful_readings():
    assert competitor_service.trend_pct([], "revenue_est_vnd") is None
    assert competitor_service.trend_pct([_snap(100)], "revenue_est_vnd") is None


def test_trend_pct_computes_first_to_last_change():
    snaps = [_snap(100, minutes=0), _snap(150, minutes=1)]
    assert competitor_service.trend_pct(snaps, "revenue_est_vnd") == 50.0

    snaps = [_snap(200, minutes=0), _snap(150, minutes=1)]
    assert competitor_service.trend_pct(snaps, "revenue_est_vnd") == -25.0


def test_trend_pct_ignores_failed_and_empty_readings():
    snaps = [
        _snap(100, minutes=0),
        _snap(None, ok=False, minutes=1),   # failed capture
        _snap(None, minutes=2),             # succeeded but no value
        _snap(120, minutes=3),
    ]
    assert competitor_service.trend_pct(snaps, "revenue_est_vnd") == 20.0


def test_follower_share_is_share_of_the_tracked_set():
    # Follower count, not revenue: the listing endpoints that would carry sales
    # are blocked, so a revenue share would be invented.
    share = competitor_service.follower_share(
        {1: _snap(followers=600), 2: _snap(followers=400)}
    )
    assert share == {1: 60.0, 2: 40.0}


def test_follower_share_is_empty_when_nothing_measured():
    assert competitor_service.follower_share({1: None, 2: _snap()}) == {}
    assert competitor_service.follower_share({}) == {}


def test_trend_abs_reports_rating_movement_not_percent():
    snaps = [_snap(rating=4.9, minutes=0), _snap(rating=4.78, minutes=1)]
    # A percentage of a 4.9 average would be meaningless; the drop is the signal.
    assert competitor_service.trend_abs(snaps, "rating") == -0.12


def test_trend_abs_needs_two_readings():
    assert competitor_service.trend_abs([_snap(rating=4.9)], "rating") is None
