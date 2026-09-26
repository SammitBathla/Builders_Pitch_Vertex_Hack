"""Postgres persistence layer (Supabase or any Postgres) — see README "Database".

Schema is intentionally denormalised/explicit so every stored value can be traced back to
which layer produced it (AI extraction vs rule vs human override) per Requirement 8.2 and
the audit trail of Requirement 9.

Query strings throughout the codebase were originally written for sqlite3's "?"
placeholder convention. Rather than rewrite every call site, `_TranslatingCursor` below
rewrites "?" to psycopg's "%s" transparently, so those call sites are unchanged. The one
sqlite-specific idiom that couldn't be papered over this way was `cursor.lastrowid` (no
Postgres equivalent) — see `backend/audit/trail.py`, which uses `RETURNING seq` instead.
"""
from __future__ import annotations

import json
import re
import threading
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from backend.config import get_settings

# A single shared connection is used across the ThreadPoolExecutor workers that drive
# concurrent extraction/embedding (Requirement 3.5). A bare connection is not safe for
# unsynchronized concurrent use from multiple threads, and the audit hash chain
# (Requirement 9.2) additionally requires reads-then-writes of "the last hash" to be
# strictly serialized. This lock guards every access to the connection, DB-wide.
_DB_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    drug TEXT NOT NULL,
    event TEXT NOT NULL,
    age INTEGER,
    sex TEXT,
    seriousness TEXT,
    country TEXT,
    received_date TEXT,
    narrative TEXT NOT NULL,
    is_planted_true_signal INTEGER DEFAULT 0,
    is_planted_confounded_signal INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reports_drug_event ON reports(drug, event);

CREATE TABLE IF NOT EXISTS investigations (
    investigation_id TEXT PRIMARY KEY,
    drug TEXT NOT NULL,
    event TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | signed_off
    created_at TEXT NOT NULL,
    stats_json TEXT,
    recommendation_json TEXT,
    summary_draft TEXT,
    summary_final TEXT,
    summary_citation_check_json TEXT,
    signed_off_at TEXT,
    signed_off_by TEXT,
    final_decision TEXT,       -- accept_recommendation | override_recommendation
    decision_reason TEXT,
    ai_processing_seconds REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS extractions (
    id SERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    model_id TEXT,
    prompt_version TEXT,
    schema_valid INTEGER NOT NULL,
    extraction_failed INTEGER NOT NULL DEFAULT 0,
    failure_reason TEXT,
    time_to_onset_days INTEGER,
    onset_order TEXT,
    dechallenge TEXT,
    rechallenge TEXT,
    confounders_json TEXT,
    data_gaps_json TEXT,
    facts_json TEXT NOT NULL,   -- full structured fact list incl. quotes + offsets + verified flag
    quotes_verified INTEGER DEFAULT 0,
    quotes_rejected INTEGER DEFAULT 0,
    cache_hit INTEGER DEFAULT 0,
    cache_key TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(investigation_id, report_id)
);

CREATE TABLE IF NOT EXISTS extraction_cache (
    cache_key TEXT PRIMARY KEY,   -- sha256(model_id + prompt_version + narrative)
    model_id TEXT,
    prompt_version TEXT,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS causality (
    id SERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    category TEXT NOT NULL,           -- Certain|Probable|Possible|Unlikely|Unassessable
    source TEXT NOT NULL,             -- rule | override
    rule_id TEXT,
    ruleset_version TEXT,
    explanation TEXT,
    overridden_by TEXT,
    override_reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(investigation_id, report_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    seq SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    investigation_id TEXT,
    payload_json TEXT NOT NULL,
    actor TEXT,
    model_id TEXT,
    prompt_version TEXT,
    rule_version TEXT,
    timestamp TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    chunk_id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    report_id TEXT,
    chunk_type TEXT NOT NULL,   -- narrative | fact | stat | case_summary
    text TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    granularity TEXT NOT NULL,  -- summary | chunk
    embedding_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kb_investigation ON kb_chunks(investigation_id, granularity);

CREATE TABLE IF NOT EXISTS chat_log (
    id SERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL,
    question TEXT NOT NULL,
    retrieved_chunk_ids_json TEXT,
    model_id TEXT,
    prompt_version TEXT,
    answer TEXT,
    citations_json TEXT,
    created_at TEXT NOT NULL
);
"""

_QMARK_RE = re.compile(r"\?")


def _translate(sql: str) -> str:
    return _QMARK_RE.sub("%s", sql)


class _TranslatingCursor:
    """Wraps a psycopg cursor so existing '?'-placeholder SQL (written for sqlite3) keeps
    working unmodified against Postgres. Intentionally does NOT implement `.lastrowid`
    (Postgres has none) — that call site (audit/trail.py) uses `RETURNING` instead."""

    def __init__(self, real_cursor):
        self._cur = real_cursor

    def execute(self, sql: str, params: tuple = ()):
        self._cur.execute(_translate(sql), params)
        return self

    def executemany(self, sql: str, seq_of_params):
        self._cur.executemany(_translate(sql), seq_of_params)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def close(self):
        self._cur.close()


_conn: psycopg.Connection | None = None


def _connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, row_factory=dict_row, autocommit=False)


def get_connection() -> psycopg.Connection:
    global _conn
    with _DB_LOCK:
        if _conn is None:
            settings = get_settings()
            if not settings.database_url:
                raise RuntimeError(
                    "DATABASE_URL is not set. This app persists to Postgres (Supabase or "
                    "any Postgres) — copy a connection string into .env. See "
                    ".env.example / README 'Database' section."
                )
            _conn = _connect(settings.database_url)
            with _conn.cursor() as cur:
                cur.execute(SCHEMA)
            _conn.commit()
        return _conn


@contextmanager
def cursor() -> Iterator[_TranslatingCursor]:
    """Guarded write handle: acquires the DB-wide lock for the duration of the block, so
    concurrent writers (e.g. extraction workers) never interleave statements on the shared
    connection, and commits atomically before releasing it."""
    with _DB_LOCK:
        conn = get_connection()
        cur = _TranslatingCursor(conn.cursor())
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def fetchone(sql: str, params: tuple = ()) -> dict | None:
    with _DB_LOCK:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(_translate(sql), params)
            return cur.fetchone()


def fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with _DB_LOCK:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(_translate(sql), params)
            return cur.fetchall()


def row_to_dict(row: dict) -> dict:
    """psycopg's dict_row factory already returns plain dicts; kept as a no-op so every
    existing call site (`row_to_dict(r)`) needs no change."""
    return dict(row)


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def loads(s: str | None):
    if s is None:
        return None
    return json.loads(s)
