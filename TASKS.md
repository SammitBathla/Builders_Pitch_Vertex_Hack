# AI Signal Investigation Copilot — Build Task List

Architecture: single Python process (FastAPI) serves both the JSON API and a static
vanilla-JS frontend (no build step) so the whole app starts with one command
(`python run.py`). Persistence is a single SQLite file. Vector store is a brute-force numpy
cosine-similarity store over locally-computed hashing vectors. Requirement IDs refer to
`requirements.md`.

**Status: core build complete, passing 33 automated tests, and verified live end-to-end**
against the real Anthropic Claude API (`claude-opus-5` — see README "LLM provider" for why
this deviates from Assumption A6's original Bedrock plan). Live results: 26-case true-signal
investigation (Zentrivex) ran in 12.4s with 0 extraction failures, all quotes verified,
correct causality (Certain/Probable/Possible) and recommendation ("Validated – escalate");
23-case confounded investigation (Mirocaine) ran in 9.5s, 0 failures, correctly did NOT
validate (fell to "Insufficient information" given the actual causality mix the model
extracted — a legitimate rule-engine outcome, not a bug); AI summary drafting produced a
well-cited clinical narrative with zero invalid case-ID citations; the RAG chatbot answered
a real question with verified, click-navigable citations; the audit hash chain stayed valid
across 216+ events including all of the above.

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

## 3. LLM fact extraction (Req 3) + guardrails (Req 4) — done, verified live
- [x] Anthropic Claude API client (`claude-opus-5`), forced JSON-schema structured output
      (no `temperature` — the model rejects it; low inference effort used instead)
- [x] Versioned extraction prompt; Pydantic schema validation (non-conforming = failure)
- [x] Substring/offset verification guardrail; downgrade-to-unknown on failed verification
- [x] Guardrail outcome recorded per extraction; concurrent extraction (ThreadPoolExecutor)
- [x] Extraction cache keyed by hash(model+prompt_version+narrative)
- [x] Live timing validated: 26 real cases in 12.4s, 23 in 9.5s — well under the ~60s target

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

## 12. RAG chatbot (Req 12) — done, verified live
- [x] KB build (case narratives/sentences, verified facts, stats) at two granularities
- [x] Retrieval: summary vectors select cases, then chunk vectors within them
- [x] Scoped strictly to the investigation's KB
- [x] Citation verification against retrieved context; unverifiable citations flagged inline
- [x] No-sufficient-context path answers "no evidence" without even calling the LLM
- [x] Logged to audit trail
- [x] Live-tested: a real question returned a correctly-cited, verified answer; embeddings
      are a local hashing fallback (no Anthropic embeddings endpoint) — keyword-driven
      retrieval, not semantic; see README

## 13. Frontend UI — done
- [x] Dashboard, Cases & Evidence, Recommendation & Summary, Ask the Copilot, Metrics, Audit
      Trail views; accessibility pass

## 14. Tests — done (33 passing)
- [x] Stats, causality, recommendation, guardrails, audit chain (+tamper), extraction
      pipeline (schema rejection, cache, unreachable-LLM), vectorstore scoping, RAG citation
      verification, full end-to-end investigation flow

## 15. Docs — done
- [x] README: setup, LLM provider deviation (Anthropic, not Bedrock), one-command run,
      assumptions, demo script

## Remaining / follow-ups
- [ ] Optional: swap the local hashing embeddings for a real embedding provider (Voyage AI,
      OpenAI, or Bedrock Titan if AWS credentials become available) for semantic retrieval
- [ ] Optional polish: richer KB chunk browsing in the audit view
- [ ] Two pre-swap investigations (created before the Anthropic wiring) have all-failed
      extractions in the DB from testing without credentials — re-run those signals from
      the dashboard to get real results; new investigations are unaffected
