# AI Signal Investigation Copilot — Build Task List

Architecture: FastAPI backend (deployable standalone, e.g. Render) + a plain static
vanilla-JS frontend (deployable standalone, e.g. Vercel — no build step, no React), which
FastAPI can also serve itself for single-command local dev (`python run.py`). Persistence
is Postgres (Supabase or any Postgres) via `DATABASE_URL` — no local-file fallback (see
README "Database"). Vector store is a brute-force numpy cosine-similarity store over
locally-computed hashing vectors, stored in Postgres. Requirement IDs refer to
`requirements.md`.

**Status: core build complete, passing 33 automated tests (22 pure-logic + 11 DB-dependent,
gracefully skipped without a DATABASE_URL), and verified live end-to-end against the real
Anthropic Claude API** (`claude-opus-5` — see README "LLM provider" for why this deviates
from Assumption A6's original Bedrock plan). Live results (from before the Postgres
migration, against the then-SQLite backend — logic is unchanged, re-verify once Supabase is
wired up): 26-case true-signal investigation (Zentrivex) ran in 12.4s with 0 extraction
failures, all quotes verified, correct causality (Certain/Probable/Possible) and
recommendation ("Validated – escalate"); 23-case confounded investigation (Mirocaine) ran in
9.5s, 0 failures, correctly did NOT validate; AI summary drafting produced a well-cited
clinical narrative with zero invalid case-ID citations; the RAG chatbot answered a real
question with verified, click-navigable citations; the audit hash chain stayed valid across
216+ events.

**Currently migrating to Postgres (Supabase) + split deployment (Render backend / Vercel
frontend)** — see "16. Deployment migration" below for exact status.

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

## 14. Tests — done (33; 22 pure-logic + 11 DB-dependent)
- [x] Stats, causality, recommendation, guardrails, audit chain (+tamper), extraction
      pipeline (schema rejection, cache, unreachable-LLM), vectorstore scoping, RAG citation
      verification, full end-to-end investigation flow
- [x] `tests/conftest.py`'s `fresh_db` fixture: isolated throwaway Postgres schema per test
      (via libpq `options=-csearch_path=...`), skips gracefully without a DATABASE_URL

## 15. Docs — done
- [x] README: setup, LLM provider deviation (Anthropic, not Bedrock), Database (Supabase)
      walkthrough, Deployment (Vercel + Render), one-command local run, assumptions, demo script

## 16. Deployment migration (branch: dev) — in progress
- [x] Frontend made deployable standalone: relative asset paths, `frontend/config.js`
      (`window.API_BASE`), FastAPI static mount moved to "/" (after all /api/* routes) with
      html=True — local `python run.py` behaviour unchanged, verified
- [x] `render.yaml` added for one-click Render backend deploy
- [x] DB layer rewritten Postgres-only (`backend/db.py`): SERIAL instead of AUTOINCREMENT,
      `_TranslatingCursor` maps existing `?`-placeholder SQL to `%s` so call sites didn't
      need touching, `RETURNING seq` replaces `cursor.lastrowid` (audit trail — the one
      genuinely Postgres-incompatible idiom), named placeholders in `seed.py` converted from
      sqlite3's `:name` to psycopg's `%(name)s`
- [x] `psycopg[binary]` added; `boto3`/AWS config kept (unused, Bedrock fallback)
- [x] **Live-verified against a real Supabase project (Postgres 17.6, ap-northeast-1)**:
      full suite 33/33 passing twice in a row, live app running, both planted-signal
      investigations created, override/summary/chat/sign-off/audit-chain all exercised for
      real. Found and fixed a real bug along the way: `conftest.py`'s per-test schema
      isolation had a malformed libpq options string (`-csearch_path=...` needed a space:
      `-c search_path=...`), which had let one test's intentional tamper-test corrupt the
      *real* `public.audit_log` table instead of a throwaway schema — confirmed the exact
      residue (literal strings matching the tests' hardcoded values), truncated it, fixed
      the fixture, re-verified clean on a second full run.
- [x] **Fixed a real, measured perf regression**: single round-trip latency to this
      Supabase project measured at ~465ms (region distance). Unbatched code meant
      `create_investigation` issued ~300+ sequential round trips (one INSERT per
      case/table/audit-event/KB-chunk) — ~140s+ of pure DB latency on top of the LLM calls.
      Fixed by batching every multi-row write into one round trip:
      - `backend/db.py`: new `insert_many()` (single multi-row INSERT, optional
        `RETURNING` — Postgres preserves row order for both)
      - `backend/audit/trail.py`: new `append_events_batch()` — computes the whole hash
        chain in memory (still correctly sequential/tamper-evident) from one read of the
        starting hash, then writes all events in one INSERT
      - `backend/kb/vectorstore.py` / `kb/build.py`: `add_chunks_batch()` — one insert for
        an entire KB build instead of one per chunk (~150-200 chunks/investigation)
      - `backend/services/investigation.py`: `create_investigation()`'s per-case loop now
        builds rows/events in memory first, writes them in ~4 batched round trips total
      - `backend/stats/disproportionality.py` + `services/investigation.py`: dashboard
        signal listing and the 2x2 table now use SQL `GROUP BY`/conditional-`SUM`
        aggregation instead of fetching all 1000 full report rows (narrative text
        included) just to recompute counts in Python
      **Measured results** (same Zentrivex signal, same machine, same Supabase project):
      `create_investigation` 26 cases: ~2.5min (est., unbatched) → **13.3s** (4.4s of which
      is the actual Claude extraction). Dashboard `/api/signals`: 2.6s → **0.54s**. 2x2
      table: → **0.24s**.
- [ ] Not yet batched: the one-time 1000-row dataset seed (`data_gen/seed.py`) still uses
      per-row `executemany` — only affects first-ever startup against an empty database, so
      lower priority, but still slow (contributes most of the ~3min full test-suite runtime
      against real Supabase). Same `insert_many()` fix would apply.
- [ ] Deploy: Render backend (`render.yaml` ready) + Vercel frontend (root dir `frontend/`,
      set `window.API_BASE` in `frontend/config.js` to the Render URL) — not yet done

## Remaining / follow-ups
- [ ] Optional: swap the local hashing embeddings for a real embedding provider (Voyage AI,
      OpenAI, or Bedrock Titan if AWS credentials become available) for semantic retrieval
- [ ] Optional polish: richer KB chunk browsing in the audit view
