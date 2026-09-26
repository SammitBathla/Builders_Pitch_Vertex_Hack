# AI Signal Investigation Copilot

A pharmacovigilance signal-investigation prototype: deterministic statistics detect
disproportionate drug–event pairs, an LLM extracts causality-relevant facts from case
narratives (with every quote independently verified against the source text), versioned
pure-function rules assign causality and a recommendation, and a human reviewer approves or
overrides every AI-derived value before signing off. See [requirements.md](requirements.md)
for the full specification and [TASKS.md](TASKS.md) for the build checklist.

## Architecture

- **Deployable as two independent pieces.** `frontend/` is a React app built with Vite
  (deployable as a static build, e.g. Vercel — auto-detected, standard build pipeline) and
  `backend/` is a FastAPI app (e.g. Render). The FastAPI app can also serve the frontend's
  build output itself for local single-command dev (`python run.py`, after one `npm run
  build`) — `VITE_API_BASE` (set at build time) is the only thing that changes between modes.
- **Database.** Postgres (Supabase or any Postgres) via `DATABASE_URL` — no local-file
  fallback. See "Database" below.
- **Vector store.** Brute-force numpy cosine similarity over locally-computed hashing
  vectors (see "LLM provider" below), stored in Postgres — the corpus per signal (dozens of
  cases) doesn't need pgvector/FAISS.
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
frontend/        React (Vite) UI — dashboard, cases/evidence, recommendation/summary, chat, audit
tests/           pytest — deterministic pieces + integration flow, no AWS required
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in DATABASE_URL and ANTHROPIC_API_KEY (see below)

cd frontend
npm install
npm run build            # produces frontend/dist/, which the backend serves
cd ..

python run.py            # starts on http://localhost:8000
```

The dataset (1,000+ synthetic reports, fixed seed) is generated automatically into Postgres
on first startup (once `reports` is empty — safe to leave running, it won't re-seed).

**Frontend development** (hot reload, instead of rebuilding on every change): run the
backend (`python run.py`) in one terminal, then in another:
```bash
cd frontend
npm run dev              # starts on http://localhost:5173, proxies /api/* to :8000
```
`vite.config.js`'s dev-server proxy means the app works with the same relative
`fetch("/api/...")` calls either way — no code difference between dev and the production
build, only *how* `/api/*` reaches the backend (Vite's proxy vs. FastAPI serving both).

### Database: Postgres via Supabase (required — no local-file fallback)

The app persists everything (reports, investigations, extractions, causality, the audit
trail, the KB vector store, chat history) to Postgres via `DATABASE_URL`. There's no SQLite
fallback for zero-config local dev — this was a deliberate tradeoff for a database that
survives Render's ephemeral disk in production, at the cost of needing a real Postgres even
locally. Any Postgres works; these instructions use Supabase's free tier since it's the
fastest path to one:

1. Create a free project at [supabase.com/dashboard](https://supabase.com/dashboard) (pick
   any name/region/password — save the password, you'll need it in the connection string).
2. Once it's provisioned: **Project Settings → Database → Connection string**, select
   **"Session pooler"** (not "Direct connection" — the pooler works from IPv4-only hosts
   like Render/Vercel, which most hosts are; direct connections require IPv6).
3. Copy that URI, replace `[YOUR-PASSWORD]` with your actual project password, and paste it
   into `.env` as `DATABASE_URL=postgresql://...`.
4. `python run.py` — on first startup it creates all tables (see `SCHEMA` in
   `backend/db.py`) and seeds the synthetic dataset automatically.

The same `DATABASE_URL` also works for running the test suite against — see "Running the
tests" below; tests use an isolated throwaway schema, never your real tables.

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

## Deployment: frontend on Vercel, backend on Render

**Frontend (Vercel) — React (Vite), auto-detected.**
1. New Vercel project → import this GitHub repo.
2. Project Settings → **Root Directory** → `frontend`. Framework preset: Vercel
   auto-detects **Vite** from `package.json`/`vite.config.js` — build command
   (`npm run build`) and output directory (`dist`) are filled in automatically.
3. Project Settings → **Environment Variables** → add `VITE_API_BASE` = your Render
   backend's URL (e.g. `https://your-backend.onrender.com`, no trailing slash). Vite reads
   this at *build* time, so it must be set before deploying, not edited afterward — a
   change to it requires a redeploy, not just a page refresh.
4. Deploy.

**Backend (Render).**
1. New Web Service → connect this GitHub repo (this repo includes `render.yaml`, so you can
   also use Render's "Blueprint" deploy to skip the manual steps below).
2. Build command: `pip install -r requirements.txt`. Start command: `python run.py` — it
   already reads Render's `$PORT`, no changes needed.
3. Environment variables: `DATABASE_URL` (your Supabase connection string — **this is what
   makes data survive Render's restarts/redeploys, which wipe local disk**), `ANTHROPIC_API_KEY`,
   `ANTHROPIC_MODEL_ID=claude-opus-5`.
4. Deploy. First request seeds the dataset into your Supabase Postgres.

CORS is already wide open (`allow_origins=["*"]` in `backend/api/main.py`) so the
Vercel-hosted frontend can call the Render backend directly — no proxy/rewrite needed.

## Running the tests

```bash
python -m pytest tests/ -q
```

22 of 33 tests are pure logic (dataset reproducibility, PRR/ROR/chi-square determinism,
causality/recommendation rules, quote-verification guardrails) and need nothing — no
database, no API key. The other 11 touch the database (audit hash chain, extraction
pipeline, vector store, RAG chatbot, the full end-to-end investigation flow) and need a
Postgres to run against; **they skip gracefully (not fail) if `DATABASE_URL` isn't set.**
Point `TEST_DATABASE_URL` (or just reuse `DATABASE_URL`) at any Postgres, including your
Supabase project directly — each test runs in its own throwaway schema
(`tests/conftest.py`'s `fresh_db` fixture) and cleans up after itself, so it's safe to point
at the same database the app itself uses.

None of the 33 tests call a real LLM — Anthropic calls are mocked throughout, so the suite
never spends API credits.

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
