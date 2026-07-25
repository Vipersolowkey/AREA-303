"""Auto-analysis ("portfolio") services — run the existing scorers over the
store's customers / sessions so the seller gets a ready report instead of
filling forms. Churn / return / regret scan the customer base; journey analyses
pre-built shopping sessions (real data to test, not a manual simulation).
"""

from __future__ import annotations

from typing import Any, cast

from app.schemas.insights import ChurnRequest, RegretRequest, ReturnRequest
from app.schemas.journey import JourneyEvent, JourneyRequest
from app.services import commerce_store as store
from app.services import insights
from app.services import journey as journey_svc


def churn_portfolio() -> dict:
    rows = []
    for c in store.all_customers():
        r = insights.score_churn(ChurnRequest(
            recency_days=c["recency_days"], frequency_orders=c["frequency_orders"],
            sessions_last_month=c["sessions_last_month"], cart_abandon_rate=c["cart_abandon_rate"],
            trend=cast(Any, c["trend"]),
        ))
        rows.append({"id": c["id"], "customer": c["name"], "recency_days": c["recency_days"],
                     **r.model_dump()})
    rows.sort(key=lambda x: x["churn_risk"], reverse=True)
    return {"customers": rows, "total": len(rows),
            "at_risk_count": sum(1 for r in rows if r["risk_band"] == "high")}


def return_portfolio() -> dict:
    rows = []
    for c in store.all_customers():
        r = insights.score_return(ReturnRequest(
            category=cast(Any, c["last_category"]), price_vnd=c["last_order_value_vnd"],
            is_new_customer=c["is_first_purchase"], size_related=c["has_size_variants"],
            discount_pct=20 if c["discount_driven"] else 0, reviews_read=c["reviews_read"],
        ))
        rows.append({"id": c["id"], "customer": c["name"], "product": c["last_product"],
                     "order_value_vnd": c["last_order_value_vnd"], **r.model_dump()})
    rows.sort(key=lambda x: x["return_risk"], reverse=True)
    return {"orders": rows, "total": len(rows),
            "high_risk_count": sum(1 for r in rows if r["risk_band"] == "high")}


def regret_portfolio() -> dict:
    rows = []
    for c in store.all_customers():
        r = insights.score_regret(RegretRequest(
            decision_time_seconds=c["decision_seconds"], revisit_count=c["revisits_before_buy"],
            purchase_hour=c["purchase_hour"], price_vnd=c["last_order_value_vnd"],
            used_discount=c["discount_driven"],
        ))
        rows.append({"id": c["id"], "customer": c["name"], "product": c["last_product"],
                     **r.model_dump()})
    rows.sort(key=lambda x: x["regret_risk"], reverse=True)
    return {"orders": rows, "total": len(rows),
            "high_risk_count": sum(1 for r in rows if r["risk_band"] == "high")}


async def journey_sessions() -> dict:
    out = []
    for s in store.all_sessions():
        res = await journey_svc.analyze_journey(
            JourneyRequest(events=[JourneyEvent(**e) for e in s["events"]]))
        out.append({"id": s["id"], "label": s["label"], "events": s["events"],
                    "analysis": res.model_dump()})
    return {"sessions": out, "total": len(out)}
