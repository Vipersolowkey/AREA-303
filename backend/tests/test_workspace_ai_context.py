from types import SimpleNamespace

import pytest

from app.services import commerce_store, copilot


@pytest.mark.asyncio
async def test_copilot_receives_workspace_business_profile(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        async def chat_tools(self, messages, tools, max_tokens):  # noqa: ANN001, ANN201
            captured["messages"] = messages
            return {"content": "Đã hiểu đúng shop thời trang.", "tool_calls": []}

    monkeypatch.setattr(copilot, "get_llm_client", lambda: FakeClient())
    workspace = SimpleNamespace(
        name="Mây Outfit",
        industry="fashion",
        description="Áo thun và áo khoác unisex",
        target_customer="Nam nữ 18-28 tuổi",
        brand_voice="Thân thiện như stylist",
    )

    result = await copilot.agent_ask("Shop tôi bán gì?", SimpleNamespace(), workspace=workspace)

    prompt = captured["messages"][0]["content"]
    assert "Mây Outfit" in prompt
    assert "Áo thun và áo khoác unisex" in prompt
    assert "Mỹ phẩm" not in prompt
    assert result.answer == "Đã hiểu đúng shop thời trang."


def test_sample_catalog_is_one_industry() -> None:
    assert commerce_store.categories() == ["Thời trang", "Phụ kiện"]
    assert all(
        product["category"] in commerce_store.categories()
        for product in commerce_store.all_products()
    )
