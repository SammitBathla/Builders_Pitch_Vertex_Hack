from backend.rules.causality import assign_causality, CaseFacts
from backend.rules.recommendation import compute_recommendation


def test_causality_certain():
    f = CaseFacts(time_to_onset_days=3, onset_order="after_drug_start", dechallenge="positive",
                  rechallenge="positive", has_confounders=False)
    r = assign_causality(f)
    assert r.category == "Certain"
    assert r.rule_id == "R3-certain"


def test_causality_deterministic():
    f = CaseFacts(time_to_onset_days=3, onset_order="after_drug_start", dechallenge="positive",
                  rechallenge="not_done", has_confounders=False)
    r1 = assign_causality(f)
    r2 = assign_causality(f)
    assert r1 == r2
    assert r1.category == "Probable"


def test_causality_implausible_temporal_is_unlikely():
    f = CaseFacts(time_to_onset_days=None, onset_order="before_drug_start", dechallenge="unknown",
                  rechallenge="unknown", has_confounders=False)
    assert assign_causality(f).category == "Unlikely"


def test_causality_no_data_unassessable():
    f = CaseFacts(time_to_onset_days=None, onset_order="unclear", dechallenge="unknown",
                  rechallenge="unknown", has_confounders=False)
    assert assign_causality(f).category == "Unassessable"


def test_causality_confounder_pulls_to_possible_or_unlikely():
    f = CaseFacts(time_to_onset_days=10, onset_order="after_drug_start", dechallenge="not_done",
                  rechallenge="unknown", has_confounders=True)
    assert assign_causality(f).category == "Possible"


def test_recommendation_validated():
    cats = ["Certain"] * 6 + ["Probable"] * 4 + ["Possible"] * 2
    r = compute_recommendation(True, cats)
    assert r.recommendation.startswith("Validated")


def test_recommendation_confounded():
    cats = ["Unlikely"] * 8 + ["Possible"] * 2
    r = compute_recommendation(True, cats)
    assert r.recommendation.startswith("Not confirmed")


def test_recommendation_not_statistical_signal_short_circuits():
    cats = ["Certain"] * 10
    r = compute_recommendation(False, cats)
    assert r.recommendation.startswith("Not confirmed")


def test_recommendation_insufficient_info():
    cats = ["Unassessable"] * 5 + ["Possible"] * 2
    r = compute_recommendation(True, cats)
    assert r.recommendation.startswith("Insufficient")
