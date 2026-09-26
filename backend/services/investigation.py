"""Orchestrates a full investigation run: extraction (Req 3/4) -> causality rules (Req 5)
-> recommendation (Req 6) -> KB build (Req 12) -> audit trail (Req 9), and the human
review actions (override, summary edit, sign-off — Req 8) that mutate it afterward.

This is the only place that writes to the `investigations`/`extractions`/`causality`
tables, so every write path also appends its audit event in the same place.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from backend.audit.trail import append_event
from backend.chatbot.rag import answer_question
from backend.config import get_settings
from backend.db import cursor, dumps, fetchall, fetchone, loads, row_to_dict
from backend.kb.build import build_kb
from backend.llm.extraction import extract_many
from backend.rules.causality import CATEGORIES, CaseFacts, assign_causality
from backend.rules.recommendation import compute_recommendation
from backend.stats.disproportionality import compute_signal_stats, rank_flagged_signals
from backend.summary.draft import generate_summary_draft


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _all_reports() -> list[dict]:
    return [row_to_dict(r) for r in fetchall("SELECT * FROM reports")]


def _reports_for_pair(drug: str, event: str) -> list[dict]:
    rows = fetchall("SELECT * FROM reports WHERE drug=? AND event=?", (drug, event))
    return [row_to_dict(r) for r in rows]


# --- Signals (Requirement 2) ------------------------------------------------------------

def list_flagged_signals() -> list[dict]:
    reports = _all_reports()
    return [s.as_dict() for s in rank_flagged_signals(reports)]


def get_pair_stats(drug: str, event: str) -> dict:
    reports = _all_reports()
    return compute_signal_stats(reports, drug, event).as_dict()


# --- Investigation lifecycle (Requirements 3, 4, 5, 6, 9, 12) ---------------------------

def list_investigations() -> list[dict]:
    rows = fetchall(
        "SELECT investigation_id, drug, event, status, created_at, recommendation_json "
        "FROM investigations ORDER BY created_at DESC"
    )
    out = []
    for r in rows:
        d = row_to_dict(r)
        rec = loads(d.pop("recommendation_json"))
        d["recommendation"] = rec["recommendation"] if rec else None
        out.append(d)
    return out


def create_investigation(drug: str, event: str, actor: str = "system") -> dict:
    reports = _reports_for_pair(drug, event)
    if not reports:
        raise ValueError(f"No reports found for {drug} / {event}")

    all_reports = _all_reports()
    stats = compute_signal_stats(all_reports, drug, event)

    investigation_id = f"INV-{uuid.uuid4().hex[:10]}"
    created_at = _now()
    with cursor() as cur:
        cur.execute(
            "INSERT INTO investigations (investigation_id, drug, event, status, created_at, stats_json) "
            "VALUES (?, ?, ?, 'in_progress', ?, ?)",
            (investigation_id, drug, event, created_at, dumps(stats.as_dict())),
        )
    append_event("investigation_created", {"drug": drug, "event": event, "case_count": len(reports),
                                            "stats": stats.as_dict()},
                 investigation_id=investigation_id, actor=actor)

    t0 = time.monotonic()
    records = extract_many(reports)
    ai_elapsed = time.monotonic() - t0

    extractions_by_report: dict[str, dict] = {}
    causality_by_report: dict[str, dict] = {}

    with cursor() as cur:
        for rec in records:
            cur.execute(
                """INSERT INTO extractions
                    (investigation_id, report_id, model_id, prompt_version, schema_valid,
                     extraction_failed, failure_reason, time_to_onset_days, onset_order,
                     dechallenge, rechallenge, confounders_json, data_gaps_json, facts_json,
                     quotes_verified, quotes_rejected, cache_hit, cache_key, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (investigation_id, rec.report_id, rec.model_id, rec.prompt_version,
                 int(rec.schema_valid), int(rec.extraction_failed), rec.failure_reason,
                 rec.time_to_onset_days, rec.onset_order, rec.dechallenge, rec.rechallenge,
                 dumps(rec.confounders), dumps(rec.data_gaps), dumps(rec.facts),
                 rec.quotes_verified, rec.quotes_rejected, int(rec.cache_hit), rec.cache_key, _now()),
            )
            append_event(
                "extraction",
                {"report_id": rec.report_id, "schema_valid": rec.schema_valid,
                 "extraction_failed": rec.extraction_failed, "failure_reason": rec.failure_reason,
                 "quotes_verified": rec.quotes_verified, "quotes_rejected": rec.quotes_rejected,
                 "cache_hit": rec.cache_hit},
                investigation_id=investigation_id, actor="ai",
                model_id=rec.model_id, prompt_version=rec.prompt_version,
            )

            extractions_by_report[rec.report_id] = {
                "report_id": rec.report_id, "schema_valid": rec.schema_valid,
                "extraction_failed": rec.extraction_failed, "failure_reason": rec.failure_reason,
                "time_to_onset_days": rec.time_to_onset_days, "onset_order": rec.onset_order,
                "dechallenge": rec.dechallenge, "rechallenge": rec.rechallenge,
                "confounders": rec.confounders, "data_gaps": rec.data_gaps, "facts": rec.facts,
                "quotes_verified": rec.quotes_verified, "quotes_rejected": rec.quotes_rejected,
                "cache_hit": rec.cache_hit, "model_id": rec.model_id, "prompt_version": rec.prompt_version,
            }

            if rec.extraction_failed:
                causality_result = None
                category, rule_id, ruleset_version, explanation = (
                    "Unassessable", "R0-extraction-failed", "causality-v1",
                    f"Extraction failed for this case ({rec.failure_reason}); no verified "
                    "facts are available to assess causality.",
                )
            else:
                facts = CaseFacts(
                    time_to_onset_days=rec.time_to_onset_days, onset_order=rec.onset_order,
                    dechallenge=rec.dechallenge, rechallenge=rec.rechallenge,
                    has_confounders=bool(rec.confounders),
                )
                causality_result = assign_causality(facts)
                category, rule_id = causality_result.category, causality_result.rule_id
                ruleset_version, explanation = causality_result.ruleset_version, causality_result.explanation

            cur.execute(
                """INSERT INTO causality
                    (investigation_id, report_id, category, source, rule_id, ruleset_version,
                     explanation, created_at)
                   VALUES (?, ?, ?, 'rule', ?, ?, ?, ?)""",
                (investigation_id, rec.report_id, category, rule_id, ruleset_version, explanation, _now()),
            )
            append_event(
                "rule_evaluation", {"report_id": rec.report_id, "category": category, "rule_id": rule_id},
                investigation_id=investigation_id, actor="rule-engine", rule_version=ruleset_version,
            )
            causality_by_report[rec.report_id] = {
                "category": category, "source": "rule", "rule_id": rule_id,
                "ruleset_version": ruleset_version, "explanation": explanation,
                "overridden_by": None, "override_reason": None,
            }

    rec_result = compute_recommendation(stats.is_signal, [c["category"] for c in causality_by_report.values()])
    with cursor() as cur:
        cur.execute(
            "UPDATE investigations SET recommendation_json=?, ai_processing_seconds=? WHERE investigation_id=?",
            (dumps(_rec_to_dict(rec_result)), ai_elapsed, investigation_id),
        )
    append_event("recommendation_computed", _rec_to_dict(rec_result), investigation_id=investigation_id,
                 actor="rule-engine", rule_version=rec_result.ruleset_version)

    try:
        kb_result = build_kb(investigation_id, drug, event, reports, extractions_by_report,
                              causality_by_report, stats.as_dict())
        append_event("kb_built", kb_result, investigation_id=investigation_id, actor="system")
    except Exception as e:  # KB build failing must never take down the investigation itself
        append_event("kb_build_failed", {"error": str(e)}, investigation_id=investigation_id, actor="system")

    return get_investigation(investigation_id)


