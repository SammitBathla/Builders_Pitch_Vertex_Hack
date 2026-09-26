"""Requirement 11.1: single process serves both the API and the static frontend."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.schemas import (
    ChatRequest, CreateInvestigationRequest, EditSummaryRequest, OverrideRequest, SignOffRequest,
)
from backend.audit.trail import list_events, verify_chain
from backend.config import get_settings
from backend.data_gen.seed import seed_database
from backend.db import get_connection
import backend.services.investigation as svc

app = FastAPI(title="AI Signal Investigation Copilot")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    get_connection()
    seed_database()


# --- Signals (Requirement 2) -------------------------------------------------------------

@app.get("/api/signals")
def api_list_signals():
    return {"signals": svc.list_flagged_signals()}


@app.get("/api/signals/table")
def api_signal_table(drug: str, event: str):
    return svc.get_pair_stats(drug, event)


# --- Investigations (Requirements 3-9, 12) ------------------------------------------------

@app.get("/api/investigations")
def api_list_investigations():
    return {"investigations": svc.list_investigations()}


@app.post("/api/investigations")
def api_create_investigation(body: CreateInvestigationRequest):
    try:
        return svc.create_investigation(body.drug, body.event, actor=body.actor)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/investigations/{investigation_id}")
def api_get_investigation(investigation_id: str):
    try:
        return svc.get_investigation(investigation_id)
    except KeyError:
        raise HTTPException(404, "Investigation not found")


@app.post("/api/investigations/{investigation_id}/cases/{report_id}/override")
def api_override_case(investigation_id: str, report_id: str, body: OverrideRequest):
    try:
        return svc.override_case(investigation_id, report_id, body.category, body.reason, body.actor)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "Investigation not found")


@app.post("/api/investigations/{investigation_id}/summary/draft")
def api_generate_summary(investigation_id: str):
    try:
        return svc.generate_summary(investigation_id)
    except KeyError:
        raise HTTPException(404, "Investigation not found")


@app.put("/api/investigations/{investigation_id}/summary")
def api_edit_summary(investigation_id: str, body: EditSummaryRequest):
    try:
        return svc.edit_summary(investigation_id, body.text, body.actor)
    except KeyError:
        raise HTTPException(404, "Investigation not found")


@app.post("/api/investigations/{investigation_id}/signoff")
def api_sign_off(investigation_id: str, body: SignOffRequest):
    try:
        return svc.sign_off(investigation_id, body.actor_name, body.final_decision, body.decision_reason)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "Investigation not found")


@app.post("/api/investigations/{investigation_id}/chat")
def api_chat(investigation_id: str, body: ChatRequest):
    return svc.ask_chat(investigation_id, body.question, actor=body.actor)


@app.get("/api/investigations/{investigation_id}/chat")
def api_chat_history(investigation_id: str):
    return {"messages": svc.list_chat_history(investigation_id)}


@app.get("/api/investigations/{investigation_id}/metrics")
def api_metrics(investigation_id: str):
    try:
        return svc.compute_metrics(investigation_id)
    except KeyError:
        raise HTTPException(404, "Investigation not found")


# --- Audit trail (Requirement 9) ----------------------------------------------------------

@app.get("/api/audit")
def api_audit(investigation_id: str | None = None):
    return {"events": list_events(investigation_id)}


@app.get("/api/audit/verify")
def api_audit_verify():
    return verify_chain()


# --- Config surfaced to the UI (assumptions banner) ---------------------------------------

@app.get("/api/config")
def api_config():
    s = get_settings()
    return {
        "manual_minutes_per_case": s.manual_minutes_per_case,
        "llm_provider": s.llm_provider,
        "anthropic_model_id": s.anthropic_model_id,
        "assumptions": [
            "A1. All data is synthetic, FAERS-style; no real patient data.",
            "A2. Drug names are fictional; event terms are MedDRA-like but not a licensed dictionary.",
            "A3. Causality rules are simplified, WHO-UMC-inspired, not a validated clinical algorithm.",
            "A4. Manual effort baseline (minutes/case) is a configurable assumption.",
            "A5. Single-user local prototype; authentication is out of scope.",
            f"A6. LLM: Anthropic Claude API ({s.anthropic_model_id}). Deviates from the original "
            "Bedrock Nova Lite plan because an Anthropic key, not AWS credentials, was available "
            "in this environment (see README). This model doesn't expose a temperature parameter "
            "(sampling controls were removed on it); consistency instead comes from low inference "
            "effort plus this system's own downstream verification, rules and guardrails.",
            "A6a. Embeddings for the RAG knowledge base use a local, deterministic hashing vector "
            "(feature hashing), not a trained embedding model — Anthropic has no embeddings "
            "endpoint. Retrieval is keyword-driven rather than semantic; see README.",
        ],
    }


# --- Static frontend (Requirement 11.1) ----------------------------------------------------
# The frontend is now a Vite/React app (frontend/) — its BUILD OUTPUT (frontend/dist/) is
# what gets served, not the source tree. Mounted at "/" and LAST, so it only catches paths
# no /api/* route above matched. html=True serves index.html for "/".
#
# Local single-command dev requires one manual step first (`cd frontend && npm install &&
# npm run build`) — this guard just means `python run.py` alone, with no frontend build,
# serves the API only rather than crashing; the same frontend/dist/ also deploys as a
# standalone static site (e.g. Vercel, pointed at frontend/ with Vite auto-detected),
# with frontend/.env.production's VITE_API_BASE telling it where this backend lives.

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
