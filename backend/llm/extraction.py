"""Requirement 3 + 4: per-case fact extraction pipeline with both guardrail levels wired in.

Level 1 (prompt) guardrails live in prompts.py. Level 2 (system) guardrails — schema
validation and verbatim-quote verification — happen here, deterministically, after every
model call, and are never skippable by prompt instructions alone (Requirement 4.3).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from backend.cache.extraction_cache import cache_key, get_cached, put_cached
from backend.config import get_settings
from backend.guardrails.verify import verify_quote
from backend.llm.bedrock_client import BedrockUnavailableError, converse_with_tool
from backend.llm.prompts import (
    EXTRACTION_INPUT_SCHEMA, EXTRACTION_PROMPT_VERSION, EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_TOOL_DESCRIPTION, EXTRACTION_TOOL_NAME, build_extraction_user_message,
)
from backend.llm.schema import ExtractionSchemaError, validate_extraction


@dataclass
class QuotedFact:
    field: str
    value: str | int | None
    quote: str | None
    verified: bool
    char_start: int | None
    char_end: int | None


@dataclass
class ExtractionRecord:
    report_id: str
    model_id: str | None
    prompt_version: str
    schema_valid: bool
    extraction_failed: bool
    failure_reason: str | None
    time_to_onset_days: int | None
    onset_order: str
    dechallenge: str
    rechallenge: str
    confounders: list[dict]
    data_gaps: list[str]
    facts: list[dict]  # every quoted fact incl. verification + offsets, for the UI
    quotes_verified: int
    quotes_rejected: int
    cache_hit: bool
    cache_key: str | None
    elapsed_seconds: float = 0.0


def _call_llm_raw(report_id: str, drug: str, event: str, narrative: str) -> dict:
    user_message = build_extraction_user_message(report_id, drug, event, narrative)
    return converse_with_tool(
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        user_message=user_message,
        tool_name=EXTRACTION_TOOL_NAME,
        tool_description=EXTRACTION_TOOL_DESCRIPTION,
        input_schema=EXTRACTION_INPUT_SCHEMA,
    )


def _downgrade_and_verify(narrative: str, parsed) -> tuple[dict, list[dict], int, int]:
    """Applies the Level-2 substring guardrail to every quoted fact. Any fact whose quote
    fails verification is downgraded to 'unknown'/None and flagged unverified
    (Requirement 4.6)."""
    facts: list[dict] = []
    verified_count = 0
    rejected_count = 0

    def handle(field_name: str, value, quote: str | None, unknown_value):
        nonlocal verified_count, rejected_count
        if value is None or value == unknown_value or quote is None:
            facts.append({"field": field_name, "value": value, "quote": None, "verified": None,
                          "char_start": None, "char_end": None})
            return value
        v = verify_quote(narrative, quote)
        if v.verified:
            verified_count += 1
            facts.append({"field": field_name, "value": value, "quote": quote, "verified": True,
                          "char_start": v.char_start, "char_end": v.char_end})
            return value
        rejected_count += 1
        facts.append({"field": field_name, "value": unknown_value, "quote": quote, "verified": False,
                      "char_start": None, "char_end": None})
        return unknown_value

    final_onset_days = handle("time_to_onset_days", parsed.time_to_onset_days,
                               parsed.time_to_onset_quote, None)
    final_onset_order = handle("onset_order", parsed.onset_order, parsed.onset_order_quote, "unclear")
    final_dechallenge = handle("dechallenge", parsed.dechallenge, parsed.dechallenge_quote, "unknown")
    final_rechallenge = handle("rechallenge", parsed.rechallenge, parsed.rechallenge_quote, "unknown")

    final_confounders = []
    for c in parsed.confounders:
        v = verify_quote(narrative, c.quote)
        if v.verified:
            verified_count += 1
            final_confounders.append({"text": c.text, "quote": c.quote})
            facts.append({"field": "confounder", "value": c.text, "quote": c.quote, "verified": True,
                          "char_start": v.char_start, "char_end": v.char_end})
        else:
            rejected_count += 1
            facts.append({"field": "confounder", "value": c.text, "quote": c.quote, "verified": False,
                          "char_start": None, "char_end": None})
            # An unverifiable confounder is dropped from the facts used by the rule engine —
            # it is surfaced to the reviewer (via `facts`) but not trusted.

    downgraded = {
        "time_to_onset_days": final_onset_days,
        "onset_order": final_onset_order,
        "dechallenge": final_dechallenge,
        "rechallenge": final_rechallenge,
        "confounders": final_confounders,
        "data_gaps": list(parsed.data_gaps),
    }
    return downgraded, facts, verified_count, rejected_count


def extract_one(report: dict, prompt_version: str = EXTRACTION_PROMPT_VERSION) -> ExtractionRecord:
    settings = get_settings()
    narrative = report["narrative"]
    report_id = report["report_id"]
    key = cache_key(settings.bedrock_model_id, prompt_version, narrative)

    start = time.monotonic()
    cached = get_cached(key)
    cache_hit = cached is not None

    if not cache_hit:
        try:
            raw = _call_llm_raw(report_id, report["drug"], report["event"], narrative)
        except BedrockUnavailableError as e:
            elapsed = time.monotonic() - start
            return ExtractionRecord(
                report_id=report_id, model_id=settings.bedrock_model_id, prompt_version=prompt_version,
                schema_valid=False, extraction_failed=True, failure_reason=str(e),
                time_to_onset_days=None, onset_order="unclear", dechallenge="unknown",
                rechallenge="unknown", confounders=[], data_gaps=[], facts=[],
                quotes_verified=0, quotes_rejected=0, cache_hit=False, cache_key=key,
                elapsed_seconds=elapsed,
            )
    else:
        raw = cached

    try:
        parsed = validate_extraction(raw)
    except ExtractionSchemaError as e:
        elapsed = time.monotonic() - start
        return ExtractionRecord(
            report_id=report_id, model_id=settings.bedrock_model_id, prompt_version=prompt_version,
            schema_valid=False, extraction_failed=True, failure_reason=str(e),
            time_to_onset_days=None, onset_order="unclear", dechallenge="unknown",
            rechallenge="unknown", confounders=[], data_gaps=[], facts=[],
            quotes_verified=0, quotes_rejected=0, cache_hit=cache_hit, cache_key=key,
            elapsed_seconds=elapsed,
        )

    if not cache_hit:
        put_cached(key, settings.bedrock_model_id, prompt_version, raw)

    downgraded, facts, verified, rejected = _downgrade_and_verify(narrative, parsed)
    elapsed = time.monotonic() - start

    return ExtractionRecord(
        report_id=report_id, model_id=settings.bedrock_model_id, prompt_version=prompt_version,
        schema_valid=True, extraction_failed=False, failure_reason=None,
        time_to_onset_days=downgraded["time_to_onset_days"], onset_order=downgraded["onset_order"],
        dechallenge=downgraded["dechallenge"], rechallenge=downgraded["rechallenge"],
        confounders=downgraded["confounders"], data_gaps=downgraded["data_gaps"], facts=facts,
        quotes_verified=verified, quotes_rejected=rejected, cache_hit=cache_hit, cache_key=key,
        elapsed_seconds=elapsed,
    )


def extract_many(reports: list[dict], max_workers: int = 12,
                  prompt_version: str = EXTRACTION_PROMPT_VERSION) -> list[ExtractionRecord]:
    """Requirement 3.5: concurrent extraction so ~40 cases complete in well under 60s."""
    results: dict[str, ExtractionRecord] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(extract_one, r, prompt_version): r["report_id"] for r in reports}
        for fut in as_completed(futures):
            report_id = futures[fut]
            results[report_id] = fut.result()
    return [results[r["report_id"]] for r in reports]
