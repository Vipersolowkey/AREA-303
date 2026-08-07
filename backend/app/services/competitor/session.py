"""Sales figures via a logged-in Shopee session replayed in a real browser.

## Read this before enabling it

Shopee serves sales figures only to an authenticated visitor. This module reuses
a session the operator logged in themselves (captured once by
``scripts/shopee_login.py``) and drives it with a real Chromium.

**The risk is on the account, and it is not theoretical.** Shopee's terms
prohibit automated access. An account used this way can be rate-limited,
challenged with a CAPTCHA, or banned — and a banned account takes its order
history with it. Use a throwaway account, never the one running the business.
That is why ``COMPETITOR_USE_SESSION`` defaults to False and why the login
script writes to a gitignored path.

Sessions also expire. When the cookie dies the shop page comes back as the login
wall, which this module reports as a specific, actionable error rather than a
generic parse failure — otherwise the operator sees "no data" and starts
debugging the collector instead of logging in again.

## How the read works

The listing endpoint is called with `fetch()` **from inside the loaded shop
page**, not from Python. That matters: the request then inherits the page's
origin, cookies and whatever headers Shopee's own SDK installs, which is what
makes it a session read rather than a forged one. We do not construct
signatures, rotate proxies, spoof fingerprints, or impersonate a crawler — if
the session is genuinely logged in it works, and if it isn't we report that.

One browser is launched per collection run and shared across shops; launching
per shop costs ~1.5s each and buys nothing.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import TracebackType
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.services.competitor.base import (
    MIN_REQUEST_GAP_S,
    ProductObservation,
    SalesReading,
)

log = get_logger("app.services.competitor.session")

#: Shopee's anti-automation verdict. Arrives with HTTP 200 and this in the body,
#: so status code alone is not a success signal.
_BLOCKED_ERROR = 90309999
#: Shopee returns VND multiplied by 100_000.
_PRICE_SCALE = 100_000
_PAGE_TIMEOUT_MS = 45_000
#: How long to let the SPA hydrate before asking it to fetch for us.
_HYDRATE_MS = 6_000


def session_file() -> Path:
    return Path(settings.COMPETITOR_SESSION_PATH)


def is_configured() -> tuple[bool, str | None]:
    """``(usable, reason_if_not)`` — checked before a run, not per shop."""
    if not settings.COMPETITOR_USE_SESSION:
        return False, None
    if not session_file().exists():
        return False, (
            f"Đã bật COMPETITOR_USE_SESSION nhưng không thấy file session tại "
            f"{session_file()}. Chạy `python scripts/shopee_login.py` để đăng nhập một lần."
        )
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False, (
            "Đã bật COMPETITOR_USE_SESSION nhưng chưa cài playwright. "
            "Chạy `pip install playwright && playwright install chromium`."
        )
    return True, None


class ShopeeSessionReader:
    """Holds one browser for the length of a collection run.

    Use as an async context manager. Constructing it does not launch anything —
    the browser starts on first use — so a run that ends up with nothing to read
    costs nothing.
    """

    def __init__(self) -> None:
        self._pw: Any = None
        self._browser: Any = None
        self._ctx: Any = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> ShopeeSessionReader:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def _ensure_browser(self) -> None:
        if self._ctx is not None:
            return
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        self._ctx = await self._browser.new_context(
            storage_state=str(session_file()),
            locale="vi-VN",
            viewport={"width": 1366, "height": 900},
        )

    async def close(self) -> None:
        for closer in (self._ctx, self._browser):
            if closer is not None:
                try:
                    await closer.close()
                except Exception:  # noqa: BLE001 - teardown must not mask a real error
                    log.debug("competitor.session.close_failed", exc_info=True)
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:  # noqa: BLE001
                log.debug("competitor.session.stop_failed", exc_info=True)
        self._pw = self._browser = self._ctx = None

    async def fetch_sales(
        self, shop_id: str, shop_url: str
    ) -> tuple[SalesReading | None, str | None]:
        """Read one shop's best sellers. Returns ``(reading, error)``."""
        # Serialised: two Chromium tabs hammering shopee.vn concurrently is
        # exactly the traffic pattern that gets a session flagged.
        async with self._lock:
            try:
                await self._ensure_browser()
            except Exception as exc:  # noqa: BLE001
                return None, f"Không mở được browser cho session Shopee: {exc}"
            try:
                return await self._read(shop_id, shop_url)
            except Exception as exc:  # noqa: BLE001
                # A collector failure is data, not an incident — record and move on.
                log.warning("competitor.session.read_failed", error=str(exc))
                return None, f"Đọc bằng session Shopee thất bại: {type(exc).__name__}: {exc}"
            finally:
                await asyncio.sleep(MIN_REQUEST_GAP_S)

    async def _read(
        self, shop_id: str, shop_url: str
    ) -> tuple[SalesReading | None, str | None]:
        assert self._ctx is not None
        page = await self._ctx.new_page()
        try:
            await page.goto(shop_url, wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT_MS)
            await page.wait_for_timeout(_HYDRATE_MS)

            body = await page.inner_text("body")
            if _looks_like_login_wall(body):
                return None, (
                    "Session Shopee đã hết hạn (trang trả về yêu cầu đăng nhập). "
                    "Chạy lại `python scripts/shopee_login.py`."
                )

            raw = await page.evaluate(_FETCH_JS, _listing_path(shop_id))
        finally:
            await page.close()

        if not isinstance(raw, dict) or raw.get("ok") is not True:
            detail = (raw or {}).get("detail") if isinstance(raw, dict) else None
            return None, f"Shopee không trả về danh sách sản phẩm: {detail or 'không rõ'}"

        try:
            payload = json.loads(raw.get("text") or "")
        except ValueError:
            return None, "Shopee trả về nội dung không phải JSON (thường là trang xác minh)."

        if not isinstance(payload, dict):
            return None, "Shopee trả về cấu trúc không mong đợi."
        if payload.get("error") == _BLOCKED_ERROR:
            return None, (
                "Shopee từ chối yêu cầu dù có session (error 90309999) — session "
                "chưa hợp lệ, hoặc account đang bị giới hạn truy cập tự động."
            )

        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return None, "Shopee trả về danh sách sản phẩm rỗng."

        return _to_reading(items), None


