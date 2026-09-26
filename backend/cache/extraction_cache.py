"""Requirement 9.3: cache extractions keyed by hash(model ID + prompt version + narrative)
so re-running an investigation reproduces identical facts without new LLM calls."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from backend.db import cursor, dumps, fetchone, loads


def cache_key(model_id: str, prompt_version: str, narrative: str) -> str:
    material = f"{model_id}|{prompt_version}|{narrative}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def get_cached(key: str) -> dict | None:
    row = fetchone("SELECT result_json FROM extraction_cache WHERE cache_key = ?", (key,))
    if row is None:
        return None
    return loads(row["result_json"])


def put_cached(key: str, model_id: str, prompt_version: str, result: dict) -> None:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO extraction_cache (cache_key, model_id, prompt_version, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO NOTHING
            """,
            (key, model_id, prompt_version, dumps(result), datetime.now(timezone.utc).isoformat()),
        )
