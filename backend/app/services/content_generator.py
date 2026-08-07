"""#09 Content Generator — 3 platform variants + predicted CTR."""

from __future__ import annotations

import re

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.genai import ContentGeneratorRequest, ContentGeneratorResponse, ContentVariant
from app.services.genai import CONTENT_GENERATOR_PROMPT, llm_cache
from app.services.genai.base import LlmMessage
from app.services.genai.demo_data import CONTENT_DEMO_VARIANTS
from app.services.genai.factory import get_llm_client

log = get_logger("app.services.content_generator")

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]",
    flags=re.UNICODE,
)


def _estimate_ctr(platform: str, title: str, body: str) -> float:
    """Cheap heuristic. Replace with a trained model when one is ready.

    Rules (rough, biased toward the demo baselines):
    - TikTok Shop gains the most from emoji + short hook.
    - Shopee rewards concrete shipping/discount mentions.
    - Tiki rewards 'chính hãng' / 'TikiNOW' mentions.
    """
    text = f"{title} {body}".lower()
    score = 0.045  # baseline

    if platform == "Shopee":
        if "free ship" in text or "freeship" in text:
            score += 0.025
        if any(k in text for k in ("chính hãng", "bảo hành")):
            score += 0.010
    elif platform == "Tiki":
        if "chính hãng" in text:
            score += 0.018
        if "tikinow" in text or "giao 2h" in text:
            score += 0.012
        if "đổi trả" in text:
            score += 0.008
    elif platform == "TikTok Shop":
        emoji_count = len(_EMOJI_RE.findall(f"{title} {body}"))
        score += min(0.04, emoji_count * 0.012)
        if len(title) < 50:
            score += 0.020
        if "comment" in text or "voucher" in text:
            score += 0.018
        if "best seller" in text or "🔥" in f"{title} {body}":
            score += 0.008

    # Body length penalty (over 200 chars hurts retention).
    if len(body) > 220:
        score -= 0.008
    return round(min(0.20, max(0.01, score)), 4)


def _rationale(platform: str, title: str, body: str) -> str:
    text = f"{title} {body}".lower()
    if platform == "Shopee":
        if "free ship" in text:
            return "Hero keywords: shipping hook + concrete features — Shopee ưu tiên free-ship."
        return "Tiêu chí Shopee: bullet ngắn + thông số rõ."
    if platform == "Tiki":
        if "tikinow" in text:
            return "Đề cao 'TikiNOW' + 'chính hãng' — phù hợp khách Tiki tìm đảm bảo."
        return "Tiki thiên về 'chính hãng' + 'đổi trả'."
    emoji = len(_EMOJI_RE.findall(f"{title} {body}"))
    if emoji:
        return f"Hook ngắn + {emoji} emoji — TikTok Shop thường thắng trên impulse."
    return "Hook ngắn, gọn — TikTok Shop ưu tiên dưới 50 ký tự."


def _demo_body(platform: str) -> str:
    """The deterministic copy for a platform, used when the LLM returns nothing."""
    for v in CONTENT_DEMO_VARIANTS:
        if v["platform"] == platform:
            return str(v["body"])
    return ""


@llm_cache(prefix="content_generator")
async def generate(req: ContentGeneratorRequest) -> ContentGeneratorResponse:
    if settings.DEMO_MODE or not settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY:
        log.info("content_generator.demo_mode")
        variants = [
            ContentVariant(
                platform=v["platform"],  # type: ignore[arg-type]
                title=v["title"],
                body=v["body"],
                predicted_ctr=v["predicted_ctr"],
                rationale=v["rationale"],
            )
            for v in CONTENT_DEMO_VARIANTS
            if v["platform"] in req.platforms
        ]
        return ContentGeneratorResponse(
            variants=variants,
            model="mock-demo",
            demo_mode=True,
        )

    llm = get_llm_client()
    out: list[ContentVariant] = []

    for platform in req.platforms:
        prompt = CONTENT_GENERATOR_PROMPT.format(
            platform=platform,
            product_name=req.product_name,
            features=req.features,
        )
        messages = [
            LlmMessage(
                role="system",
                content="Bạn là copywriter chuyên nghiệp cho sàn TMĐT Việt Nam.",
            ),
            LlmMessage(role="user", content=prompt),
        ]
        resp = await llm.chat(messages, temperature=0.7, max_tokens=400)
        raw_title, _, raw_body = resp.content.partition("\n")

        final_title = raw_title.strip()[:120] or req.product_name
        final_body = raw_body.strip()[:600]
        if not final_body:
            # A successful call can still return nothing usable — an empty
            # response, or a single line with no body after it. The old
            # `or resp.content[:600]` fallback didn't help: for an empty
            # response it's also empty (shipping a variant with no body), and
            # for a one-liner it just duplicated the title. Fall back to the
            # deterministic copy for this platform instead.
            final_body = _demo_body(platform) or req.features

        out.append(
            ContentVariant(
                platform=platform,  # type: ignore[arg-type]
                title=final_title,
                # Score the copy we're actually returning, not the raw parse —
                # otherwise the predicted CTR describes text nobody sees.
                body=final_body,
                predicted_ctr=_estimate_ctr(platform, final_title, final_body),
                rationale=_rationale(platform, final_title, final_body),
            )
        )

    return ContentGeneratorResponse(
        variants=out,
        model=llm.model,
        demo_mode=False,
    )