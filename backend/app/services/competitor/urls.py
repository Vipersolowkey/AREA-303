"""Parse Shopee / Lazada URLs into something we can track.

This is the one genuinely reliable part of competitor tracking: URL shapes are
stable and parsing them is pure string work, so it's fully unit-tested. Data
*collection* is the fragile half (see :mod:`.shopee` / :mod:`.lazada`).

Recognised shapes
-----------------
Shopee
    https://shopee.vn/shop/123456789
    https://shopee.vn/shop/123456789/search
    https://shopee.vn/someusername
    https://shopee.vn/Ao-thun-nam-i.123456789.9876543210   (product → shop id)
Lazada
    https://www.lazada.vn/shop/ten-shop/
    https://www.lazada.vn/shop/ten-shop?spm=...
    https://www.lazada.vn/products/ao-thun-i1234567890-s9876543210.html
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

Platform = Literal["shopee", "lazada"]

# Shopee product slug: "...-i.<shopid>.<itemid>"
_SHOPEE_PRODUCT = re.compile(r"-i\.(\d+)\.(\d+)")
# Lazada product slug: "...-i<itemid>-s<skuid>.html"
_LAZADA_PRODUCT = re.compile(r"-i(\d+)(?:-s(\d+))?\.html?$", re.I)

_SHOPEE_HOSTS = ("shopee.vn", "shopee.com", "shopee.sg", "shopee.co.id", "shopee.com.my")
_LAZADA_HOSTS = ("lazada.vn", "lazada.com", "lazada.sg", "lazada.co.id", "lazada.com.my")

# Shopee paths that are pages *about* a shop rather than the shop's identity.
_SHOPEE_RESERVED = {
    "shop", "product", "search", "cart", "user", "buyer", "seller", "mall",
    "daily_discover", "flash_sale", "verify", "login", "api",
}


class InvalidCompetitorUrl(ValueError):
    """The URL isn't a recognisable Shopee/Lazada shop or product link."""


@dataclass(frozen=True)
class ParsedCompetitor:
    platform: Platform
    #: Numeric shop id when the URL exposes one, else None.
    shop_id: str | None
    #: Username / slug when the URL exposes one, else None.
    shop_slug: str | None
    #: Normalised URL we store and re-visit.
    url: str

    @property
    def ref(self) -> str:
        """Stable identifier for this shop — used for de-duplication."""
        return self.shop_id or self.shop_slug or self.url


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _platform_for(host: str) -> Platform | None:
    if any(host == h or host.endswith("." + h) for h in _SHOPEE_HOSTS):
        return "shopee"
    if any(host == h or host.endswith("." + h) for h in _LAZADA_HOSTS):
        return "lazada"
    return None


def parse_competitor_url(raw: str) -> ParsedCompetitor:
    """Turn a pasted URL into a trackable shop reference, or raise.

    Accepts a bare host-less paste (``shopee.vn/shop/123``) by assuming https.
    """
    candidate = (raw or "").strip()
    if not candidate:
        raise InvalidCompetitorUrl("Hãy dán link cửa hàng Shopee hoặc Lazada.")
    if not re.match(r"^https?://", candidate, re.I):
        candidate = "https://" + candidate.lstrip("/")

    parsed = urlparse(candidate)
    host = _host(candidate)
    platform = _platform_for(host)
    if platform is None:
        raise InvalidCompetitorUrl(
            "Chỉ hỗ trợ link Shopee hoặc Lazada. Ví dụ: https://shopee.vn/shop/123456789"
        )

    segments = [s for s in parsed.path.split("/") if s]
    # Drop tracking params — they make the same shop look like two entries.
    normalised = f"https://{parsed.hostname}{parsed.path}".rstrip("/")

    if platform == "shopee":
        return _parse_shopee(segments, normalised)
    return _parse_lazada(segments, normalised)


def _parse_shopee(segments: list[str], url: str) -> ParsedCompetitor:
    # /shop/<id>[/...]
    if segments and segments[0] == "shop" and len(segments) >= 2 and segments[1].isdigit():
        return ParsedCompetitor("shopee", shop_id=segments[1], shop_slug=None, url=url)

    # Product link — the shop id is embedded in the slug.
    for seg in segments:
        m = _SHOPEE_PRODUCT.search(seg)
        if m:
            return ParsedCompetitor("shopee", shop_id=m.group(1), shop_slug=None, url=url)

    # /<username> — a shop's vanity URL.
    if len(segments) == 1 and segments[0].lower() not in _SHOPEE_RESERVED:
        return ParsedCompetitor("shopee", shop_id=None, shop_slug=segments[0], url=url)

    raise InvalidCompetitorUrl(
        "Không đọc được mã cửa hàng từ link Shopee này. "
        "Hãy dùng link trang cửa hàng (shopee.vn/shop/... hoặc shopee.vn/tên-shop)."
    )


def _parse_lazada(segments: list[str], url: str) -> ParsedCompetitor:
    # /shop/<slug>[/...]
    if segments and segments[0] == "shop" and len(segments) >= 2:
        return ParsedCompetitor("lazada", shop_id=None, shop_slug=segments[1], url=url)

    # Product link — carries an item id but not the shop; still trackable as a
    # single product, and the collector resolves the seller from the page.
    for seg in segments:
        m = _LAZADA_PRODUCT.search(seg)
        if m:
            return ParsedCompetitor("lazada", shop_id=m.group(1), shop_slug=None, url=url)

    raise InvalidCompetitorUrl(
        "Không đọc được cửa hàng từ link Lazada này. "
        "Hãy dùng link trang cửa hàng (lazada.vn/shop/tên-shop)."
    )
