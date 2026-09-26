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
- **Vector store.** Brute-force numpy cosine similarity over Bedrock Titan embeddings,
  stored in SQLite — the corpus per signal (dozens of cases) doesn't need FAISS/pgvector.
- **LLM.** Amazon Bedrock Nova Lite (`apac.amazon.nova-lite-v1:0`, region `ap-south-1`),
  temperature 0, forced structured output via the Converse API's tool-use.

```
backend/
  data_gen/      Requirement 1  — synthetic FAERS-style dataset generator (seeded)
  stats/         Requirement 2  — PRR / ROR / chi-square, Evans criteria (pure functions)
  llm/           Requirement 3/4 — Bedrock client, prompts, schema validation, extraction
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
cp .env.example .env   # then fill in AWS credentials (see below)
python run.py           # starts on http://localhost:8000
```

The dataset (1,000+ synthetic reports, fixed seed) is generated automatically into SQLite on
first startup.

### AWS credentials (required for live extraction / chat / summary)

This prototype calls **Amazon Bedrock** (Nova Lite for text, Titan for embeddings) in
`ap-south-1`. **No AWS credentials are configured in this environment** — you'll need to
supply your own before extraction, the chatbot, or AI summary drafting will work against a
real model:

- Either populate `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (and optionally
  `AWS_SESSION_TOKEN`) in `.env`, or
- Rely on the standard boto3 credential chain (`aws configure`, `~/.aws/credentials`, an
  instance/task role, SSO, etc.) and leave those blank.

Either way, your IAM principal needs `bedrock:InvokeModel` / `bedrock:Converse` for
`apac.amazon.nova-lite-v1:0` and `amazon.titan-embed-text-v2:0` in `ap-south-1`.

**Without credentials, the app still runs** — signal detection, the dashboard, dataset
generation, causality rules and the audit trail all work with zero AI calls. Every
extraction will fail loudly and visibly per case (Requirement 11.2: "IF the LLM is
unreachable THEN fail loudly per case"), causality falls back to `Unassessable`, and the
recommendation engine correctly reports "Insufficient information" — this is the intended
degraded-mode behaviour, not a bug. Once cached results exist (`extraction_cache` table),
they reload without new calls even if credentials are later removed again.

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
