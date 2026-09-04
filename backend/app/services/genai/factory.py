"""LLM + RAG client factories.

Tests use a deterministic client. Runtime always uses the configured provider
and reports missing credentials instead of substituting canned output.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.exceptions import UpstreamUnavailableError
from app.services.genai.base import LlmClient
from app.services.genai.rag import BaseRetriever, InMemoryRetriever


@lru_cache(maxsize=1)
def get_llm_client() -> LlmClient:
    if settings.APP_ENV == "test":
        from app.services.genai.mock_client import MockLlmClient

        return MockLlmClient()

    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise UpstreamUnavailableError(
                "Chưa cấu hình GEMINI_API_KEY.", code="LLM_NOT_CONFIGURED"
            )
        from app.services.genai.gemini_client import GeminiClient

        return GeminiClient()
    if provider in {"openai", "ollama"}:
        provider_key = (
            settings.OLLAMA_API_KEY if provider == "ollama" else settings.OPENAI_API_KEY
        )
        if not provider_key:
            raise UpstreamUnavailableError(
                f"Chưa cấu hình API key cho {provider}.", code="LLM_NOT_CONFIGURED"
            )
        from app.services.genai.openai_client import OpenAIClient

        return OpenAIClient()

    raise UpstreamUnavailableError(
        f"LLM provider không được hỗ trợ: {provider}.", code="LLM_PROVIDER_INVALID"
    )


async def close_llm_client() -> None:
    """Close the cached provider transport without instantiating a new one."""
    if get_llm_client.cache_info().currsize == 0:
        return
    client = get_llm_client()
    close = getattr(client, "aclose", None)
    if close is not None:
        await close()
    get_llm_client.cache_clear()


@lru_cache(maxsize=1)
def get_rag() -> BaseRetriever:
    """Return the configured retriever.

    ``memory`` is an explicit local catalog index. ``pinecone`` requires its
    own credentials and never silently changes backend.
    """
    backend = settings.VECTOR_BACKEND.lower()
    if backend == "memory":
        return InMemoryRetriever()
    if backend == "pinecone":
        if not settings.PINECONE_API_KEY:
            raise UpstreamUnavailableError(
                "Chưa cấu hình PINECONE_API_KEY.", code="RAG_NOT_CONFIGURED"
            )
        # Lazily imported so the dep is optional.
        from app.services.genai.pinecone_retriever import PineconeRetriever

        return PineconeRetriever()
    raise UpstreamUnavailableError(
        f"Vector backend chưa được hỗ trợ: {backend}.", code="RAG_PROVIDER_INVALID"
    )