def _rec_to_dict(rec_result) -> dict:
    return {
        "recommendation": rec_result.recommendation, "rule_id": rec_result.rule_id,
        "ruleset_version": rec_result.ruleset_version, "thresholds": rec_result.thresholds,
        "explanation": rec_result.explanation, "causality_counts": rec_result.causality_counts,
        "supportive_fraction": rec_result.supportive_fraction,
        "unsupportive_fraction": rec_result.unsupportive_fraction,
        "unassessable_fraction": rec_result.unassessable_fraction,
    }


def get_investigation(investigation_id: str) -> dict:
    inv_row = fetchone("SELECT * FROM investigations WHERE investigation_id=?", (investigation_id,))
    if inv_row is None:
        raise KeyError(investigation_id)
    inv = row_to_dict(inv_row)

    reports_by_id = {
        r["report_id"]: row_to_dict(r)
        for r in fetchall("SELECT * FROM reports WHERE drug=? AND event=?", (inv["drug"], inv["event"]))
    }
    causality_by_report = {
        r["report_id"]: row_to_dict(r)
        for r in fetchall("SELECT * FROM causality WHERE investigation_id=?", (investigation_id,))
    }
    ext_rows = fetchall(
        "SELECT * FROM extractions WHERE investigation_id=? ORDER BY report_id", (investigation_id,)
    )

    cases = []
    for row in ext_rows:
        e = row_to_dict(row)
        report_id = e["report_id"]
        e["confounders"] = loads(e.pop("confounders_json"))
        e["data_gaps"] = loads(e.pop("data_gaps_json"))
        e["facts"] = loads(e.pop("facts_json"))
        e["schema_valid"] = bool(e["schema_valid"])
        e["extraction_failed"] = bool(e["extraction_failed"])
        e["cache_hit"] = bool(e["cache_hit"])
        cases.append({
            "report": reports_by_id.get(report_id, {"report_id": report_id}),
            "extraction": e,
            "causality": causality_by_report.get(report_id),
        })

    return {
        "investigation_id": investigation_id, "drug": inv["drug"], "event": inv["event"],
        "status": inv["status"], "created_at": inv["created_at"],
        "stats": loads(inv["stats_json"]),
        "recommendation": loads(inv["recommendation_json"]) if inv["recommendation_json"] else None,
        "summary_draft": inv["summary_draft"], "summary_final": inv["summary_final"],
        "summary_citation_check": loads(inv["summary_citation_check_json"]) if inv["summary_citation_check_json"] else None,
        "signed_off_at": inv["signed_off_at"], "signed_off_by": inv["signed_off_by"],
        "final_decision": inv["final_decision"], "decision_reason": inv["decision_reason"],
        "ai_processing_seconds": inv["ai_processing_seconds"], "cases": cases,
    }


