"""Seller Autopilot: grounded detection, real Ollama explanation and approval."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    UpstreamUnavailableError,
    ValidationError,
)
from app.models.autopilot import AutopilotAuditEvent, AutopilotOpportunity
from app.models.onboarding_data import WorkspaceDataRecord
from app.services import commerce_store as store
from app.services import onboarding_data


def _candidates() -> list[dict]:
    products = store.all_products()
    low = sorted(
        (p for p in products if p["stock_status"] in {"low", "out"}),
        key=lambda p: p["stock"] / max(p["daily_sales"], 0.1),
    )[0]
    runway = round(low["stock"] / max(low["daily_sales"], 0.1), 1)
    lost = round(low["daily_sales"] * low["price_vnd"] * 14)

    if low["stock_status"] == "out":
        inventory_title = f"{low['name']} đã hết hàng"
        inventory_baseline = (
            "Tồn kho đã về 0. Ưu tiên bổ sung hàng hoặc tạm dừng khuyến mãi; "
            "không tăng giá một sản phẩm hiện không thể bán."
        )
        inventory_options = [
            {
                "id": "restock",
                "label": "Tạo nhiệm vụ nhập thêm hàng",
                "risk": "low",
                "impact": {
                    "revenue_protected_vnd": lost,
                    "runway_days": runway + 30,
                },
            },
            {
                "id": "pause-campaigns",
                "label": "Tạm dừng khuyến mãi và quảng cáo",
                "risk": "low",
                "impact": {
                    "wasted_spend_avoided_vnd": round(lost * 0.08),
                    "campaigns_to_review": 1,
                },
            },
        ]
    else:
        inventory_title = f"{low['name']} có nguy cơ hết hàng"
        inventory_baseline = (
            f"Tồn kho chỉ đủ khoảng {runway} ngày; nếu không xử lý, doanh thu "
            "14 ngày có thể bị ảnh hưởng."
        )
        inventory_options = [
            {
                "id": "restock",
                "label": "Tạo nhiệm vụ nhập thêm hàng",
                "risk": "low",
                "impact": {
                    "revenue_protected_vnd": lost,
                    "runway_days": runway + 30,
                },
            },
            {
                "id": "raise-price-5",
                "label": "Lập bản nháp tăng giá 5%",
                "risk": "medium",
                "impact": {
                    "revenue_protected_vnd": round(lost * 0.55),
                    "runway_days": round(runway * 1.18, 1),
                },
            },
            {
                "id": "slow-campaign",
                "label": "Lập nhiệm vụ giảm campaign 20%",
                "risk": "medium",
                "impact": {
                    "revenue_protected_vnd": round(lost * 0.4),
                    "runway_days": round(runway * 1.25, 1),
                },
            },
        ]

    negatives = sum(
        r["rating"] <= 3
        for p in products
        for r in p["reviews_list"]
        if r["days_ago"] <= 30
    )
    at_risk = [
        c for c in store.all_customers()
        if c["recency_days"] >= 60 or c["cart_abandon_rate"] >= 0.7
    ]
    risk_ltv = sum(c.get("lifetime_value_vnd", 0) for c in at_risk)
    return [
        {
            "fingerprint": f"inventory:v2:{low['id']}:{low['stock_status']}", "kind": "inventory",
            "severity": "critical" if runway <= 7 else "warning",
            "title": inventory_title,
            "evidence": {"product_id": low["id"], "product_name": low["name"],
                         "stock": low["stock"], "daily_sales": low["daily_sales"],
                         "runway_days": runway, "revenue_at_risk_vnd": lost},
            "baseline_explanation": inventory_baseline,
            "options": inventory_options,
        },
        {
            "fingerprint": "reviews:negative-30d:v2", "kind": "reviews", "severity": "warning",
            "title": f"{negatives} review thấp cần xử lý",
            "evidence": {"negative_reviews_30d": negatives, "products_reviewed": len(products)},
            "baseline_explanation": f"Có {negatives} đánh giá từ 3 sao trở xuống trong 30 ngày; nên xử lý chủ đề lặp lại trước khi ảnh hưởng chuyển đổi.",
            "options": [
                {"id": "review-triage", "label": "Tạo hàng đợi phân loại review", "risk": "low",
                 "impact": {"reviews_prioritized": negatives, "response_sla_hours": 24}},
                {"id": "listing-fix", "label": "Tạo checklist sửa listing", "risk": "low",
                 "impact": {"reviews_prioritized": negatives, "response_sla_hours": 48}},
            ],
        },
        {
            "fingerprint": "customers:winback:v2", "kind": "customer_risk", "severity": "info",
            "title": f"{len(at_risk)} khách nên được win-back",
            "evidence": {"customers_at_risk": len(at_risk), "ltv_at_risk_vnd": risk_ltv},
            "baseline_explanation": f"Nhóm {len(at_risk)} khách có recency cao hoặc bỏ giỏ nhiều đang mang {risk_ltv:,}₫ LTV lịch sử.",
            "options": [
                {"id": "voucher-draft", "label": "Lập voucher 8% chờ duyệt", "risk": "medium",
                 "impact": {"customers_targeted": len(at_risk), "expected_reactivation_pct": 12}},
                {"id": "winback-segment", "label": "Tạo phân khúc win-back", "risk": "low",
                 "impact": {"customers_targeted": len(at_risk), "expected_reactivation_pct": 8}},
            ],
        },
    ]


async def _ollama_explain(candidates: list[dict]) -> tuple[dict[str, str], bool, str]:
    model = settings.AUTOPILOT_OLLAMA_MODEL
    api_key = settings.OLLAMA_API_KEY
    if settings.APP_ENV == "test":
        return {}, False, model
    if not api_key:
        raise UpstreamUnavailableError(
            "Chưa cấu hình OLLAMA_API_KEY cho Seller Autopilot.",
            code="LLM_NOT_CONFIGURED",
        )
    evidence = [
        {"fingerprint": c["fingerprint"], "title": c["title"], "evidence": c["evidence"],
         "options": [{"id": o["id"], "label": o["label"], "impact": o["impact"]} for o in c["options"]]}
        for c in candidates
    ]
    prompt = (
        "Bạn là cố vấn vận hành TMĐT cho seller Việt Nam. Chỉ dùng số trong evidence, "
        "không bịa dữ kiện. Với mỗi item, viết explanation thuyết phục nhưng tối đa 2 câu "
        "và 240 ký tự, nêu rủi ro rồi giải thích đúng phương án đầu tiên trong options "
        "(đó là hành động được đề xuất). Trả JSON đúng dạng "
        '{"items":[{"fingerprint":"...","explanation":"..."}]}.\nDATA=' +
        json.dumps(evidence, ensure_ascii=False)
    )
    try:
        async with httpx.AsyncClient(
            base_url=settings.AUTOPILOT_OLLAMA_URL.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(settings.AUTOPILOT_LLM_TIMEOUT_SECONDS, connect=3),
        ) as client:
            response = await client.post("/api/chat", json={
                "model": model,
                "messages": [{"role": "system", "content": "Output valid JSON only."},
                             {"role": "user", "content": prompt}],
                "format": "json", "stream": False, "think": False,
                # gpt-oss accounts for hidden reasoning inside num_predict even
                # with think disabled. A small cap can return HTTP 200 with an
                # empty/truncated content field, so leave enough room for all
                # three concise explanations.
                "options": {"temperature": 0.15, "num_predict": 2000},
            })
            response.raise_for_status()
            parsed = json.loads(response.json()["message"]["content"])
            items = parsed.get("items", [])
            result = {
                str(item["fingerprint"]): _concise(str(item["explanation"]))
                for item in items if item.get("fingerprint") and item.get("explanation")
            }
            expected = {item["fingerprint"] for item in candidates}
            if set(result) != expected:
                raise ValueError("Ollama response is missing opportunity explanations")
            return result, bool(result), model
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise UpstreamUnavailableError(
            "Không thể lấy giải thích từ Ollama.", code="LLM_UPSTREAM_ERROR"
        ) from exc


def _payload_int(value: object, default: int = 0) -> int:
    """payload is JSON (dict[str, object]); coerce a field to int defensively."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default


