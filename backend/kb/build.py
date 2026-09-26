"""Requirement 12.1: assemble a signal's knowledge base (narratives, verified facts,
quotes, statistics) into embedded, retrievable chunks."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from backend.kb.chunking import (
    build_case_summary_text, build_fact_chunk_texts, build_stat_chunk_text,
    new_chunk_id, split_narrative_sentences,
)
from backend.kb.vectorstore import add_chunks_batch, clear_investigation_kb
from backend.llm.anthropic_client import embed_text


def build_kb(
    investigation_id: str,
    drug: str,
    event: str,
    reports: list[dict],
    extractions_by_report: dict[str, dict],
    causality_by_report: dict[str, dict],
    stats: dict,
    embed_fn: Callable[[str], list[float]] = embed_text,
    max_workers: int = 12,
) -> dict:
    """Returns {"chunks_built": int, "embedding_failures": int}. Raises nothing — a failed
    embedding call for one chunk is skipped and counted, never silently fabricated, so the
    chatbot still works over whatever embedded successfully (Requirement 11.2 spirit)."""
    clear_investigation_kb(investigation_id)

    pending: list[dict] = []  # {chunk_id, report_id, chunk_type, text, char_start, char_end, granularity}

    stat_text = build_stat_chunk_text(drug, event, stats)
    pending.append({"chunk_id": new_chunk_id(), "report_id": None, "chunk_type": "stat",
                     "text": stat_text, "char_start": None, "char_end": None, "granularity": "chunk"})

    for report in reports:
        report_id = report["report_id"]
        extraction = extractions_by_report.get(report_id, {})
        causality = causality_by_report.get(report_id, {})

        summary_text = build_case_summary_text(report, extraction, causality)
        pending.append({"chunk_id": new_chunk_id(), "report_id": report_id, "chunk_type": "case_summary",
                         "text": summary_text, "char_start": None, "char_end": None, "granularity": "summary"})

        for sentence, start, end in split_narrative_sentences(report["narrative"]):
            if len(sentence.strip()) < 8:
                continue
            pending.append({"chunk_id": new_chunk_id(), "report_id": report_id, "chunk_type": "narrative",
                             "text": f"[{report_id}] {sentence}", "char_start": start, "char_end": end,
                             "granularity": "chunk"})

        for fc in build_fact_chunk_texts(report, extraction):
            pending.append({"chunk_id": new_chunk_id(), "report_id": fc["report_id"], "chunk_type": "fact",
                             "text": fc["text"], "char_start": fc["char_start"], "char_end": fc["char_end"],
                             "granularity": "chunk"})

    embedding_failures = 0
    to_insert: list[dict] = []

    def embed_one(item: dict):
        try:
            return item, embed_fn(item["text"])
        except Exception:
            return item, None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for item, embedding in pool.map(embed_one, pending):
            if embedding is None:
                embedding_failures += 1
                continue
            to_insert.append({
                "chunk_id": item["chunk_id"], "investigation_id": investigation_id,
                "report_id": item["report_id"], "chunk_type": item["chunk_type"],
                "text": item["text"], "char_start": item["char_start"],
                "char_end": item["char_end"], "granularity": item["granularity"],
                "embedding": embedding,
            })

    # One round trip for all chunks, not one per chunk — matters a lot against a remote
    # Postgres (a ~200-chunk KB build would otherwise be ~200 sequential round trips).
    add_chunks_batch(to_insert)

    return {"chunks_built": len(to_insert), "embedding_failures": embedding_failures}
