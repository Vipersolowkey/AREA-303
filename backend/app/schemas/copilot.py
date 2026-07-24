"""Seller Copilot — a conversational AI agent over the seller's data.

The copilot routes a natural-language business question to the right existing
analytical feature (product-knowledge / market / creator / decision / journey),
runs it against a demo seller knowledge base, and synthesizes a business answer
with an estimated VND impact. The briefing endpoint scans the whole store and
returns the prioritized actions for today, ranked by revenue impact.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class CopilotAgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


class AgentStep(BaseModel):
    tool: str
    args: dict
    summary: str


class CopilotAgentResponse(BaseModel):
    answer: str
    tools_used: list[str]
    steps: list[AgentStep]
    multi_step: bool


class CopilotResponse(BaseModel):
    answer: str
    skill_used: str
    entity: str | None = None
    impact_vnd: int | None = None
    tool_result: dict


class BriefingAction(BaseModel):
    kind: Literal["restock", "reduce", "reprice", "investigate", "promote"]
    title: str
    product: str
    priority: Literal["high", "medium", "low"]
    impact_vnd: int
    detail: str


class BriefingResponse(BaseModel):
    summary: str
    total_impact_vnd: int
    actions: list[BriefingAction]