def _concise(value: str, limit: int = 240) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    sentence_end = text.rfind(". ", 0, limit - 1)
    if sentence_end >= 80:
        return text[: sentence_end + 1]
    return text[: limit - 1].rstrip(" ,;:") + "…"


async def _workspace_candidates(db: AsyncSession, workspace_id: int) -> list[dict]:
    """Derive operational work only from this workspace's confirmed import.

    Imports currently guarantee product name, SKU, price and stock.  They do
    not invent velocity, reviews, customers or campaign spend, so this helper
    deliberately limits its advice to inventory facts actually available.
    """
    result = await db.execute(
        select(WorkspaceDataRecord).where(
            WorkspaceDataRecord.workspace_id == workspace_id,
            WorkspaceDataRecord.dataset_type == "products",
        )
    )
    records = list(result.scalars().all())
    products = [
        {
            **row.payload,
            "_source_record_id": getattr(row, "id", None),
            "_source_updated_at": (
                row.updated_at.isoformat() if getattr(row, "updated_at", None) else None
            ),
        }
        for row in records
    ]
    low = sorted(
        (product for product in products if _payload_int(product.get("stock")) <= 5),
        key=lambda product: _payload_int(product.get("stock")),
    )
    if not low:
        return [
            {
                "fingerprint": f"inventory:imported-catalogue:{len(products)}",
                "kind": "inventory",
                "severity": "info",
                "title": f"Đã kiểm tra tồn kho của {len(products)} sản phẩm",
                "evidence": {"source": "confirmed_import", "products_checked": len(products), "low_stock_threshold": 5},
                "baseline_explanation": "Không có sản phẩm nào trong file đã xác nhận có tồn kho từ 5 trở xuống.",
                "options": [],
            }
        ]
    candidates: list[dict] = []
    for product in low:
        sku = str(product.get("sku", ""))
        name = str(product.get("name", sku))
        stock = _payload_int(product.get("stock"))
        candidates.append(
            {
                "fingerprint": f"inventory:imported:{sku}:{stock}",
                "kind": "inventory",
                "severity": "critical" if stock == 0 else "warning",
                "title": f"{name} còn {stock} sản phẩm trong kho",
                "evidence": {
                    "source": "confirmed_import",
                    "source_record_id": product.get("_source_record_id"),
                    "source_updated_at": product.get("_source_updated_at"),
                    "sku": sku, "product_name": name,
                    "stock": stock, "current_price_vnd": _payload_int(product.get("price")),
                },
                "baseline_explanation": "Cảnh báo dựa trên tồn kho trong file đã xác nhận; chưa ước tính doanh thu hay tốc độ bán vì bạn chưa nạp lịch sử đơn hàng.",
                "options": [
                    {"id": "review-restock", "label": "Tạo việc kiểm tra và nhập thêm hàng", "risk": "low", "impact": {"sku": sku, "stock_before": stock}},
                    {"id": "review-listing", "label": "Kiểm tra listing và tạm dừng khuyến mãi nếu cần", "risk": "low", "impact": {"sku": sku, "stock_before": stock}},
                ],
            }
        )
    return candidates


