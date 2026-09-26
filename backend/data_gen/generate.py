"""Requirement 1: reproducible synthetic FAERS-style dataset generator."""
from __future__ import annotations

import random
from datetime import date, timedelta

from backend.data_gen.narrative import build_narrative
from backend.data_gen.vocab import (
    ALL_EVENTS, BACKGROUND_EVENTS, COUNTRIES, DRUGS, SERIOUSNESS_VALUES,
    SEX_VALUES, SIGNAL_DRUG_CONFOUNDED, SIGNAL_DRUG_TRUE, SIGNAL_EVENT_CONFOUNDED,
    SIGNAL_EVENT_TRUE,
)

START_DATE = date(2022, 1, 1)
END_DATE = date(2024, 12, 31)

N_TRUE_SIGNAL_CASES = 26
N_CONFOUNDED_SIGNAL_CASES = 23
N_BASELINE_TRUE_EVENT_ELSEWHERE = 5
N_BASELINE_CONFOUNDED_EVENT_ELSEWHERE = 6


def _random_date(rng: random.Random) -> str:
    span = (END_DATE - START_DATE).days
    return (START_DATE + timedelta(days=rng.randint(0, span))).isoformat()


def _base_fields(rng: random.Random, idx: int) -> dict:
    return {
        "report_id": f"RPT-{idx:05d}",
        "age": rng.randint(18, 90),
        "sex": rng.choice(SEX_VALUES),
        "country": rng.choice(COUNTRIES),
        "received_date": _random_date(rng),
    }


def _make_true_signal_case(rng: random.Random, idx: int) -> dict:
    f = _base_fields(rng, idx)
    # Overwhelmingly strong causal pattern, with a small amount of realistic noise.
    roll = rng.random()
    if roll < 0.70:
        onset_days, dechallenge, rechallenge, confounder = rng.randint(1, 10), "positive", (
            "positive" if rng.random() < 0.35 else "not_mentioned"
        ), "none"
        seriousness = rng.choice(["Serious", "Serious - Life-threatening"])
    elif roll < 0.90:
        onset_days, dechallenge, rechallenge, confounder = rng.randint(3, 21), "positive", "not_mentioned", "minor"
        seriousness = rng.choice(SERIOUSNESS_VALUES)
    else:
        onset_days, dechallenge, rechallenge, confounder = None, "not_done", "not_mentioned", "minor"
        seriousness = rng.choice(SERIOUSNESS_VALUES)
    narrative = build_narrative(
        rng, age=f["age"], sex=f["sex"], drug=SIGNAL_DRUG_TRUE, event=SIGNAL_EVENT_TRUE,
        onset_days=onset_days, dechallenge=dechallenge, rechallenge=rechallenge,
        confounder_kind=confounder,
    )
    return {
        **f, "drug": SIGNAL_DRUG_TRUE, "event": SIGNAL_EVENT_TRUE, "seriousness": seriousness,
        "narrative": narrative, "is_planted_true_signal": 1, "is_planted_confounded_signal": 0,
    }


def _make_confounded_signal_case(rng: random.Random, idx: int) -> dict:
    f = _base_fields(rng, idx)
    # Statistically disproportionate volume, but narratives dominated by alternative causes.
    roll = rng.random()
    if roll < 0.75:
        onset_days = rng.choice([None, rng.randint(45, 200)])
        dechallenge = rng.choice(["not_done", "negative", "unknown"])
        confounder = "major"
    else:
        onset_days = rng.randint(10, 40)
        dechallenge = rng.choice(["negative", "not_done"])
        confounder = "major"
    narrative = build_narrative(
        rng, age=f["age"], sex=f["sex"], drug=SIGNAL_DRUG_CONFOUNDED, event=SIGNAL_EVENT_CONFOUNDED,
        onset_days=onset_days, dechallenge=dechallenge, rechallenge="not_mentioned",
        confounder_kind=confounder,
    )
    return {
        **f, "drug": SIGNAL_DRUG_CONFOUNDED, "event": SIGNAL_EVENT_CONFOUNDED,
        "seriousness": rng.choice(SERIOUSNESS_VALUES),
        "narrative": narrative, "is_planted_true_signal": 0, "is_planted_confounded_signal": 1,
    }


def _make_background_case(rng: random.Random, idx: int, drug: str, event: str) -> dict:
    f = _base_fields(rng, idx)
    onset_days = rng.choice([None, None, rng.randint(1, 120)])
    dechallenge = rng.choice(["unknown", "unknown", "not_done", "positive", "negative"])
    rechallenge = "not_mentioned"
    confounder = rng.choice(["none", "none", "minor", "minor", "major"])
    narrative = build_narrative(
        rng, age=f["age"], sex=f["sex"], drug=drug, event=event, onset_days=onset_days,
        dechallenge=dechallenge, rechallenge=rechallenge, confounder_kind=confounder,
    )
    return {
        **f, "drug": drug, "event": event, "seriousness": rng.choice(SERIOUSNESS_VALUES),
        "narrative": narrative, "is_planted_true_signal": 0, "is_planted_confounded_signal": 0,
    }


def generate_reports(seed: int, size: int) -> list[dict]:
    rng = random.Random(seed)
    reports: list[dict] = []
    idx = 1

    for _ in range(N_TRUE_SIGNAL_CASES):
        reports.append(_make_true_signal_case(rng, idx)); idx += 1
    for _ in range(N_CONFOUNDED_SIGNAL_CASES):
        reports.append(_make_confounded_signal_case(rng, idx)); idx += 1

    other_drugs = [d for d in DRUGS if d != SIGNAL_DRUG_TRUE]
    for _ in range(N_BASELINE_TRUE_EVENT_ELSEWHERE):
        d = rng.choice(other_drugs)
        reports.append(_make_background_case(rng, idx, d, SIGNAL_EVENT_TRUE)); idx += 1

    other_drugs2 = [d for d in DRUGS if d != SIGNAL_DRUG_CONFOUNDED]
    for _ in range(N_BASELINE_CONFOUNDED_EVENT_ELSEWHERE):
        d = rng.choice(other_drugs2)
        reports.append(_make_background_case(rng, idx, d, SIGNAL_EVENT_CONFOUNDED)); idx += 1

    remaining = max(0, size - len(reports))
    for _ in range(remaining):
        d = rng.choice(DRUGS)
        e = rng.choice(BACKGROUND_EVENTS)
        reports.append(_make_background_case(rng, idx, d, e)); idx += 1

    rng.shuffle(reports)
    return reports
