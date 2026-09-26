"""Requirement 12: retrieval-grounded chatbot. Answers only from the current signal's KB,
with every citation independently verified against retrieved context (never trusted on the
model's word alone) before being shown to the reviewer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from backend.kb.vectorstore import retrieve
from backend.llm.bedrock_client import BedrockUnavailableError, converse_text, embed_text
from backend.llm.prompts import CHAT_PROMPT_VERSION, CHAT_SYSTEM_PROMPT, build_chat_user_message

CITATION_RE = re.compile(r"\[([A-Za-z0-9\-]+)\]")
NO_EVIDENCE_MESSAGE = (
    "I don't have supporting evidence for that in this signal's case data. Try rephrasing, "
    "or ask about a specific case ID."
)
RELEVANCE_THRESHOLD = 0.15  # cosine similarity floor below which context is not "sufficiently relevant"


@dataclass
class ChatAnswer:
    answer: str
    citations: list[dict]
    retrieved_chunk_ids: list[str]
    model_id: str | None
    prompt_version: str
    had_sufficient_context: bool
    error: str | None = None


def answer_question(
    investigation_id: str,
    question: str,
    model_id: str,
    embed_fn: Callable[[str], list[float]] = embed_text,
    chat_fn: Callable[..., str] = converse_text,
) -> ChatAnswer:
    try:
        query_embedding = embed_fn(question)
    except BedrockUnavailableError as e:
        return ChatAnswer("", [], [], model_id, CHAT_PROMPT_VERSION, False, error=str(e))

    retrieved = retrieve(investigation_id, query_embedding)
    sufficiently_relevant = bool(retrieved) and max((c["score"] for c in retrieved), default=0.0) >= RELEVANCE_THRESHOLD

    if not sufficiently_relevant:
        # Requirement 12.7: no sufficiently relevant context -> say so, no LLM call needed
        # (and none made — this cannot be talked around by the model).
        return ChatAnswer(NO_EVIDENCE_MESSAGE, [], [c["chunk_id"] for c in retrieved], model_id,
                           CHAT_PROMPT_VERSION, False)

    context_for_prompt = [
        {"chunk_id": c["chunk_id"], "case_id": c.get("report_id"), "text": c["text"]}
        for c in retrieved
    ]

    try:
        raw_answer = chat_fn(
            system_prompt=CHAT_SYSTEM_PROMPT,
            user_message=build_chat_user_message(question, context_for_prompt),
            model_id=model_id,
        )
    except BedrockUnavailableError as e:
        return ChatAnswer("", [], [c["chunk_id"] for c in retrieved], model_id, CHAT_PROMPT_VERSION,
                           True, error=str(e))

    # Level 2 guardrail: every [CASE-ID] citation must correspond to a report_id that was
    # actually part of the retrieved context passed to the model. Anything else is flagged.
    retrieved_report_ids = {c.get("report_id") for c in retrieved if c.get("report_id")}
    best_chunk_by_report: dict[str, dict] = {}
    for c in retrieved:
        rid = c.get("report_id")
        if rid and (rid not in best_chunk_by_report or c["score"] > best_chunk_by_report[rid]["score"]):
            best_chunk_by_report[rid] = c

    citations = []
    cleaned_answer_parts = []
    last_end = 0
    seen = set()
    for m in CITATION_RE.finditer(raw_answer):
        cid = m.group(1)
        if cid in seen:
            continue
        seen.add(cid)
        if cid in retrieved_report_ids:
            chunk = best_chunk_by_report[cid]
            citations.append({
                "case_id": cid, "chunk_id": chunk["chunk_id"], "verified": True,
                "quote": chunk["text"], "char_start": chunk.get("char_start"),
                "char_end": chunk.get("char_end"),
            })
        else:
            citations.append({"case_id": cid, "chunk_id": None, "verified": False,
                               "quote": None, "char_start": None, "char_end": None})

    # Replace unverifiable citation markers inline so the reviewer never sees a false-looking cite.
    def _mark(m: re.Match) -> str:
        cid = m.group(1)
        if cid in retrieved_report_ids:
            return m.group(0)
        return f"[{cid} — unverified citation, removed]"

    final_answer = CITATION_RE.sub(_mark, raw_answer)

    return ChatAnswer(
        answer=final_answer, citations=citations,
        retrieved_chunk_ids=[c["chunk_id"] for c in retrieved], model_id=model_id,
        prompt_version=CHAT_PROMPT_VERSION, had_sufficient_context=True,
    )
