"""Seller Autopilot grounding and Ollama Cloud contract tests."""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.core.exceptions import UpstreamUnavailableError
from app.services import autopilot


def test_center_state_requires_real_data_before_analysis() -> None:
    readiness = {"ready": False, "shops": []}
    assert autopilot._derive_center_state(readiness, []) == "no_data"  # noqa: SLF001


def test_center_state_exposes_sync_failure_before_generic_readiness() -> None:
    readiness = {"ready": False, "shops": [{"status": "sync_failed"}]}
    assert autopilot._derive_center_state(readiness, []) == "sync_failed"  # noqa: SLF001


def test_center_state_moves_from_first_analysis_to_monitoring() -> None:
    readiness = {"ready": True, "shops": []}
    assert autopilot._derive_center_state(readiness, []) == "ready_unanalyzed"  # noqa: SLF001
    assert autopilot._derive_center_state(readiness, ["detected"]) == "awaiting_approval"  # noqa: SLF001
    assert autopilot._derive_center_state(readiness, ["applied"]) == "monitoring"  # noqa: SLF001


@pytest.mark.asyncio
async def test_candidates_use_confirmed_workspace_import_only() -> None:
    class _Row:
        payload = {"sku": "SER-01", "name": "Serum thật", "price": 250000, "stock": 2}

    class _Scalars:
        def all(self):
            return [_Row()]

    class _Result:
        def scalars(self):
            return _Scalars()

    class _Db:
        async def execute(self, _statement):  # noqa: ANN001
            return _Result()

    candidates = await autopilot._workspace_candidates(_Db(), 7)  # noqa: SLF001
    assert len(candidates) == 1
    evidence = candidates[0]["evidence"]
    assert evidence["source"] == "confirmed_import"
    assert evidence["product_name"] == "Serum thật"
    assert all("revenue" not in option["impact"] for option in candidates[0]["options"])


def test_concise_keeps_model_copy_within_ui_limit() -> None:
    long_copy = "Rủi ro tồn kho cần xử lý ngay. " + ("Hành động hợp lý. " * 30)
    result = autopilot._concise(long_copy)  # noqa: SLF001

    assert len(result) <= 240
    assert result.endswith(".") or result.endswith("…")


@pytest.mark.asyncio
async def test_ollama_cloud_request_uses_bearer_key_and_real_response(monkeypatch) -> None:
    captured: dict = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            content = json.dumps({"items": [{
                "fingerprint": "inventory:SKU-001",
                "explanation": "Chỉ còn 4 ngày tồn kho; nhập thêm hàng để bảo vệ doanh thu.",
            }]}, ensure_ascii=False)
            return {"message": {"content": content}}

    class _Client:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            captured["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:  # noqa: ANN002
            return None

        async def post(self, path: str, *, json: dict):  # noqa: A002
            captured["path"] = path
            captured["body"] = json
            return _Response()

    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "OLLAMA_API_KEY", "ollama-test-key")
    monkeypatch.setattr(settings, "AUTOPILOT_OLLAMA_URL", "https://ollama.com")
    monkeypatch.setattr(settings, "AUTOPILOT_OLLAMA_MODEL", "gpt-oss:120b")
    monkeypatch.setattr(autopilot.httpx, "AsyncClient", _Client)

    candidate = {
        "fingerprint": "inventory:SKU-001", "title": "Sắp hết hàng",
        "evidence": {"stock": 8, "runway_days": 4},
        "options": [{"id": "restock", "label": "Nhập hàng", "impact": {"days": 30}}],
    }
    explanations, used, model = await autopilot._ollama_explain([candidate])  # noqa: SLF001

    assert used is True
    assert model == "gpt-oss:120b"
    assert explanations["inventory:SKU-001"].startswith("Chỉ còn 4 ngày")
    assert captured["client"]["base_url"] == "https://ollama.com"
    assert captured["client"]["headers"] == {"Authorization": "Bearer ollama-test-key"}
    assert captured["path"] == "/api/chat"
    assert captured["body"]["stream"] is False
    assert captured["body"]["think"] is False
    assert captured["body"]["options"]["num_predict"] == 2000


@pytest.mark.asyncio
async def test_missing_key_returns_explicit_configuration_error(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "OLLAMA_API_KEY", None)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    with pytest.raises(UpstreamUnavailableError) as exc_info:
        await autopilot._ollama_explain([])  # noqa: SLF001

    assert exc_info.value.code == "LLM_NOT_CONFIGURED"
