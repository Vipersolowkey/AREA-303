"""Shared GenAI utilities — LLM clients, RAG, caching, prompts.

Public surface (re-exported from :mod:`app.services.genai`):

* :class:`LlmClient` — async streaming chat interface
* :func:`get_llm_client` — factory keyed off settings.LLM_PROVIDER
* :func:`get_rag` — retrieval helper (Pinecone / FAISS / in-memory)
* :func:`llm_cache` — Redis-backed decorator w/ TTL

The :class:`MockLlmClient` is restricted to ``APP_ENV=test``. Runtime provider
or credential problems are surfaced through the standard API error envelope.
"""

from __future__ import annotations

from app.services.genai.base import (
    ChatChunk,
    LlmClient,
    LlmMessage,
    LlmResponse,
)
from app.services.genai.cache import llm_cache
from app.services.genai.factory import get_llm_client, get_rag
from app.services.genai.prompts import (
    CONTENT_GENERATOR_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    PERSONAL_SHOPPER_SYSTEM,
    RECSYS_REASONING_PROMPT,
    SELLER_COACH_SYSTEM,
)

__all__ = [
    "LlmClient",
    "LlmMessage",
    "LlmResponse",
    "ChatChunk",
    "get_llm_client",
    "get_rag",
    "llm_cache",
    "PERSONAL_SHOPPER_SYSTEM",
    "CONTENT_GENERATOR_PROMPT",
    "RECSYS_REASONING_PROMPT",
    "SELLER_COACH_SYSTEM",
    "INTENT_CLASSIFICATION_PROMPT",
]
