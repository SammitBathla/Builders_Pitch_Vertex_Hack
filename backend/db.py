"""SQLite persistence layer. One file, no external DB server (Requirement 11.1).

Schema is intentionally denormalised/explicit so every stored value can be traced back to
which layer produced it (AI extraction vs rule vs human override) per Requirement 8.2 and
the audit trail of Requirement 9.
"""
from __future__ import annotations

import sqlite3
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.config import get_settings

# A single shared sqlite3.Connection is used across the ThreadPoolExecutor workers that
# drive concurrent extraction/embedding (Requirement 3.5). A bare Python sqlite3 Connection
# is not safe for unsynchronized concurrent use from multiple threads even with
# check_same_thread=False, and the audit hash chain (Requirement 9.2) additionally requires
# reads-then-writes of "the last hash" to be strictly serialized. This lock guards every
# access to the connection, DB-wide.
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


_conn: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    global _conn
    with _DB_LOCK:
        if _conn is None:
            settings = get_settings()
            _conn = _connect(settings.sqlite_path)
            _conn.executescript(SCHEMA)
            _conn.commit()
        return _conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    """Guarded write handle: acquires the DB-wide lock for the duration of the block, so
    concurrent writers (e.g. extraction workers) never interleave statements on the shared
    connection, and commits atomically before releasing it."""
    with _DB_LOCK:
        conn = get_connection()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def fetchone(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with _DB_LOCK:
        return get_connection().execute(sql, params).fetchone()


def fetchall(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _DB_LOCK:
        return get_connection().execute(sql, params).fetchall()


def row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def loads(s: str | None):
    if s is None:
        return None
    return json.loads(s)
