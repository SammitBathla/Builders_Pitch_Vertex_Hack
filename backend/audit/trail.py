"""Requirement 9: tamper-evident audit trail.

Every AI call, rule evaluation, override and sign-off is appended as an event. Each event's
hash covers its own payload plus the previous event's hash, so any edit or deletion anywhere
in the chain is detectable by recomputing hashes forward (Requirement 9.2).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from backend.db import cursor, dumps, fetchall, insert_many, loads

GENESIS_HASH = "0" * 64


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def _row_hash(prev_hash: str, event_type: str, investigation_id: str | None, payload_json: str,
              actor: str | None, model_id: str | None, prompt_version: str | None,
              rule_version: str | None, timestamp: str) -> str:
    material = "|".join([
        prev_hash, event_type, investigation_id or "", payload_json, actor or "",
        model_id or "", prompt_version or "", rule_version or "", timestamp,
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def append_event(
    event_type: str,
    payload: dict,
    *,
    investigation_id: str | None = None,
    actor: str | None = "system",
    model_id: str | None = None,
    prompt_version: str | None = None,
    rule_version: str | None = None,
) -> dict:
    # The read of "last hash" and the insert of the new row must be atomic together, or two
    # concurrent appends (e.g. from parallel extraction-audit calls) could both read the same
    # prev_hash and corrupt the chain. `cursor()` holds the DB-wide lock for this whole block.
    with cursor() as cur:
        last = cur.execute("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = last["hash"] if last else GENESIS_HASH

        timestamp = datetime.now(timezone.utc).isoformat()
        payload_json = _canonical(payload)
        row_hash = _row_hash(
            prev_hash, event_type, investigation_id, payload_json, actor, model_id,
            prompt_version, rule_version, timestamp,
        )

        cur.execute(
            """
            INSERT INTO audit_log
                (event_type, investigation_id, payload_json, actor, model_id, prompt_version,
                 rule_version, timestamp, prev_hash, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING seq
            """,
            (event_type, investigation_id, payload_json, actor, model_id, prompt_version,
             rule_version, timestamp, prev_hash, row_hash),
        )
        seq = cur.fetchone()["seq"]

    return {
        "seq": seq, "event_type": event_type, "investigation_id": investigation_id,
        "payload": payload, "actor": actor, "model_id": model_id,
        "prompt_version": prompt_version, "rule_version": rule_version,
        "timestamp": timestamp, "prev_hash": prev_hash, "hash": row_hash,
    }


def append_events_batch(events: list[dict]) -> list[dict]:
    """Same guarantee as `append_event` (each event's hash covers the previous event's
    hash), but for N events in ONE round trip instead of N. Hash chaining is sequential by
    nature, but that sequencing only needs to happen once, in memory — the "read last
    hash, compute, write" pattern doesn't require a DB round trip between each step,
    because nothing else can be interleaved: `cursor()` (and the read of the starting
    prev_hash below) holds the DB-wide lock for the whole batch, same as a single append.

    Each dict in `events` needs: event_type, payload, and optionally investigation_id,
    actor, model_id, prompt_version, rule_version. Returns the same shape as
    `append_event`, one per input event, in order.
    """
    if not events:
        return []

    with cursor() as cur:
        last = cur.execute("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = last["hash"] if last else GENESIS_HASH

        rows = []
        results = []
        for e in events:
            event_type = e["event_type"]
            investigation_id = e.get("investigation_id")
            actor = e.get("actor", "system")
            model_id = e.get("model_id")
            prompt_version = e.get("prompt_version")
            rule_version = e.get("rule_version")
            timestamp = datetime.now(timezone.utc).isoformat()
            payload_json = _canonical(e["payload"])
            row_hash = _row_hash(
                prev_hash, event_type, investigation_id, payload_json, actor, model_id,
                prompt_version, rule_version, timestamp,
            )
            rows.append((event_type, investigation_id, payload_json, actor, model_id,
                         prompt_version, rule_version, timestamp, prev_hash, row_hash))
            results.append({
                "event_type": event_type, "investigation_id": investigation_id,
                "payload": e["payload"], "actor": actor, "model_id": model_id,
                "prompt_version": prompt_version, "rule_version": rule_version,
                "timestamp": timestamp, "prev_hash": prev_hash, "hash": row_hash,
            })
            prev_hash = row_hash

        col_ph = ", ".join(["%s"] * 10)
        values_clause = ", ".join([f"({col_ph})"] * len(rows))
        flat_params = tuple(v for row in rows for v in row)
        cur.execute(
            f"""INSERT INTO audit_log
                    (event_type, investigation_id, payload_json, actor, model_id,
                     prompt_version, rule_version, timestamp, prev_hash, hash)
                VALUES {values_clause}
                RETURNING seq""",
            flat_params,
        )
        seqs = [r["seq"] for r in cur.fetchall()]

    for result, seq in zip(results, seqs):
        result["seq"] = seq
    return results


def list_events(investigation_id: str | None = None) -> list[dict]:
    if investigation_id:
        rows = fetchall(
            "SELECT * FROM audit_log WHERE investigation_id = ? ORDER BY seq ASC",
            (investigation_id,),
        )
    else:
        rows = fetchall("SELECT * FROM audit_log ORDER BY seq ASC")
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = loads(d.pop("payload_json"))
        out.append(d)
    return out


def verify_chain() -> dict:
    """Requirement 9.2 — recompute every hash forward and report the first break, if any."""
    rows = fetchall("SELECT * FROM audit_log ORDER BY seq ASC")

    expected_prev = GENESIS_HASH
    for r in rows:
        d = dict(r)
        if d["prev_hash"] != expected_prev:
            return {"valid": False, "broken_at_seq": d["seq"], "reason": "prev_hash mismatch",
                    "events_checked": d["seq"] - 1, "total_events": len(rows)}
        recomputed = _row_hash(
            d["prev_hash"], d["event_type"], d["investigation_id"], d["payload_json"],
            d["actor"], d["model_id"], d["prompt_version"], d["rule_version"], d["timestamp"],
        )
        if recomputed != d["hash"]:
            return {"valid": False, "broken_at_seq": d["seq"], "reason": "hash mismatch (tampered payload)",
                    "events_checked": d["seq"] - 1, "total_events": len(rows)}
        expected_prev = d["hash"]

    return {"valid": True, "broken_at_seq": None, "reason": None,
            "events_checked": len(rows), "total_events": len(rows)}
