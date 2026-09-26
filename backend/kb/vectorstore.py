"""Requirement 12.2/12.3: brute-force cosine-similarity vector store over SQLite-persisted
embeddings. The corpus per signal is small (dozens of cases -> low hundreds of chunks), so
an external vector DB is unnecessary overhead for this prototype (see Out of scope)."""
from __future__ import annotations

import numpy as np

from backend.db import cursor, dumps, fetchall, fetchone, loads


def add_chunk(
    chunk_id: str, investigation_id: str, report_id: str | None, chunk_type: str,
    text: str, char_start: int | None, char_end: int | None, granularity: str,
    embedding: list[float],
) -> None:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO kb_chunks
                (chunk_id, investigation_id, report_id, chunk_type, text, char_start, char_end,
                 granularity, embedding_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (chunk_id, investigation_id, report_id, chunk_type, text, char_start, char_end,
             granularity, dumps(embedding)),
        )


def clear_investigation_kb(investigation_id: str) -> None:
    with cursor() as cur:
        cur.execute("DELETE FROM kb_chunks WHERE investigation_id = ?", (investigation_id,))


def _cosine_sim(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    m_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    return m_norm @ q_norm


def _load_granularity(investigation_id: str, granularity: str) -> list[dict]:
    rows = fetchall(
        "SELECT * FROM kb_chunks WHERE investigation_id = ? AND granularity = ?",
        (investigation_id, granularity),
    )
    out = []
    for r in rows:
        d = dict(r)
        d["embedding"] = loads(d.pop("embedding_json"))
        out.append(d)
    return out


def top_k_by_similarity(chunks: list[dict], query_embedding: list[float], k: int) -> list[dict]:
    if not chunks:
        return []
    matrix = np.array([c["embedding"] for c in chunks], dtype=np.float32)
    query_vec = np.array(query_embedding, dtype=np.float32)
    sims = _cosine_sim(query_vec, matrix)
    order = np.argsort(-sims)[:k]
    results = []
    for i in order:
        c = dict(chunks[int(i)])
        c["score"] = float(sims[int(i)])
        c.pop("embedding", None)
        results.append(c)
    return results


def retrieve(investigation_id: str, query_embedding: list[float], top_cases: int = 5,
             top_chunks: int = 8) -> list[dict]:
    """Requirement 12.3: summary vectors select cases first, then chunk vectors within
    those cases (plus any investigation-level stat chunks) provide fine-grained evidence."""
    summaries = _load_granularity(investigation_id, "summary")
    top_case_summaries = top_k_by_similarity(summaries, query_embedding, top_cases)
    selected_report_ids = {c["report_id"] for c in top_case_summaries if c.get("report_id")}

    all_chunks = _load_granularity(investigation_id, "chunk")
    scoped_chunks = [
        c for c in all_chunks
        if c.get("report_id") in selected_report_ids or c.get("report_id") is None
    ]
    return top_k_by_similarity(scoped_chunks, query_embedding, top_chunks)


def get_chunk_by_id(chunk_id: str) -> dict | None:
    row = fetchone("SELECT * FROM kb_chunks WHERE chunk_id = ?", (chunk_id,))
    if row is None:
        return None
    d = dict(row)
    d.pop("embedding_json", None)
    return d
