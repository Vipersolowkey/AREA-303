"""Collector contract + a deliberately polite HTTP client.

## Read this before touching the collectors

Neither Shopee nor Lazada publishes an API for *other people's* shops — their
official platform APIs only cover a shop you own and have authorised. So the
collectors here call the same undocumented endpoints the marketplaces' own web
apps call. That means:

* **They will break.** Those endpoints are internal, unversioned, and change
  without notice. Treat a failure as normal operation, not an incident — the
  snapshot records `ok=False` with the reason and the UI shows it.
* **They may be blocked.** Both sites run bot protection. A 403 or an HTML
  challenge page instead of JSON is an expected outcome.
* **This code does not try to defeat that.** No proxy rotation, no CAPTCHA
  solving, no fingerprint spoofing. Beyond being the part that turns scraping
  into abuse, evasion is also what gets an IP banned fastest. If a marketplace
  says no, we record no and move on.

What we *do* do is behave: one request at a time per host, a minimum gap
between requests, short timeouts, a single retry at most, and an honest
User-Agent so the far end can identify and rate-limit us.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.core.logging import get_logger
from app.services.competitor.urls import ParsedCompetitor

log = get_logger("app.services.competitor")

#: Be identifiable rather than pretend to be Chrome. A real UA string is still
#: needed because both sites reject empty ones outright.
USER_AGENT = (
    "Mozilla/5.0 (compatible; AREA303-CompetitorWatch/1.0; "
    "+https://github.com/icebearhoho/AREA-303) httpx"
)

#: Minimum seconds between two requests to the same host.
MIN_REQUEST_GAP_S = 1.5
REQUEST_TIMEOUT_S = 12.0


@dataclass
class ProductObservation:
    name: str
    price_vnd: int | None = None
    sold: int | None = None
    discount_pct: float | None = None


@dataclass
class CollectorResult:
    """One collection attempt — success or failure, both worth recording."""

    ok: bool
    error: str | None = None
    display_name: str | None = None
    follower_count: int | None = None
    rating: float | None = None
    product_count: int | None = None
    items_sold_total: int | None = None
    revenue_est_vnd: int | None = None
    voucher_count: int | None = None
    top_products: list[ProductObservation] = field(default_factory=list)
    promotions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def failed(cls, reason: str) -> CollectorResult:
        return cls(ok=False, error=reason)


class Collector(Protocol):
    """Fetch a point-in-time reading for one tracked shop."""

    async def collect(self, target: ParsedCompetitor) -> CollectorResult: ...


class _HostThrottle:
    """Serialise requests per host and keep a minimum gap between them."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._last: dict[str, float] = {}

    def lock_for(self, host: str) -> asyncio.Lock:
        if host not in self._locks:
            self._locks[host] = asyncio.Lock()
        return self._locks[host]

    async def wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < MIN_REQUEST_GAP_S:
            await asyncio.sleep(MIN_REQUEST_GAP_S - elapsed)
        self._last[host] = time.monotonic()


_throttle = _HostThrottle()


async def polite_get_json(
    url: str, *, headers: dict[str, str] | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """GET a JSON endpoint. Returns ``(payload, error)`` — never raises.

    A non-JSON body is the usual sign of a bot-protection interstitial, so it's
    reported as such rather than as a parse error.
    """
    host = httpx.URL(url).host
    async with _throttle.lock_for(host):
        await _throttle.wait(host)
        merged = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            **(headers or {}),
        }
        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT_S, follow_redirects=True
            ) as client:
                resp = await client.get(url, headers=merged)
        except httpx.TimeoutException:
            return None, f"Hết thời gian chờ khi gọi {host}."
        except httpx.HTTPError as exc:
            return None, f"Không kết nối được {host}: {exc}"

        if resp.status_code in (403, 429):
            return None, (
                f"{host} chặn yêu cầu (HTTP {resp.status_code}) — "
                "sàn đang giới hạn truy cập tự động."
            )
        if resp.status_code >= 400:
            return None, f"{host} trả về HTTP {resp.status_code}."

        try:
            payload = resp.json()
        except ValueError:
            return None, (
                f"{host} trả về HTML thay vì JSON — thường là trang xác minh "
                "chống bot hoặc endpoint đã đổi."
            )
        if not isinstance(payload, dict):
            return None, f"{host} trả về dữ liệu không mong đợi."
        return payload, None
