"""Requirement 7: AI-drafted investigation summary, generated from structured facts/stats/
recommendation (never from free reasoning), with every cited case ID verified to exist."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from backend.guardrails.verify import verify_case_ids
from backend.llm.anthropic_client import converse_text
from backend.llm.errors import LLMUnavailableError
from backend.llm.prompts import SUMMARY_PROMPT_VERSION, SUMMARY_SYSTEM_PROMPT, build_summary_user_message

CASE_ID_RE = re.compile(r"\bRPT-\d+\b")

LABEL = "AI draft – requires human approval"


@dataclass
class SummaryDraftResult:
    draft_text: str
    cited_case_ids: list[str]
    invalid_case_ids: list[str]
    model_id: str | None
    prompt_version: str
    error: str | None = None


def build_summary_context(
    drug: str, event: str, stats: dict, recommendation: dict, cases: list[dict],
) -> dict:
    """`cases` is a light-weight list of {report_id, causality_category, key facts} — never
    raw narratives, so the model drafts from structured facts, not free reasoning
    (Requirement 7.1)."""
    return {
        "drug": drug, "event": event, "statistics": stats, "recommendation": recommendation,
        "cases": cases, "valid_case_ids": [c["report_id"] for c in cases],
    }


def generate_summary_draft(
    drug: str, event: str, stats: dict, recommendation: dict, cases: list[dict],
    model_id: str,
    chat_fn: Callable[..., str] = converse_text,
) -> SummaryDraftResult:
    context = build_summary_context(drug, event, stats, recommendation, cases)
    valid_ids = {c["report_id"] for c in cases}

    try:
        text = chat_fn(
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            user_message=build_summary_user_message(context),
            model_id=model_id,
        )
    except LLMUnavailableError as e:
        return SummaryDraftResult("", [], [], model_id, SUMMARY_PROMPT_VERSION, error=str(e))

    cited = sorted(set(CASE_ID_RE.findall(text)))
    valid_cited, invalid_cited = verify_case_ids(cited, valid_ids)

    labelled = f"**{LABEL}**\n\n{text}"
    if invalid_cited:
        labelled += (
            "\n\n---\n_System guardrail notice: the following cited case IDs do not exist "
            f"in this signal and could not be verified: {', '.join(invalid_cited)}._"
        )

    return SummaryDraftResult(
        draft_text=labelled, cited_case_ids=valid_cited, invalid_case_ids=invalid_cited,
        model_id=model_id, prompt_version=SUMMARY_PROMPT_VERSION,
    )
