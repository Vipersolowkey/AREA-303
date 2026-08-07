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

from app.core.config import settings
from app.models.competitor import CompetitorSnapshot
from app.services import competitor_service
from app.services.competitor import lazada as lazada_mod
from app.services.competitor import session as session_mod
from app.services.competitor import shopee as shopee_mod
from app.services.competitor import vendor as vendor_mod
from app.services.competitor.base import SalesReading
from app.services.competitor.lazada import LazadaCollector
from app.services.competitor.shopee import ShopeeCollector
from app.services.competitor.urls import ParsedCompetitor

SHOPEE_TARGET = ParsedCompetitor("shopee", "123456789", None, "https://shopee.vn/shop/123456789")
LAZADA_TARGET = ParsedCompetitor("lazada", None, "ten-shop", "https://www.lazada.vn/shop/ten-shop")


# --- Shopee -----------------------------------------------------------------


def _shop_base_payload():
    return {
        "data": {
            "shopid": 123456789,
            "name": "Coolmate Official",
            "follower_count": 250_000,
            "rating_star": 4.8,
            "item_count": 320,
            "vouchers": [{"id": 1}, {"id": 2}],
        }
    }


def _shopee_items_payload():
    return {
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


class _FakeSalesReader:
    """Stands in for the browser session — same signature, no Chromium."""

    def __init__(self, reading=None, error=None):  # noqa: ANN001
        self._reading, self._error = reading, error
        self.calls: list[tuple[str, str]] = []

    async def fetch_sales(self, shop_id, shop_url):  # noqa: ANN001
        self.calls.append((shop_id, shop_url))
        return self._reading, self._error


@pytest.mark.asyncio
async def test_shopee_shop_level_capture_needs_no_sales_source(monkeypatch):
    """The anonymous half is a complete reading, not a failure."""
    calls: list[str] = []

    async def fake_get(url, *, headers=None):  # noqa: ANN001, ARG001
        calls.append(url)
        return _shop_base_payload(), None

    monkeypatch.setattr(shopee_mod, "polite_get_json", fake_get)
    got = await ShopeeCollector().collect(SHOPEE_TARGET)

    assert got.ok is True
    assert got.display_name == "Coolmate Official"
    assert got.follower_count == 250_000
    assert got.rating == 4.8
    assert got.product_count == 320
    assert got.voucher_count == 2
    # No sales source configured, so the sales half stays empty — and says why
    # rather than looking like data that hasn't arrived yet.
    assert got.sales_source is None
    assert got.items_sold_total is None
    assert got.revenue_est_vnd is None
    assert "Chưa cấu hình nguồn số liệu bán hàng" in (got.error or "")
    # Exactly one call: nothing else answers anonymously, so nothing else is tried.
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_shopee_uses_the_session_reader_when_one_is_given(monkeypatch):
    async def fake_get(url, *, headers=None):  # noqa: ANN001, ARG001
        return _shop_base_payload(), None

    monkeypatch.setattr(shopee_mod, "polite_get_json", fake_get)
    reading = session_mod._to_reading(_shopee_items_payload()["items"])
    reader = _FakeSalesReader(reading=reading)

    got = await ShopeeCollector(reader).collect(SHOPEE_TARGET)

    assert got.ok is True
    assert got.sales_source == "session"
    # Shop-level fields survive the merge.
    assert got.follower_count == 250_000
    # Prices de-scaled from Shopee's ×100_000 representation.
    assert got.top_products[0].price_vnd == 199_000
    assert got.items_sold_total == 1_500
    assert got.revenue_est_vnd == 199_000 * 1_200 + 450_000 * 300
    # Only the discounted item counts as a promotion.
    assert len(got.promotions) == 1
    assert got.promotions[0]["name"] == "Áo thun cotton"
    # Called with the resolved numeric shop id, not the slug.
    assert reader.calls == [("123456789", SHOPEE_TARGET.url)]


@pytest.mark.asyncio
async def test_shopee_session_failure_keeps_the_shop_level_reading(monkeypatch):
    """An expired session must not throw away the half that worked."""

    async def fake_get(url, *, headers=None):  # noqa: ANN001, ARG001
        return _shop_base_payload(), None

    monkeypatch.setattr(shopee_mod, "polite_get_json", fake_get)
    reader = _FakeSalesReader(error="Session Shopee đã hết hạn.")

    got = await ShopeeCollector(reader).collect(SHOPEE_TARGET)

    assert got.ok is True
    assert got.follower_count == 250_000
    assert got.sales_source is None
    assert got.top_products == []
    assert "hết hạn" in (got.error or "")


@pytest.mark.asyncio
async def test_shopee_prefers_the_vendor_over_the_session(monkeypatch):
    """Vendor data carries no account risk, so it wins when both are available."""

    async def fake_get(url, *, headers=None):  # noqa: ANN001, ARG001
        return _shop_base_payload(), None

    monkeypatch.setattr(shopee_mod, "polite_get_json", fake_get)

    async def fake_vendor(platform, shop_ref):  # noqa: ANN001, ARG001
        return SalesReading(source="vendor", items_sold_total=999), None

    monkeypatch.setattr(vendor_mod, "fetch_sales", fake_vendor)
    reader = _FakeSalesReader(reading=SalesReading(source="session", items_sold_total=1))

    got = await ShopeeCollector(reader).collect(SHOPEE_TARGET)

    assert got.sales_source == "vendor"
    assert got.items_sold_total == 999
    # The session was never touched — no browser launched, no account exposed.
    assert reader.calls == []


@pytest.mark.asyncio
async def test_shopee_blocked_is_a_recorded_failure_not_a_crash(monkeypatch):
    async def blocked(url, *, headers=None):  # noqa: ANN001, ARG001
        return None, "shopee.vn chặn yêu cầu (HTTP 403) — sàn đang giới hạn truy cập tự động."

    monkeypatch.setattr(shopee_mod, "polite_get_json", blocked)
    got = await ShopeeCollector().collect(SHOPEE_TARGET)

    assert got.ok is False
    assert "403" in (got.error or "")


def test_shopee_price_descaling():
    assert session_mod._price(199_000 * 100_000) == 199_000
    assert session_mod._price(0) is None
    assert session_mod._price(None) is None
    assert session_mod._price("garbage") is None


# --- Session reader ---------------------------------------------------------


def test_session_is_off_unless_explicitly_enabled(monkeypatch):
    monkeypatch.setattr(settings, "COMPETITOR_USE_SESSION", False)
    usable, reason = session_mod.is_configured()
    assert usable is False
    # Off by default is not a misconfiguration, so nothing to warn about.
    assert reason is None


def test_session_enabled_without_a_session_file_explains_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "COMPETITOR_USE_SESSION", True)
    monkeypatch.setattr(settings, "COMPETITOR_SESSION_PATH", str(tmp_path / "nope.json"))
    usable, reason = session_mod.is_configured()
    assert usable is False
    assert "shopee_login.py" in (reason or "")