def serialize(row: AutopilotOpportunity) -> dict:
    selected = next(
        (item for item in row.options if item.get("id") == row.selected_option_id), None
    )
    execution = None
    monitoring = None
    if row.status == "applied" and selected:
        execution = {
            "action": selected.get("label"),
            "target": "internal_workflow",
            "status": "draft_created",
            "message": "Đã tạo workflow nội bộ; chưa gửi thay đổi sang nền tảng bán hàng.",
            "executed_at": row.applied_at,
        }
        monitoring = {
            "status": "waiting_for_new_data",
            "before": selected.get("impact", {}),
            "after": None,
            "message": "Cần một lần đồng bộ mới để so sánh KPI trước và sau.",
        }
    return {
        "id": row.id, "workspace_id": row.workspace_id, "kind": row.kind,
        "severity": row.severity, "status": row.status, "title": row.title,
        "explanation": row.explanation, "evidence": row.evidence,
        "options": row.options, "model": row.model_name, "llm_used": row.llm_used,
        "provider": "ollama_cloud" if row.llm_used else "test_rules",
        "selected_option_id": row.selected_option_id,
        "created_at": row.created_at, "updated_at": row.updated_at,
        "applied_at": row.applied_at,
        "problem": row.title,
        "impact_level": row.severity,
        "confidence": {
            "score": 0.95 if row.evidence.get("source") in {"confirmed_import", "seeded_admin_demo"} else 0.7,
            "basis": (
                "Dữ liệu import đã xác nhận"
                if row.evidence.get("source") == "confirmed_import"
                else "Bộ dữ liệu mẫu của tài khoản admin"
                if row.evidence.get("source") == "seeded_admin_demo"
                else "Rule vận hành"
            ),
        },
        "data_updated_at": row.evidence.get("source_updated_at"),
        "execution": execution,
        "monitoring": monitoring,
    }


def _derive_center_state(readiness: dict[str, object], opportunity_statuses: list[str]) -> str:
    shops = readiness.get("shops") or []
    shop_statuses = {str(shop.get("status", "")).lower() for shop in shops if isinstance(shop, dict)}
    if shop_statuses & {"failed", "error", "sync_failed"}:
        return "sync_failed"
    if shop_statuses & {"pending", "connecting", "authorizing", "syncing"}:
        return "syncing"
    if not readiness.get("ready"):
        return "no_data"
    if not opportunity_statuses:
        return "ready_unanalyzed"
    if any(status in {"detected", "simulated"} for status in opportunity_statuses):
        return "awaiting_approval"
    if any(status == "applied" for status in opportunity_statuses):
        return "monitoring"
    return "analyzed"


