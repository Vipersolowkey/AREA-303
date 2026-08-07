"""URL parsing is the part of competitor tracking that's fully deterministic,
so it gets real coverage — including the shapes people actually paste (with
tracking params, trailing slashes, no scheme)."""

from __future__ import annotations

import pytest

from app.services.competitor import InvalidCompetitorUrl, parse_competitor_url


@pytest.mark.parametrize(
    ("url", "shop_id"),
    [
        ("https://shopee.vn/shop/123456789", "123456789"),
        ("https://shopee.vn/shop/123456789/search", "123456789"),
        ("https://shopee.vn/shop/123456789?smtt=0.0.9", "123456789"),
        ("shopee.vn/shop/123456789", "123456789"),  # no scheme
        ("https://shopee.vn/shop/123456789/", "123456789"),  # trailing slash
    ],
)
def test_shopee_shop_urls(url, shop_id):
    got = parse_competitor_url(url)
    assert got.platform == "shopee"
    assert got.shop_id == shop_id
    assert got.ref == shop_id


def test_shopee_product_url_yields_the_shop_id():
    got = parse_competitor_url(
        "https://shopee.vn/Ao-thun-nam-cotton-i.123456789.9876543210"
    )
    assert got.platform == "shopee"
    # The first number in `-i.<shopid>.<itemid>` is the shop.
    assert got.shop_id == "123456789"


def test_shopee_vanity_username():
    got = parse_competitor_url("https://shopee.vn/coolmate.official")
    assert got.platform == "shopee"
    assert got.shop_slug == "coolmate.official"
    assert got.shop_id is None


@pytest.mark.parametrize("reserved", ["cart", "search", "user", "api", "mall"])
def test_shopee_reserved_paths_are_not_shops(reserved):
    with pytest.raises(InvalidCompetitorUrl):
        parse_competitor_url(f"https://shopee.vn/{reserved}")


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://www.lazada.vn/shop/ten-shop/", "ten-shop"),
        ("https://lazada.vn/shop/ten-shop", "ten-shop"),
        ("https://www.lazada.vn/shop/ten-shop?spm=a2o4n.home", "ten-shop"),
    ],
)
def test_lazada_shop_urls(url, slug):
    got = parse_competitor_url(url)
    assert got.platform == "lazada"
    assert got.shop_slug == slug


def test_lazada_product_url():
    got = parse_competitor_url(
        "https://www.lazada.vn/products/ao-thun-nam-i1234567890-s9876543210.html"
    )
    assert got.platform == "lazada"
    assert got.shop_id == "1234567890"


def test_tracking_params_are_stripped_so_one_shop_is_one_entry():
    a = parse_competitor_url("https://shopee.vn/shop/555?smtt=0.0.9&utm_source=x")
    b = parse_competitor_url("https://shopee.vn/shop/555")
    assert a.url == b.url
    assert a.ref == b.ref


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "https://tiki.vn/shop/abc",       # unsupported marketplace
        "https://example.com/shop/123",
        "not a url at all",
    ],
)
def test_rejects_unsupported_input(url):
    with pytest.raises(InvalidCompetitorUrl):
        parse_competitor_url(url)


def test_error_message_is_actionable_vietnamese():
    with pytest.raises(InvalidCompetitorUrl) as exc:
        parse_competitor_url("https://tiki.vn/shop/abc")
    assert "Shopee" in str(exc.value) and "Lazada" in str(exc.value)
