import tempfile
from pathlib import Path

import backend.db as db_module
from backend.config import get_settings


def _fresh_db(tmp_path):
    get_settings.cache_clear()
    import os
    os.environ["DATA_DIR"] = str(tmp_path)
    db_module._conn = None
    return db_module.get_connection()


def test_hash_chain_valid_after_appends(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    db_module._conn = None
    db_module.get_connection()

    from backend.audit.trail import append_event, verify_chain

    append_event("extraction", {"report_id": "RPT-1"}, investigation_id="INV-1")
    append_event("rule_evaluation", {"report_id": "RPT-1", "category": "Certain"}, investigation_id="INV-1")
    append_event("override", {"report_id": "RPT-1", "reason": "clinician judgement"}, investigation_id="INV-1")

    result = verify_chain()
    assert result["valid"] is True
    assert result["total_events"] == 3


def test_hash_chain_detects_tamper(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    db_module._conn = None
    conn = db_module.get_connection()

    from backend.audit.trail import append_event, verify_chain

    append_event("extraction", {"report_id": "RPT-1"}, investigation_id="INV-1")
    append_event("sign_off", {"actor": "reviewer1"}, investigation_id="INV-1")

    # Tamper with the first event's payload directly in the DB.
    conn.execute("UPDATE audit_log SET payload_json = '{\"report_id\": \"HACKED\"}' WHERE seq = 1")
    conn.commit()

    result = verify_chain()
    assert result["valid"] is False
    assert result["broken_at_seq"] == 1
