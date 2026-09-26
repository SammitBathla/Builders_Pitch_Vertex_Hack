from backend.data_gen.generate import generate_reports
from backend.data_gen.vocab import (
    SIGNAL_DRUG_TRUE, SIGNAL_EVENT_TRUE, SIGNAL_DRUG_CONFOUNDED, SIGNAL_EVENT_CONFOUNDED,
)
from backend.stats.disproportionality import compute_signal_stats


def test_reproducible_with_fixed_seed():
    a = generate_reports(42, 500)
    b = generate_reports(42, 500)
    assert a == b


def test_different_seed_differs():
    a = generate_reports(42, 500)
    b = generate_reports(43, 500)
    assert a != b


def test_at_least_1000_reports_default_size():
    reports = generate_reports(42, 1000)
    assert len(reports) >= 1000


def test_true_signal_planted_and_flagged():
    reports = generate_reports(42, 1000)
    s = compute_signal_stats(reports, SIGNAL_DRUG_TRUE, SIGNAL_EVENT_TRUE)
    assert s.a >= 3
    assert s.is_signal is True


def test_confounded_signal_planted_and_statistically_flagged():
    reports = generate_reports(42, 1000)
    s = compute_signal_stats(reports, SIGNAL_DRUG_CONFOUNDED, SIGNAL_EVENT_CONFOUNDED)
    assert s.a >= 3
    assert s.is_signal is True  # statistically flagged despite being confounded


def test_causal_features_not_in_structured_fields():
    reports = generate_reports(42, 200)
    structured_keys = {
        "report_id", "drug", "event", "age", "sex", "seriousness", "country",
        "received_date", "narrative", "is_planted_true_signal", "is_planted_confounded_signal",
    }
    for r in reports:
        assert set(r.keys()) == structured_keys
    # onset/dechallenge/rechallenge/confounder vocabulary only appears in narrative text
    for r in reports[:5]:
        assert isinstance(r["narrative"], str) and len(r["narrative"]) > 20
