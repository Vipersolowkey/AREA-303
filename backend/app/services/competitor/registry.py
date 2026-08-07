"""Pick the collector for a platform."""

from __future__ import annotations

from app.services.competitor.base import Collector, CollectorResult
from app.services.competitor.lazada import LazadaCollector
from app.services.competitor.shopee import ShopeeCollector
from app.services.competitor.urls import ParsedCompetitor, Platform

_COLLECTORS: dict[Platform, Collector] = {
    "shopee": ShopeeCollector(),
    "lazada": LazadaCollector(),
}


async def collect(target: ParsedCompetitor) -> CollectorResult:
    """Run the platform's collector. Never raises — a broken marketplace
    endpoint is normal operation here, so it comes back as a failed result."""
    collector = _COLLECTORS.get(target.platform)
    if collector is None:
        return CollectorResult.failed(f"Chưa hỗ trợ sàn {target.platform}.")
    try:
        return await collector.collect(target)
    except Exception as exc:  # noqa: BLE001 — collection is best-effort by design
        return CollectorResult.failed(f"Lỗi khi thu thập: {exc}")
