"""Loads the generated dataset into Postgres, once, deterministically."""
from __future__ import annotations

from backend.config import get_settings
from backend.data_gen.generate import generate_reports
from backend.db import cursor, fetchone, insert_many

_COLUMNS = [
    "report_id", "drug", "event", "age", "sex", "seriousness", "country",
    "received_date", "narrative", "is_planted_true_signal", "is_planted_confounded_signal",
]


def reports_count() -> int:
    row = fetchone("SELECT COUNT(*) AS n FROM reports")
    return row["n"]


def seed_database(force: bool = False) -> int:
    """Populate the reports table if empty (or always, if force=True). Returns row count."""
    if not force and reports_count() > 0:
        return reports_count()

    if force:
        with cursor() as cur:
            cur.execute("DELETE FROM reports")

    settings = get_settings()
    reports = generate_reports(settings.dataset_seed, settings.dataset_size)

    # One multi-row INSERT (one round trip) instead of one INSERT per report — matters a
    # lot against a remote Postgres; this is the dominant cost of a first-ever app startup.
    rows = [tuple(r[c] for c in _COLUMNS) for r in reports]
    insert_many("reports", _COLUMNS, rows)
    return len(reports)
