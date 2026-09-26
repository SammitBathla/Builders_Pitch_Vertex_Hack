def _fake_extract_many(reports, max_workers=12, prompt_version="extract-v1"):
    from backend.llm.extraction import ExtractionRecord
    from backend.data_gen.vocab import SIGNAL_DRUG_TRUE, SIGNAL_EVENT_TRUE
    out = []
    for r in reports:
        if r["drug"] == SIGNAL_DRUG_TRUE and r["event"] == SIGNAL_EVENT_TRUE:
            out.append(ExtractionRecord(
                report_id=r["report_id"], model_id="fake-model", prompt_version=prompt_version,
                schema_valid=True, extraction_failed=False, failure_reason=None,
                time_to_onset_days=3, onset_order="after_drug_start", dechallenge="positive",
                rechallenge="not_done", confounders=[], data_gaps=[],
                facts=[{"field": "dechallenge", "value": "positive", "quote": "x", "verified": True,
                        "char_start": 0, "char_end": 1}],
                quotes_verified=3, quotes_rejected=0, cache_hit=False, cache_key="k1",
            ))
        else:
            out.append(ExtractionRecord(
                report_id=r["report_id"], model_id="fake-model", prompt_version=prompt_version,
                schema_valid=True, extraction_failed=False, failure_reason=None,
                time_to_onset_days=None, onset_order="unclear", dechallenge="unknown",
                rechallenge="unknown", confounders=[{"text": "renal disease", "quote": "x"}],
                data_gaps=["no labs"], facts=[], quotes_verified=1, quotes_rejected=0,
                cache_hit=False, cache_key="k2",
            ))
    return out


def test_full_investigation_flow(fresh_db, monkeypatch):
    from backend.data_gen.seed import seed_database
    seed_database()

    import backend.services.investigation as svc
    from backend.data_gen.vocab import SIGNAL_DRUG_TRUE, SIGNAL_EVENT_TRUE

    monkeypatch.setattr(svc, "extract_many", _fake_extract_many)
    monkeypatch.setattr(svc, "build_kb", lambda *a, **k: {"chunks_built": 0, "embedding_failures": 0})

    signals = svc.list_flagged_signals()
    assert any(s["drug"] == SIGNAL_DRUG_TRUE and s["event"] == SIGNAL_EVENT_TRUE for s in signals)

    inv = svc.create_investigation(SIGNAL_DRUG_TRUE, SIGNAL_EVENT_TRUE, actor="tester")
    assert inv["status"] == "in_progress"
    assert len(inv["cases"]) >= 3
    assert inv["recommendation"]["recommendation"].startswith("Validated")
    for c in inv["cases"]:
        assert c["causality"]["category"] == "Probable"

    # Override one case and confirm recommendation recomputes.
    first_report_id = inv["cases"][0]["report"]["report_id"]
    updated = svc.override_case(inv["investigation_id"], first_report_id, "Unlikely",
                                 "Reviewer judged confounder significant", "dr.reviewer")
    overridden_case = next(c for c in updated["cases"] if c["report"]["report_id"] == first_report_id)
    assert overridden_case["causality"]["category"] == "Unlikely"
    assert overridden_case["causality"]["source"] == "override"
    assert overridden_case["causality"]["override_reason"]

    # Sign-off requires a summary first.
    try:
        svc.sign_off(inv["investigation_id"], "Dr. Smith", "accept_recommendation", None)
        assert False, "should have raised"
    except ValueError:
        pass

    with_summary = svc.edit_summary(inv["investigation_id"], "Manually written summary text.", "dr.reviewer")
    assert with_summary["summary_final"] == "Manually written summary text."

    signed = svc.sign_off(inv["investigation_id"], "Dr. Smith", "accept_recommendation", None)
    assert signed["status"] == "signed_off"
    assert signed["signed_off_by"] == "Dr. Smith"

    from backend.audit.trail import verify_chain
    result = verify_chain()
    assert result["valid"] is True

    metrics = svc.compute_metrics(inv["investigation_id"])
    assert metrics["cases_processed"] == len(inv["cases"])
