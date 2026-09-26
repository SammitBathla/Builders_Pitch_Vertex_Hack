import backend.db as db_module


def test_hash_chain_valid_after_appends(fresh_db):
    from backend.audit.trail import append_event, verify_chain

    append_event("extraction", {"report_id": "RPT-1"}, investigation_id="INV-1")
    append_event("rule_evaluation", {"report_id": "RPT-1", "category": "Certain"}, investigation_id="INV-1")
    append_event("override", {"report_id": "RPT-1", "reason": "clinician judgement"}, investigation_id="INV-1")

    result = verify_chain()
    assert result["valid"] is True
    assert result["total_events"] == 3


def test_hash_chain_detects_tamper(fresh_db):
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