def _listing_path(shop_id: str) -> str:
    top_n = max(1, min(int(settings.COMPETITOR_TOP_N), 60))
    return (
        "/api/v4/search/search_items"
        f"?by=sales&limit={top_n}&match_id={shop_id}"
        "&newest=0&order=desc&page_type=shop&scenario=PAGE_OTHERS&version=2"
    )


#: Runs in the page, so the request carries the page's own session context.
_FETCH_JS = """
async (path) => {
  try {
    const r = await fetch(path, {headers: {'Accept': 'application/json'}});
    const text = await r.text();
    return {ok: true, status: r.status, text};
  } catch (e) {
    return {ok: false, detail: String(e)};
  }
}
"""

_LOGIN_WALL_MARKERS = ("vui lòng đăng nhập", "trang không khả dụng", "page not available")


def _looks_like_login_wall(body: str) -> bool:
    low = body.lower()
    return any(m in low for m in _LOGIN_WALL_MARKERS)


def _to_reading(items: list[Any]) -> SalesReading:
    observed: list[ProductObservation] = []
    sold_total = 0
    revenue_est = 0
    for entry in items:
        basic = (entry or {}).get("item_basic") or {} if isinstance(entry, dict) else {}
        price = _price(basic.get("price"))
        sold = _int(basic.get("historical_sold")) or 0
        observed.append(
            ProductObservation(
                name=str(basic.get("name") or "")[:200],
                price_vnd=price,
                sold=sold,
                discount_pct=_float(basic.get("raw_discount")),
            )
        )
        sold_total += sold
        if price:
            revenue_est += price * sold

    return SalesReading(
        source="session",
        items_sold_total=sold_total or None,
        # Cumulative GMV over the products sampled — price × historical_sold,
        # an estimate, never a figure Shopee reports.
        revenue_est_vnd=revenue_est or None,
        top_products=observed,
        promotions=[
            {"name": p.name, "discount_pct": p.discount_pct, "price_vnd": p.price_vnd}
            for p in observed
            if p.discount_pct
        ],
    )


def _price(raw: object) -> int | None:
    value = _int(raw)
    return value // _PRICE_SCALE if value else None


def _int(raw: object) -> int | None:
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return None


def _float(raw: object) -> float | None:
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None
