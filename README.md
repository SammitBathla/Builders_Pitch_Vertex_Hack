# AI Signal Investigation Copilot

A pharmacovigilance signal-investigation prototype: deterministic statistics detect
disproportionate drug–event pairs, an LLM extracts causality-relevant facts from case
narratives (with every quote independently verified against the source text), versioned
pure-function rules assign causality and a recommendation, and a human reviewer approves or
overrides every AI-derived value before signing off. See [requirements.md](requirements.md)
for the full specification and [TASKS.md](TASKS.md) for the build checklist.

## Architecture

- **One process, one command.** FastAPI serves both the JSON API and the static frontend
  (`frontend/`, vanilla HTML/CSS/JS — no build step).
- **One file database.** SQLite (`data/copilot.sqlite`), no external DB server.
- **Vector store.** Brute-force numpy cosine similarity over locally-computed hashing
  vectors (see "LLM provider" below), stored in SQLite — the corpus per signal (dozens of
  cases) doesn't need FAISS/pgvector.
- **LLM.** Anthropic Claude API (`claude-opus-5`), forced structured JSON-schema output for
  extraction. See "LLM provider" below for why this deviates from Assumption A6.

```
backend/
  data_gen/      Requirement 1  — synthetic FAERS-style dataset generator (seeded)
  stats/         Requirement 2  — PRR / ROR / chi-square, Evans criteria (pure functions)
  llm/           Requirement 3/4 — Anthropic client, prompts, schema validation, extraction
  guardrails/    Requirement 4  — Level 2 system guardrails (substring verification)
  rules/         Requirement 5/6 — versioned causality + recommendation rule engines
  audit/         Requirement 9  — hash-chained audit trail
  cache/         Requirement 9.3 — extraction cache
  kb/ chatbot/   Requirement 12 — RAG knowledge base + grounded chatbot
  summary/       Requirement 7  — AI-drafted investigation summary
  services/      Orchestrates all of the above into the investigation lifecycle
  api/           FastAPI routes
frontend/        Single-page vanilla JS UI (dashboard, cases/evidence, chat, audit)
tests/           pytest — deterministic pieces + integration flow, no AWS required
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY (see below)
python run.py           # starts on http://localhost:8000
```

The dataset (1,000+ synthetic reports, fixed seed) is generated automatically into SQLite on
first startup.

### LLM provider: Anthropic Claude API (deviates from Assumption A6)

Assumption A6 in `requirements.md` originally specified Amazon Bedrock Nova Lite. **This
deployment runs on the Anthropic Claude API instead** (`backend/llm/anthropic_client.py`,
model `claude-opus-5`), because an Anthropic API key — not AWS credentials — was the
credential available. Populate `ANTHROPIC_API_KEY` in `.env`. Two consequences worth
knowing:

- **No `temperature` parameter.** `claude-opus-5` rejects sampling controls entirely (a
  400 error) — there's no dial to turn to 0. Consistency instead comes from low inference
  effort on the high-volume extraction calls plus this system's own deterministic
  verification, rule engines and guardrails, which is where the real reproducibility
  guarantee always lived anyway.
- **No embeddings endpoint.** Anthropic doesn't offer one, so the RAG knowledge base
  (Requirement 12) uses a local, dependency-free, deterministic hashing vector
  (`embed_text` in `anthropic_client.py`) instead of a trained semantic embedding model.
  Retrieval is keyword-driven rather than semantic — it works well for exact-term
  questions ("which cases had X") and less well for paraphrased ones. Swapping in a real
  embedding provider (Voyage AI, OpenAI, Bedrock Titan) later is a one-function change.

The original Bedrock path (`backend/llm/bedrock_client.py`, AWS credentials in `.env`) is
kept in the repo, unused, in case you want to switch back — see that file's docstring.

**Without any credentials, the app still runs** — signal detection, the dashboard, dataset
generation, causality rules and the audit trail all work with zero AI calls. Every
extraction fails loudly and visibly per case (Requirement 11.2: "IF the LLM is unreachable
THEN fail loudly per case"), causality falls back to `Unassessable`, and the recommendation
engine correctly reports "Insufficient information" — this is the intended degraded-mode
behaviour, not a bug. Once cached results exist (`extraction_cache` table), they reload
without new calls even if credentials are later removed again.

**If you pasted an API key into a chat session to get this working:** treat it as
potentially exposed (chat logs persist) and rotate it in the Anthropic Console once you're
done testing.

## Running the tests

```bash
python -m pytest tests/ -q
```

33 tests cover: dataset reproducibility (fixed seed) and planted signals, PRR/ROR/chi-square
determinism, causality and recommendation rule determinism, quote-verification guardrails
(including hallucination rejection), the audit hash chain (including tamper detection), the
extraction pipeline's schema-rejection and cache behaviour, the vector store's retrieval
scoping, the RAG chatbot's citation verification and no-evidence fallback, and a full
end-to-end investigation flow (extraction → causality → recommendation → override →
sign-off) with the LLM layer mocked so none of this requires AWS credentials to verify.

## Demo script (~7 minutes)

1. **Dashboard** — flagged signals ranked by PRR. Point out the two planted pairs:
   `Zentrivex / Acute Hepatic Failure` (true signal — high PRR, strong causal narratives)
   and `Mirocaine / Acute Kidney Injury` (also statistically flagged, but confounded).
2. Click **Investigate** on Zentrivex → watch cases extract concurrently.
3. **Cases & Evidence** — click a fact (e.g. "Dechallenge: positive") → the narrative
   scrolls and highlights the exact verified quote. Show a rejected/unknown fact to
   demonstrate the guardrail never fakes a highlight.
4. **Recommendation & Summary** — show the rule ID/version/thresholds; generate the AI
   draft (labelled "requires human approval"); override one case's causality with a reason;
   watch the recommendation recompute live; sign off.
5. Repeat steps 2–4 briefly for **Mirocaine** to show the confounded pair reaching a
   different, correctly "not confirmed" recommendation despite also being a statistical
   signal.
6. **Ask the Copilot** — ask a follow-up question; click a citation to jump to its source.
7. **Audit Trail** — click "Verify chain integrity" to show the hash chain is intact.

## Assumptions

See `requirements.md` (A1–A6) and `/api/config` (rendered in the UI's "Assumptions" dialog).
