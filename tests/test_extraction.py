import backend.db as db_module
from backend.config import get_settings


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    db_module._conn = None
    db_module.get_connection()


def test_valid_extraction_verifies_quotes_and_downgrades_bad_ones(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    import backend.llm.extraction as ext

    narrative = ("A 40-year-old female was started on Zentrivex and developed acute hepatic "
                 "failure. Symptoms began 3 days after starting the drug. The drug was "
                 "discontinued and the event resolved within days.")
    report = {"report_id": "RPT-00001", "drug": "Zentrivex", "event": "Acute Hepatic Failure",
              "narrative": narrative}

    fake_raw = {
        "time_to_onset_days": 3,
        "time_to_onset_quote": "3 days after starting the drug",
        "onset_order": "after_drug_start",
        "onset_order_quote": "Symptoms began 3 days after starting the drug",
        "dechallenge": "positive",
        "dechallenge_quote": "discontinued and the event resolved within days",
        "rechallenge": "unknown",
        "rechallenge_quote": None,
        "confounders": [
            {"text": "fabricated confounder", "quote": "this text does not appear anywhere"},
        ],
        "data_gaps": ["no lab values reported"],
    }

    monkeypatch.setattr(ext, "_call_llm_raw", lambda *a, **k: fake_raw)

    record = ext.extract_one(report)
    assert record.schema_valid is True
    assert record.extraction_failed is False
    assert record.time_to_onset_days == 3
    assert record.dechallenge == "positive"
    # The fabricated confounder quote does not exist in the narrative -> must be rejected.
    assert record.confounders == []
    assert record.quotes_rejected >= 1
    assert record.cache_hit is False

    # Second call with same narrative/model/prompt should hit cache, no new "LLM call".
    monkeypatch.setattr(ext, "_call_llm_raw", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not be called")))
    record2 = ext.extract_one(report)
    assert record2.cache_hit is True
    assert record2.time_to_onset_days == 3


def test_schema_invalid_output_is_extraction_failure_not_coerced(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    import backend.llm.extraction as ext

    report = {"report_id": "RPT-00002", "drug": "Zentrivex", "event": "Acute Hepatic Failure",
              "narrative": "Some narrative text."}

    bad_raw = {"onset_order": "sideways", "dechallenge": "positive", "rechallenge": "unknown",
               "confounders": [], "data_gaps": []}  # invalid enum value, missing required fields

    monkeypatch.setattr(ext, "_call_llm_raw", lambda *a, **k: bad_raw)

    record = ext.extract_one(report)
    assert record.schema_valid is False
    assert record.extraction_failed is True
    assert record.failure_reason is not None


def test_bedrock_unreachable_is_visible_failure_not_silent(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    import backend.llm.extraction as ext
    from backend.llm.bedrock_client import BedrockUnavailableError

    report = {"report_id": "RPT-00003", "drug": "Zentrivex", "event": "Acute Hepatic Failure",
              "narrative": "Some narrative text."}

    def boom(*a, **k):
        raise BedrockUnavailableError("network down")

    monkeypatch.setattr(ext, "_call_llm_raw", boom)
    record = ext.extract_one(report)
    assert record.extraction_failed is True
    assert "network down" in record.failure_reason
