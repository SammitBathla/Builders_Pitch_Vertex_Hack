"""Requirement 12.1/12.2: build the knowledge base content for a signal — narratives,
verified facts, evidence quotes and statistics — at two granularities."""
from __future__ import annotations

import re
import uuid

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_narrative_sentences(narrative: str) -> list[tuple[str, int, int]]:
    """Returns (sentence_text, char_start, char_end) tuples covering the whole narrative,
    so every chunk keeps exact offsets back into the source text (Requirement 4a.1)."""
    spans = []
    pos = 0
    for sentence in SENTENCE_SPLIT_RE.split(narrative):
        if not sentence:
            continue
        start = narrative.find(sentence, pos)
        if start == -1:
            start = pos
        end = start + len(sentence)
        spans.append((sentence, start, end))
        pos = end
    return spans


def build_case_summary_text(report: dict, extraction: dict, causality: dict) -> str:
    onset = extraction.get("time_to_onset_days")
    onset_txt = f"{onset} days" if onset is not None else "unknown"
    confounders = extraction.get("confounders") or []
    conf_txt = "; ".join(c["text"] for c in confounders) if confounders else "none documented"
    return (
        f"Case {report['report_id']}: {report['age']}-year-old {report['sex']} patient, "
        f"drug {report['drug']}, event {report['event']}, seriousness {report['seriousness']}. "
        f"Time to onset: {onset_txt}. Onset order: {extraction.get('onset_order')}. "
        f"Dechallenge: {extraction.get('dechallenge')}. Rechallenge: {extraction.get('rechallenge')}. "
        f"Confounders: {conf_txt}. "
        f"Causality category: {causality.get('category')} (rule {causality.get('rule_id')})."
    )


def build_fact_chunk_texts(report: dict, extraction: dict) -> list[dict]:
    """One retrievable chunk per verified quoted fact, so specific evidence (not just whole
    narratives) can be retrieved precisely."""
    chunks = []
    field_labels = {
        "time_to_onset_days": "Time to onset", "onset_order": "Onset order",
        "dechallenge": "Dechallenge", "rechallenge": "Rechallenge",
    }
    for fact in extraction.get("facts", []):
        if not fact.get("verified") or not fact.get("quote"):
            continue
        label = field_labels.get(fact["field"], fact["field"].capitalize())
        text = f"[{report['report_id']}] {label} ({fact['value']}): \"{fact['quote']}\""
        chunks.append({
            "text": text, "report_id": report["report_id"], "chunk_type": "fact",
            "char_start": fact.get("char_start"), "char_end": fact.get("char_end"),
        })
    return chunks


def build_stat_chunk_text(drug: str, event: str, stats: dict) -> str:
    return (
        f"Signal statistics for {drug} / {event}: case count (a) = {stats['a']}, "
        f"PRR = {stats['prr']:.2f}" if stats.get("prr") is not None else
        f"Signal statistics for {drug} / {event}: case count (a) = {stats['a']}"
    ) + (
        f", ROR = {stats['ror']:.2f} (95% CI {stats['ror_ci_low']:.2f}-{stats['ror_ci_high']:.2f})"
        if stats.get("ror") is not None else ""
    ) + (
        f", chi-square = {stats['chi_square']:.2f}. " if stats.get("chi_square") is not None else ". "
    ) + (
        "This pair meets the Evans disproportionality signal criteria." if stats.get("is_signal")
        else "This pair does NOT meet the Evans disproportionality signal criteria."
    )


def new_chunk_id() -> str:
    return uuid.uuid4().hex
