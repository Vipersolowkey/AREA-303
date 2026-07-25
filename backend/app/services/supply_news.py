"""Real Google News feed for the Supply Chain early-warning feature.

Pulls live articles via SerpApi (engine=google_news) for Vietnam logistics /
shipping / weather-disruption keywords, so the seller sees actual news rather
than only curated events. Results are cached in-process (long TTL) to protect
the limited SerpApi quota, and it degrades to an empty list if the key is
missing or the call fails (the curated disruption events still render).
"""

from __future__ import annotations

import time

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("app.services.supply_news")

_ENDPOINT = "https://serpapi.com/search"
_CACHE: dict[str, tuple[float, list[dict]]] = {}
_TTL = 6 * 3600.0  # 6h — supply-chain news doesn't need to be minute-fresh

# Region → an extra keyword to localise the query.
_REGION_Q = {
    "Miền Bắc": "miền Bắc",
    "Miền Trung": "miền Trung bão",
    "Miền Nam": "cảng Cát Lái miền Nam",
}


def _query(region: str) -> str:
    return f"logistics vận chuyển cảng biển {_REGION_Q.get(region, '')} Việt Nam".strip()


def _parse(data: dict, limit: int = 6) -> list[dict]:
    out: list[dict] = []
    for item in data.get("news_results", [])[:limit]:
        src = item.get("source")
        source_name = src.get("name") if isinstance(src, dict) else (src or "")
        out.append({
            "title": item.get("title", "").strip(),
            "source": source_name or "",
            "link": item.get("link", ""),
            "date": item.get("date", ""),
            "snippet": (item.get("snippet") or "").strip(),
        })
    return [a for a in out if a["title"] and a["link"]]


async def fetch_supply_news(region: str, *, limit: int = 6) -> list[dict]:
    if not settings.SERPAPI_KEY:
        return []
    q = _query(region)
    now = time.monotonic()
    cached = _CACHE.get(q)
    if cached and now - cached[0] < _TTL:
        return cached[1]
    params = {
        "engine": "google_news", "q": q, "gl": "vn", "hl": "vi",
        "api_key": settings.SERPAPI_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=8.0)) as client:
            r = await client.get(_ENDPOINT, params=params)
        if r.status_code >= 400:
            log.warning("supply_news.http_error", status=r.status_code)
            return cached[1] if cached else []
        articles = _parse(r.json(), limit=limit)
        _CACHE[q] = (now, articles)
        return articles
    except Exception as exc:  # noqa: BLE001 — news is best-effort
        log.warning("supply_news.failed", error=str(exc))
        return cached[1] if cached else []