def _seed_fingerprints() -> set[str]:
    return {candidate["fingerprint"] for candidate in _candidates()}


async def center_state(
    db: AsyncSession, workspace_id: int, *, use_seed_data: bool = False
) -> dict:
    data = (
        {
            "ready": True,
            "total_records": len(store.all_products()) + len(store.all_demo_orders()),
            "manual_records": 0,
            "marketplace_records": 0,
            "shops": [],
            "source": "seeded_admin_demo",
        }
        if use_seed_data
        else await onboarding_data.readiness(db, workspace_id)
    )
    if not data["ready"]:
        return {
            "state": _derive_center_state(data, []),
            "demo_mode": use_seed_data,
            "data": data,
            "latest_data_at": None,
            "sync": {"completed_sources": 0, "total_sources": len(data.get("shops") or [])},
            "decisions": {"total": 0, "awaiting_approval": 0, "approved": 0, "rejected": 0},
        }
    imported_updated_at = await db.scalar(
        select(func.max(WorkspaceDataRecord.updated_at)).where(
            WorkspaceDataRecord.workspace_id == workspace_id
        )
    )
    result = await db.execute(
        select(AutopilotOpportunity).where(AutopilotOpportunity.workspace_id == workspace_id)
    )
    rows = list(result.scalars().all())
    if use_seed_data:
        fingerprints = _seed_fingerprints()
        rows = [row for row in rows if row.fingerprint in fingerprints]
    shops = data.get("shops") or []
    synced = sum(
        str(shop.get("status", "")).lower() in {"active", "connected", "synced"}
        for shop in shops if isinstance(shop, dict)
    )
    timestamps = [
        shop.get("last_synced_at") for shop in shops
        if isinstance(shop, dict) and shop.get("last_synced_at")
    ]
    if imported_updated_at:
        timestamps.append(imported_updated_at.isoformat())
    timestamps.extend(
        row.evidence.get("source_updated_at") for row in rows
        if row.evidence.get("source_updated_at")
    )
    statuses = [row.status for row in rows]
    return {
        "state": _derive_center_state(data, statuses),
        "demo_mode": use_seed_data,
        "data": data,
        "latest_data_at": max(timestamps) if timestamps else None,
        "sync": {"completed_sources": synced, "total_sources": len(shops)},
        "decisions": {
            "total": len(rows),
            "awaiting_approval": sum(status in {"detected", "simulated"} for status in statuses),
            "approved": sum(status == "applied" for status in statuses),
            "rejected": sum(status == "rejected" for status in statuses),
        },
    }


async def refresh(
    db: AsyncSession, *, workspace_id: int, actor_user_id: int,
    use_seed_data: bool = False,
) -> list[dict]:
    candidates = _candidates() if use_seed_data else await _workspace_candidates(db, workspace_id)
    if use_seed_data:
        snapshot_at = datetime.now(UTC).isoformat()
        for candidate in candidates:
            candidate["evidence"]["source"] = "seeded_admin_demo"
            candidate["evidence"]["source_updated_at"] = snapshot_at
    explanations, llm_used, model = await _ollama_explain(candidates)
    existing = await db.execute(select(AutopilotOpportunity).where(
        AutopilotOpportunity.workspace_id == workspace_id
    ))
    by_fingerprint = {row.fingerprint: row for row in existing.scalars()}
    output = []
    for candidate in candidates:
        row = by_fingerprint.get(candidate["fingerprint"])
        if row is None:
            row = AutopilotOpportunity(workspace_id=workspace_id, fingerprint=candidate["fingerprint"])
            db.add(row)
        if row.status not in {"applied", "rejected"}:
            row.kind = candidate["kind"]
            row.severity = candidate["severity"]
            row.status = "detected"
            row.title = candidate["title"]
            row.explanation = explanations.get(
                candidate["fingerprint"], candidate["baseline_explanation"]
            )
            row.evidence = candidate["evidence"]
            row.options = candidate["options"]
            row.model_name = model
            row.llm_used = llm_used and candidate["fingerprint"] in explanations
        output.append(row)
    await db.commit()
    for row in output:
        await db.refresh(row)
    return [serialize(row) for row in output]