def test_session_login_wall_is_detected():
    assert session_mod._looks_like_login_wall("Trang không khả dụng, vui lòng đăng nhập")
    assert session_mod._looks_like_login_wall("Bạn Vui Lòng Đăng Nhập lại")
    assert not session_mod._looks_like_login_wall("Áo thun cotton — 199.000₫")


def test_session_listing_limit_is_clamped(monkeypatch):
    """A misconfigured TOP_N must not turn a trend read into a crawl."""
    monkeypatch.setattr(settings, "COMPETITOR_TOP_N", 5_000)
    assert "limit=60" in session_mod._listing_path("123")
    monkeypatch.setattr(settings, "COMPETITOR_TOP_N", 0)
    assert "limit=1" in session_mod._listing_path("123")


# --- Vendor adapter ---------------------------------------------------------


@pytest.mark.asyncio
async def test_vendor_is_skipped_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "COMPETITOR_VENDOR_BASE_URL", None)
    monkeypatch.setattr(settings, "COMPETITOR_VENDOR_API_KEY", None)
    reading, err = await vendor_mod.fetch_sales("shopee", "123")
    # Not configured is a normal state — neither data nor an error.
    assert reading is None
    assert err is None


@pytest.mark.asyncio
async def test_vendor_maps_alternate_field_names(monkeypatch):
    """Different vendors, different spellings — one adapter."""
    monkeypatch.setattr(settings, "COMPETITOR_VENDOR_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setattr(settings, "COMPETITOR_VENDOR_API_KEY", "k")

    captured: dict[str, object] = {}

    async def fake_get(url, *, headers=None):  # noqa: ANN001
        captured["url"] = url
        captured["auth"] = (headers or {}).get("Authorization")
        return {
            "data": {
                # `gmv` not `revenue`, `units_sold` not `items_sold`
                "gmv": "1.250.000.000",
                "units_sold": 4_200,
                "vouchers": [{"id": 1}, {"id": 2}, {"id": 3}],
                "best_sellers": [
                    {"title": "Áo polo", "current_price": "299000", "sold": 900, "discount": "-15%"}
                ],
            }
        }, None

    monkeypatch.setattr(vendor_mod, "polite_get_json", fake_get)
    reading, err = await vendor_mod.fetch_sales("shopee", "123")

    assert err is None
    assert reading is not None
    assert reading.source == "vendor"
    assert reading.revenue_est_vnd == 1_250_000_000
    assert reading.items_sold_total == 4_200
    # A voucher count expressed as a list.
    assert reading.voucher_count == 3
    assert reading.top_products[0].name == "Áo polo"
    assert reading.top_products[0].price_vnd == 299_000
    assert reading.promotions[0]["discount_pct"] == 15.0
    assert captured["url"] == "https://api.example.com/v1/shops/shopee/123"
    assert captured["auth"] == "Bearer k"


@pytest.mark.asyncio
async def test_vendor_200_with_no_recognised_fields_is_an_error(monkeypatch):
    """Silently storing an empty snapshot would hide a mapping bug."""
    monkeypatch.setattr(settings, "COMPETITOR_VENDOR_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(settings, "COMPETITOR_VENDOR_API_KEY", "k")

    async def fake_get(url, *, headers=None):  # noqa: ANN001, ARG001
        return {"shop": {"followers": 10}}, None

    monkeypatch.setattr(vendor_mod, "polite_get_json", fake_get)
    reading, err = await vendor_mod.fetch_sales("shopee", "123")

    assert reading is None
    assert "không có chỉ số bán hàng nào" in (err or "")


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
    sold: int | None = None,
    source: str | None = None,
    ok: bool = True,
    minutes: int = 0,
    days: int = 0,
) -> CompetitorSnapshot:
    return CompetitorSnapshot(
        competitor_id=1,
        captured_at=datetime.now(UTC) + timedelta(minutes=minutes, days=days),
        ok=ok,
        revenue_est_vnd=revenue,
        follower_count=followers,
        rating=rating,
        items_sold_total=sold,
        sales_source=source,
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


def test_revenue_share_is_empty_without_a_sales_source():
    # No sales source means no revenue anywhere, so there is no revenue share to
    # report — the caller falls back to followers rather than showing a zero.
    assert competitor_service.revenue_share({1: _snap(followers=600)}) == {}


def test_revenue_share_splits_estimated_gmv():
    share = competitor_service.revenue_share(
        {1: _snap(750_000_000, source="session"), 2: _snap(250_000_000, source="session")}
    )
    assert share == {1: 75.0, 2: 25.0}


# --- Period sales (the number historical_sold can't give you) ----------------


def test_period_sales_measures_the_gap_between_two_readings():
    snaps = [
        _snap(1_000_000_000, sold=10_000, source="session", days=0),
        _snap(1_020_000_000, sold=10_200, source="session", days=7),
    ]
    got = competitor_service.period_sales(snaps)

    assert got is not None
    assert got.units == 200
    # Priced at the later reading's average selling price: 1.02bn / 10_200 = 100_000.
    assert got.revenue_vnd == 200 * 100_000
    assert (got.to_at - got.from_at).days == 7


def test_period_sales_needs_two_readings_with_a_sales_source():
    # One reading is not a period.
    assert competitor_service.period_sales([_snap(sold=10, source="session")]) is None
    # Two readings, but no sales source: items_sold_total can't be trusted here
    # because nothing populated it.
    assert competitor_service.period_sales([_snap(sold=10), _snap(sold=20)]) is None


def test_period_sales_refuses_to_report_a_negative():
    """Shopee resetting a counter must not read as 'sold −500 this week'."""
    snaps = [
        _snap(sold=10_000, source="session", days=0),
        _snap(sold=9_500, source="session", days=7),
    ]
    assert competitor_service.period_sales(snaps) is None


def test_period_sales_ignores_readings_that_lack_sales():
    """A gap where the session expired shouldn't distort the period."""
    snaps = [
        _snap(1_000_000_000, sold=10_000, source="session", days=0),
        _snap(followers=5, days=3),                                    # shop-level only
        _snap(1_010_000_000, sold=10_100, source="session", days=6),
    ]
    got = competitor_service.period_sales(snaps)
    assert got is not None
    assert got.units == 100
    assert (got.to_at - got.from_at).days == 6
