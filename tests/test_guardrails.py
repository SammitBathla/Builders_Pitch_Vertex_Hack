from backend.guardrails.verify import verify_quote, verify_case_ids


def test_exact_substring_verified_with_offsets():
    narrative = "Symptoms began 3 days after starting the drug. The drug was stopped."
    v = verify_quote(narrative, "3 days after starting the drug")
    assert v.verified is True
    assert narrative[v.char_start:v.char_end] == "3 days after starting the drug"


def test_whitespace_normalised_match():
    narrative = "The drug   was\ndiscontinued and symptoms resolved."
    v = verify_quote(narrative, "The drug was discontinued")
    assert v.verified is True


def test_hallucinated_quote_rejected():
    narrative = "Symptoms began 3 days after starting the drug."
    v = verify_quote(narrative, "the patient died immediately")
    assert v.verified is False
    assert v.char_start is None


def test_case_id_citation_check():
    valid, invalid = verify_case_ids(["RPT-1", "RPT-2", "RPT-999"], {"RPT-1", "RPT-2", "RPT-3"})
    assert valid == ["RPT-1", "RPT-2"]
    assert invalid == ["RPT-999"]