async def reset_demo(db: AsyncSession, *, workspace_id: int, actor_user_id: int) -> list[dict]:
    """Rebuild the seeded admin walkthrough without touching seller workspace data."""
    fingerprints = _seed_fingerprints()
    result = await db.execute(select(AutopilotOpportunity).where(
        AutopilotOpportunity.workspace_id == workspace_id,
        AutopilotOpportunity.fingerprint.in_(fingerprints),
    ))
    for row in result.scalars():
        row.status = "detected"
        row.selected_option_id = None
        row.approved_by = None
        row.applied_at = None
    await db.commit()
    return await refresh(
        db,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        use_seed_data=True,
    )


async def list_opportunities(
    db: AsyncSession, workspace_id: int, *, use_seed_data: bool = False
) -> list[dict]:
    # Audit rows are retained, but stale recommendations must not be shown
    # before the current workspace has confirmed source data.
    if not use_seed_data and not (await onboarding_data.readiness(db, workspace_id))["ready"]:
        return []
    result = await db.execute(select(AutopilotOpportunity).where(
        AutopilotOpportunity.workspace_id == workspace_id
    ).order_by(AutopilotOpportunity.created_at.desc()))
    rows = list(result.scalars())
    if use_seed_data:
        fingerprints = _seed_fingerprints()
        rows = [row for row in rows if row.fingerprint in fingerprints]
    return [serialize(row) for row in rows]


async def _get(db: AsyncSession, opportunity_id: int, workspace_id: int) -> AutopilotOpportunity:
    result = await db.execute(select(AutopilotOpportunity).where(
        AutopilotOpportunity.id == opportunity_id,
        AutopilotOpportunity.workspace_id == workspace_id,
    ))
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Không tìm thấy opportunity.")
    return row


def _option(row: AutopilotOpportunity, option_id: str) -> dict:
    option = next((item for item in row.options if item["id"] == option_id), None)
    if option is None:
        raise ValidationError("Phương án không thuộc opportunity này.")
    return option


async def simulate(db: AsyncSession, *, opportunity_id: int, workspace_id: int,
                   actor_user_id: int, option_id: str) -> dict:
    row = await _get(db, opportunity_id, workspace_id)
    if row.status in {"applied", "rejected"}:
        raise ConflictError("Opportunity đã kết thúc, không thể mô phỏng lại.")
    option = _option(row, option_id)
    row.status = "simulated"
    row.selected_option_id = option_id
    event = AutopilotAuditEvent(opportunity_id=row.id, workspace_id=workspace_id,
        actor_user_id=actor_user_id, event_type="simulated",
        payload={"option_id": option_id, "impact": option["impact"], "assumption": "deterministic demo snapshot"})
    db.add(event)
    await db.commit()
    await db.refresh(row)
    return {"opportunity": serialize(row), "simulation": option["impact"],
            "risk": option["risk"], "disclaimer": "Ước tính kịch bản, chưa phải cam kết doanh thu."}


async def decide(db: AsyncSession, *, opportunity_id: int, workspace_id: int,
                 actor_user_id: int, option_id: str, decision: str, note: str | None) -> dict:
    row = await _get(db, opportunity_id, workspace_id)
    if row.status in {"applied", "rejected"}:
        raise ConflictError("Opportunity đã được quyết định.")
    option = _option(row, option_id)
    now = datetime.now(UTC)
    row.selected_option_id = option_id
    row.approved_by = actor_user_id if decision == "approve" else None
    row.status = "applied" if decision == "approve" else "rejected"
    row.applied_at = now if decision == "approve" else None
    payload = {"option_id": option_id, "option_label": option["label"], "note": note,
               "execution_mode": "workflow_draft", "target": "internal_workflow",
               "delivery_status": "draft_created", "platform_sent": False,
               "impact": option["impact"]}
    db.add(AutopilotAuditEvent(opportunity_id=row.id, workspace_id=workspace_id,
        actor_user_id=actor_user_id, event_type=row.status, payload=payload))
    await db.commit()
    await db.refresh(row)
    return {"opportunity": serialize(row), "execution": payload}


async def audit_log(db: AsyncSession, workspace_id: int) -> list[dict]:
    result = await db.execute(select(AutopilotAuditEvent).where(
        AutopilotAuditEvent.workspace_id == workspace_id
    ).order_by(AutopilotAuditEvent.created_at.desc()).limit(100))
    return [{"id": e.id, "opportunity_id": e.opportunity_id, "actor_user_id": e.actor_user_id,
             "event_type": e.event_type, "payload": e.payload, "created_at": e.created_at}
            for e in result.scalars()]
