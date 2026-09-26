"""Request bodies for the API (response bodies are plain dicts from the service layer —
they're already JSON-ready and documented by the requirements they satisfy)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateInvestigationRequest(BaseModel):
    drug: str
    event: str
    actor: str = "reviewer"


class OverrideRequest(BaseModel):
    category: str
    reason: str = Field(min_length=1)
    actor: str = "reviewer"


class EditSummaryRequest(BaseModel):
    text: str
    actor: str = "reviewer"


class SignOffRequest(BaseModel):
    actor_name: str = Field(min_length=1)
    final_decision: str  # accept_recommendation | override_recommendation
    decision_reason: str | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    actor: str = "reviewer"
