# AI Signal Investigation Copilot — Build Task List

Architecture: single Python process (FastAPI) serves both the JSON API and a static
vanilla-JS frontend (no build step) so the whole app starts with one command
(`python run.py`). Persistence is a single SQLite file. Vector store is a brute-force numpy
cosine-similarity store over Bedrock Titan embeddings. Requirement IDs refer to
`requirements.md`.

**Status: core build complete and passing 33 automated tests.** Live LLM behaviour
(extraction/chat/summary against real Bedrock) is architecturally in place but untested
end-to-end because no AWS credentials are configured in this environment — see README
"AWS credentials" section. Everything else runs and was smoke-tested against a live server.

## 0. Scaffold — done
- [x] Repo structure, `requirements.txt`, `.env.example`, `.gitignore`, `run.py`, `README.md`
- [x] `git init` + commits

## 1. Synthetic dataset (Req 1) — done
- [x] Seeded generator: 1000 FAERS-style reports
- [x] Planted true signal (Zentrivex / Acute Hepatic Failure) — strong causal narratives
- [x] Planted confounded signal (Mirocaine / Acute Kidney Injury) — statistically flagged,
      narratives dominated by alternative causes
- [x] Causal features live only in narrative text
- [x] Persist to SQLite on first run (auto-seeded at startup)

## 2. Deterministic signal detection (Req 2) — done
- [x] 2x2 table, PRR, ROR + 95% CI, chi-square; Evans criteria; pure function (unit-tested)
- [x] API: `/api/signals` (ranked by PRR), `/api/signals/table` (2x2 on request)

## 3. LLM fact extraction (Req 3) + guardrails (Req 4) — done (untested live)
- [x] Bedrock Converse client wrapper, temp 0, forced tool-use JSON schema
- [x] Versioned extraction prompt; Pydantic schema validation (non-conforming = failure)
- [x] Substring/offset verification guardrail; downgrade-to-unknown on failed verification
- [x] Guardrail outcome recorded per extraction; concurrent extraction (ThreadPoolExecutor)
- [x] Extraction cache keyed by hash(model+prompt_version+narrative)
- [ ] Live timing validation against real Bedrock (~40 cases <60s) — needs AWS credentials

## 4. Evidence navigation (Req 4a) — done
- [x] Char offsets stored per verified quote; UI scrolls+highlights via `<mark>`, no
      re-searching at render time
- [x] Unverified/unknown facts shown explicitly, never a false highlight
- [x] Chatbot citations use the same click-navigation mechanism
- [x] Keyboard-operable (native buttons); aria-live announcer for assistive tech

## 5. Causality rule engine (Req 5) — done
- [x] Versioned WHO-UMC-inspired pure-function rules; rule ID + explanation recorded

## 6. Recommendation rule engine (Req 6) — done
- [x] Versioned pure function; recomputes on override; exposes rule ID/version/thresholds

## 7. AI-drafted summary (Req 7) — done (untested live)
- [x] Drafted from structured facts/stats/recommendation; case-ID citation verification;
      labelled "AI draft – requires human approval"

## 8. Human review & sign-off (Req 8) — done
- [x] Override with required reason; AI/rule/override visually distinguished (icon+text)
- [x] Summary editor; sign-off (name + decision + reason); cannot complete without sign-off

## 9. Audit trail (Req 9) — done
- [x] Hash-chained append-only log (atomic read-prev+write under one DB lock)
- [x] Chain-verification endpoint (tamper-detection unit-tested)
- [x] Cache reuse verified to skip new LLM calls on rerun

## 10. Effort metrics (Req 10) — done
- [x] Cases processed, AI time, facts extracted, quotes verified/rejected, manual time saved
      (configurable `MANUAL_MINUTES_PER_CASE`)

## 11. Demo operability (Req 11) — done
- [x] Single command (`python run.py`), one process
- [x] LLM-unreachable path smoke-tested: fails loudly per case, rest of app still works
- [x] Accessibility: semantic HTML, skip link, labelled fields, keyboard-operable, status
      badges use icon+text, not colour alone
- [x] Fixed a real SQLite thread-safety bug found during smoke testing (concurrent
      extraction workers sharing one connection unsynchronized) — see `backend/db.py`

## 12. RAG chatbot (Req 12) — done (untested live)
- [x] KB build (case narratives/sentences, verified facts, stats) at two granularities
- [x] Retrieval: summary vectors select cases, then chunk vectors within them
- [x] Scoped strictly to the investigation's KB
- [x] Citation verification against retrieved context; unverifiable citations flagged inline
- [x] No-sufficient-context path answers "no evidence" without even calling the LLM
- [x] Logged to audit trail; temperature 0

## 13. Frontend UI — done
- [x] Dashboard, Cases & Evidence, Recommendation & Summary, Ask the Copilot, Metrics, Audit
      Trail views; accessibility pass

## 14. Tests — done (33 passing)
- [x] Stats, causality, recommendation, guardrails, audit chain (+tamper), extraction
      pipeline (schema rejection, cache, unreachable-LLM), vectorstore scoping, RAG citation
      verification, full end-to-end investigation flow

## 15. Docs — done
- [x] README: setup, AWS credential requirement, one-command run, assumptions, demo script

## Remaining / follow-ups
- [ ] Validate live Bedrock behaviour once AWS credentials are supplied (extraction timing,
      real embeddings/retrieval quality, chat/summary text quality)
- [ ] Optional polish: replace the 2x2-table `alert()` with a proper dialog; richer KB
      chunk browsing in the audit view