# --- Human review (Requirement 8) -------------------------------------------------------

def override_case(investigation_id: str, report_id: str, category: str, reason: str, actor: str) -> dict:
    if category not in CATEGORIES:
        raise ValueError(f"Invalid causality category: {category}")
    if not reason or not reason.strip():
        raise ValueError("An override reason is required.")

    existing = fetchone(
        "SELECT * FROM causality WHERE investigation_id=? AND report_id=?", (investigation_id, report_id)
    )
    old_category = existing["category"] if existing else None

    with cursor() as cur:
        cur.execute(
            """UPDATE causality SET category=?, source='override', rule_id=NULL,
                   overridden_by=?, override_reason=?, created_at=?
               WHERE investigation_id=? AND report_id=?""",
            (category, actor, reason, _now(), investigation_id, report_id),
        )
    append_event(
        "override", {"report_id": report_id, "old_category": old_category, "new_category": category,
                      "reason": reason},
        investigation_id=investigation_id, actor=actor,
    )
    _recompute_recommendation(investigation_id)
    return get_investigation(investigation_id)


def _recompute_recommendation(investigation_id: str) -> None:
    inv = fetchone("SELECT stats_json FROM investigations WHERE investigation_id=?", (investigation_id,))
    stats = loads(inv["stats_json"])
    categories = [r["category"] for r in fetchall(
        "SELECT category FROM causality WHERE investigation_id=?", (investigation_id,)
    )]
    rec_result = compute_recommendation(stats["is_signal"], categories)
    with cursor() as cur:
        cur.execute("UPDATE investigations SET recommendation_json=? WHERE investigation_id=?",
                     (dumps(_rec_to_dict(rec_result)), investigation_id))
    append_event("recommendation_computed", _rec_to_dict(rec_result), investigation_id=investigation_id,
                 actor="rule-engine", rule_version=rec_result.ruleset_version)


# --- Summary draft + sign-off (Requirements 7, 8) ---------------------------------------

def generate_summary(investigation_id: str) -> dict:
    inv = get_investigation(investigation_id)
    settings = get_settings()
    cases_light = [
        {
            "report_id": c["report"]["report_id"],
            "causality_category": (c["causality"] or {}).get("category", "Unassessable"),
            "time_to_onset_days": c["extraction"].get("time_to_onset_days"),
            "dechallenge": c["extraction"].get("dechallenge"),
            "rechallenge": c["extraction"].get("rechallenge"),
            "confounders": [x.get("text") for x in (c["extraction"].get("confounders") or [])],
        }
        for c in inv["cases"]
    ]
    result = generate_summary_draft(
        inv["drug"], inv["event"], inv["stats"], inv["recommendation"], cases_light,
        settings.bedrock_model_id,
    )
    with cursor() as cur:
        cur.execute(
            "UPDATE investigations SET summary_draft=?, summary_citation_check_json=? WHERE investigation_id=?",
            (result.draft_text, dumps({"cited": result.cited_case_ids, "invalid": result.invalid_case_ids}),
             investigation_id),
        )
    append_event(
        "summary_drafted",
        {"cited_case_ids": result.cited_case_ids, "invalid_case_ids": result.invalid_case_ids,
         "error": result.error},
        investigation_id=investigation_id, actor="ai", model_id=result.model_id,
        prompt_version=result.prompt_version,
    )
    return get_investigation(investigation_id)


