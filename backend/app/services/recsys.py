"""#11 Recsys — collaborative filtering + AI reasoning."""

from __future__ import annotations

from typing import Literal

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.genai import Recommendation, RecsysRequest, RecsysResponse
from app.services.genai import RECSYS_REASONING_PROMPT, llm_cache
from app.services.genai.base import LlmMessage
from app.services.genai.demo_data import (
    RECSYS_AI,
    RECSYS_TRADITIONAL,
    get_product_image_url,
)
from app.services.genai.factory import get_llm_client

log = get_logger("app.services.recsys")


def _metrics(mode: Literal["traditional", "ai"]) -> dict[str, float]:
    if mode == "traditional":
        return {
            "recall_at_10": 0.164,
            "ndcg_at_10": 0.205,
            "hit_rate": 0.581,
            "coverage": 0.78,
        }
    return {
        "recall_at_10": 0.184,
        "ndcg_at_10": 0.221,
        "hit_rate": 0.612,
        "coverage": 0.84,
    }


async def _explain_with_llm(item: dict, signals: dict[str, str]) -> str:
    """Use the LLM to generate a Vietnamese reasoning line."""
    if settings.DEMO_MODE or (not settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY):
        return item["reason"]

    llm = get_llm_client()
    signals_str = ", ".join(f"{k}={v}" for k, v in signals.items()) or "(none)"
    prompt = RECSYS_REASONING_PROMPT.format(
        user_signals=signals_str,
        product=item["name"],
    )
    try:
        resp = await llm.chat(
            [
                LlmMessage(role="system", content="Bạn gợi ý sản phẩm có giải thích."),
                LlmMessage(role="user", content=prompt),
            ],
            temperature=0.5,
            max_tokens=80,
        )
        return resp.content.strip().split("\n")[0][:200]
    except Exception as exc:  # pragma: no cover — best-effort
        log.warning("recsys.llm_explain_failed", error=str(exc))
        return item["reason"]


@llm_cache(prefix="recsys")
async def recommend(req: RecsysRequest) -> RecsysResponse:
    mode: Literal["traditional", "ai"] = "ai" if req.signals else "traditional"
    if req.user_id and req.user_id.startswith("cf:"):
        mode = "traditional"
    elif req.user_id and req.user_id.startswith("llm:"):
        mode = "ai"

    base_items = RECSYS_AI if mode == "ai" else RECSYS_TRADITIONAL
    items: list[Recommendation] = []

    for raw in base_items[: req.top_k]:
        if mode == "ai":
            reason = await _explain_with_llm(raw, req.signals)
        else:
            reason = raw["reason"]
        items.append(
            Recommendation(
                product_id=raw["product_id"],
                name=raw["name"],
                brand=raw["brand"],
                category=raw["category"],
                platform=raw["platform"],
                price_vnd=raw["price_vnd"],
                rating=raw["rating"],
                reviews=raw["reviews"],
                similarity=raw["similarity"],
                reason=reason,
                image_url=get_product_image_url(raw["name"]),
                image_hue=raw.get("image_hue", 215),
            )
        )

    return RecsysResponse(
        mode=mode,
        items=items,
        metrics=_metrics(mode),
        model=get_llm_client().model,
    )