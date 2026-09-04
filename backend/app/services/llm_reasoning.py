"""Shared LLM reasoning helper for the Track-2 intelligence features
(Market / Content-Creator / Product-Knowledge / Decision Intelligence).

These features are numeric at the core (scores, margins, rankings computed by
deterministic heuristics) but benefit from a natural-language *explanation* and
strategic recommendation. Runtime failures are surfaced to the API instead of
being replaced by generated-looking template text.
"""

from __future__ import annotations

import json

from app.core.config import settings
from app.services.genai.base import LlmMessage
from app.services.genai.factory import get_llm_client

# Prepended to every reasoning prompt so answers match the user's language.
_LANG_RULE = (
    "Reply in the SAME language as the input: if the user's text/question is in "
    "Vietnamese, answer in Vietnamese; if it is in English, answer in English. "
    "When the input has no clear language (only numbers/structured data), default "
    "to Vietnamese.\n\n"
)


def llm_ready() -> bool:
    """True when the selected runtime LLM has credentials."""
    provider_keys = {
        "gemini": settings.GEMINI_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "ollama": settings.OLLAMA_API_KEY,
    }
    if settings.APP_ENV == "test":
        return False
    return bool(provider_keys.get(settings.LLM_PROVIDER))


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].lstrip("json").strip()
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start : end + 1] if start != -1 and end != -1 else raw)


async def reason_json(
    system: str,
    user: str,
    *,
    max_tokens: int = 400,
    temperature: float = 0.2,
    label: str = "reason",
) -> dict | None:
    """Ask the configured LLM for a compact JSON object.

    Unit tests return ``None`` so deterministic business-rule tests never call
    an external provider. Runtime configuration and upstream errors propagate.
    """
    if settings.APP_ENV == "test":
        return None
    resp = await get_llm_client().chat(
        [
            LlmMessage(role="system", content=_LANG_RULE + system),
            LlmMessage(role="user", content=user),
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return _parse_json(resp.content)