def edit_summary(investigation_id: str, text: str, actor: str) -> dict:
    with cursor() as cur:
        cur.execute("UPDATE investigations SET summary_final=? WHERE investigation_id=?", (text, investigation_id))
    append_event("summary_edited", {"actor": actor, "length": len(text)}, investigation_id=investigation_id, actor=actor)
    return get_investigation(investigation_id)


def sign_off(investigation_id: str, actor_name: str, final_decision: str, decision_reason: str | None) -> dict:
    inv = get_investigation(investigation_id)
    if not (inv["summary_final"] or inv["summary_draft"]):
        raise ValueError("Cannot sign off: no investigation summary has been drafted or written yet.")
    if final_decision not in ("accept_recommendation", "override_recommendation"):
        raise ValueError("final_decision must be 'accept_recommendation' or 'override_recommendation'")
    if final_decision == "override_recommendation" and not (decision_reason and decision_reason.strip()):
        raise ValueError("Overriding the recommendation requires a reason.")
    if not actor_name or not actor_name.strip():
        raise ValueError("Sign-off requires a reviewer name.")

    with cursor() as cur:
        cur.execute(
            """UPDATE investigations SET status='signed_off', signed_off_at=?, signed_off_by=?,
                   final_decision=?, decision_reason=? WHERE investigation_id=?""",
            (_now(), actor_name, final_decision, decision_reason, investigation_id),
        )
    append_event(
        "sign_off", {"actor_name": actor_name, "final_decision": final_decision, "decision_reason": decision_reason},
        investigation_id=investigation_id, actor=actor_name,
    )
    return get_investigation(investigation_id)


# --- Chatbot (Requirement 12) ------------------------------------------------------------

def ask_chat(investigation_id: str, question: str, actor: str = "reviewer") -> dict:
    settings = get_settings()
    result = answer_question(investigation_id, question, settings.bedrock_model_id)
    with cursor() as cur:
        cur.execute(
            """INSERT INTO chat_log
                (investigation_id, question, retrieved_chunk_ids_json, model_id, prompt_version,
                 answer, citations_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (investigation_id, question, dumps(result.retrieved_chunk_ids), result.model_id,
             result.prompt_version, result.answer, dumps(result.citations), _now()),
        )
    append_event(
        "chat_exchange",
        {"question": question, "retrieved_chunk_ids": result.retrieved_chunk_ids, "answer": result.answer,
         "citations": result.citations, "error": result.error},
        investigation_id=investigation_id, actor=actor, model_id=result.model_id,
        prompt_version=result.prompt_version,
    )
    return {
        "question": question, "answer": result.answer, "citations": result.citations,
        "retrieved_chunk_ids": result.retrieved_chunk_ids,
        "had_sufficient_context": result.had_sufficient_context, "error": result.error,
    }


def list_chat_history(investigation_id: str) -> list[dict]:
    rows = fetchall(
        "SELECT * FROM chat_log WHERE investigation_id=? ORDER BY id ASC", (investigation_id,)
    )
    out = []
    for r in rows:
        d = row_to_dict(r)
        d["retrieved_chunk_ids"] = loads(d.pop("retrieved_chunk_ids_json"))
        d["citations"] = loads(d.pop("citations_json"))
        out.append(d)
    return out


# --- Metrics (Requirement 10) -------------------------------------------------------------

def compute_metrics(investigation_id: str) -> dict:
    inv = get_investigation(investigation_id)
    settings = get_settings()
    cases = inv["cases"]
    n = len(cases)
    facts_extracted = sum(len(c["extraction"].get("facts", [])) for c in cases)
    quotes_verified = sum(c["extraction"].get("quotes_verified", 0) for c in cases)
    quotes_rejected = sum(c["extraction"].get("quotes_rejected", 0) for c in cases)
    extraction_failures = sum(1 for c in cases if c["extraction"].get("extraction_failed"))
    manual_minutes = settings.manual_minutes_per_case

    return {
        "cases_processed": n,
        "ai_processing_seconds": inv["ai_processing_seconds"],
        "facts_extracted": facts_extracted,
        "quotes_verified": quotes_verified,
        "quotes_rejected": quotes_rejected,
        "extraction_failures": extraction_failures,
        "manual_minutes_per_case_assumption": manual_minutes,
        "estimated_manual_minutes_saved": round(n * manual_minutes, 1),
        "estimated_manual_hours_saved": round(n * manual_minutes / 60, 2),
    }
