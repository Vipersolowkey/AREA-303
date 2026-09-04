"""Moderation trigger for real, buyer-submitted reviews — gates a review
before it's persisted/published (mentor feedback: real user data needs a
filter layer before it hits the DB).

Pure orchestration over the scorers in :mod:`app.services.insights`
(``detect_fake`` / ``analyze_sentiment`` — #05 / #01). Runtime LLM errors are
surfaced explicitly, so an unmoderated review is never silently accepted.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.schemas.insights import FakeReviewRequest, SentimentRequest
from app.schemas.reviews import ReviewStatus
from app.services import insights

_MIN_WORDS = 4


class ModerationDecision(BaseModel):
    status: ReviewStatus
    reason: str | None
    confidence: float | None


async def moderate(text: str, rating: int, category: str | None) -> ModerationDecision:
    fake, sentiment = await asyncio.gather(
        insights.detect_fake(FakeReviewRequest(text=text, rating=rating, category=category)),
        insights.analyze_sentiment(SentimentRequest(text=text, rating=rating)),
    )

    if fake.is_fake:
        reason = f"{fake.reason} (độ tin cậy {fake.confidence:.0%})"
        # Model confidence is not proof. Keep suspected reviews out of the
        # storefront, but send every case to the seller queue for a human
        # decision instead of silently auto-rejecting customer content.
        return ModerationDecision(
            status="flagged", reason=reason, confidence=fake.confidence
        )

    if len(text.split()) < _MIN_WORDS:
        return ModerationDecision(
            status="flagged", reason="Nội dung quá ngắn, cần kiểm tra thêm.", confidence=fake.confidence,
        )

    mismatch = (
        (sentiment.sentiment == "negative" and rating >= 4)
        or (sentiment.sentiment == "positive" and rating <= 2)
    )
    if mismatch:
        return ModerationDecision(
            status="flagged",
            reason=f"Số sao ({rating}) không khớp với cảm xúc nội dung ({sentiment.sentiment}).",
            confidence=sentiment.confidence,
        )

    return ModerationDecision(status="published", reason=None, confidence=fake.confidence)
