"""Pick the collector for a platform.

Collectors are built per call rather than held as module singletons, because the
Shopee one now takes an optional session reader whose lifetime is the collection
run. Construction is trivial; the browser is what's expensive, and that's owned
by the caller.
"""

from __future__ import annotations

from app.services.competitor.base import CollectorResult
from app.services.competitor.lazada import LazadaCollector
from app.services.competitor.session import ShopeeSessionReader
from app.services.competitor.shopee import ShopeeCollector
from app.services.competitor.urls import ParsedCompetitor


async def collect(
    target: ParsedCompetitor, *, sales_reader: ShopeeSessionReader | None = None
) -> CollectorResult:
    """Run the platform's collector. Never raises — a broken marketplace
    endpoint is normal operation here, so it comes back as a failed result."""
    if target.platform == "shopee":
        collector: ShopeeCollector | LazadaCollector = ShopeeCollector(sales_reader)
    elif target.platform == "lazada":
        collector = LazadaCollector()
    else:
        return CollectorResult.failed(f"Chưa hỗ trợ sàn {target.platform}.")
    try:
        return await collector.collect(target)
    except Exception as exc:  # noqa: BLE001 — collection is best-effort by design
        return CollectorResult.failed(f"Lỗi khi thu thập: {exc}")
