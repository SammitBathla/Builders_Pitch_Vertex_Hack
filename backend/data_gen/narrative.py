"""Free-text narrative construction.

Requirement 1.3: onset timing, dechallenge, rechallenge and confounders must exist ONLY
in this prose, never as separate structured fields — extraction has to actually read it.
"""
from __future__ import annotations

import random

from backend.data_gen.vocab import ALTERNATIVE_CAUSES, MINOR_CONFOUNDERS


def _onset_phrase(rng: random.Random, days: int | None) -> str:
    if days is None:
        return rng.choice([
            "The precise date of onset relative to starting the drug was not documented.",
            "Onset timing was not clearly reported by the patient.",
        ])
    if days <= 1:
        return f"Symptoms began the day after the first dose."
    if days <= 14:
        return f"Symptoms began approximately {days} days after starting the drug."
    if days <= 60:
        weeks = days // 7
        return f"Symptoms began approximately {weeks} weeks after starting the drug."
    months = max(1, days // 30)
    return f"Symptoms began approximately {months} months after starting the drug, following a long period of uneventful use."


def _dechallenge_phrase(rng: random.Random, result: str) -> str:
    if result == "positive":
        return rng.choice([
            "The drug was discontinued and the event resolved within days.",
            "Treatment was stopped, after which the patient's condition improved steadily.",
            "Following discontinuation of the drug, laboratory values normalised over the following week.",
        ])
    if result == "negative":
        return rng.choice([
            "The drug was discontinued, but the event did not improve and followed its own course.",
            "Treatment was stopped; however, symptoms persisted unchanged for several weeks afterward.",
        ])
    if result == "not_done":
        return rng.choice([
            "The drug was continued unchanged and the patient was managed supportively.",
            "The reporting physician did not discontinue the drug.",
        ])
    return "It is not documented whether the drug was discontinued."


def _rechallenge_phrase(rng: random.Random, result: str) -> str:
    if result == "positive":
        return rng.choice([
            "The patient was later inadvertently re-exposed to the same drug, and the event recurred within days.",
            "On rechallenge some months later, the same reaction reappeared promptly.",
        ])
    if result == "negative":
        return "The drug was reintroduced at a later date and the event did not recur."
    return ""  # most reports simply don't mention rechallenge


def _confounder_phrase(rng: random.Random, kind: str) -> str:
    if kind == "major":
        cause = rng.choice(ALTERNATIVE_CAUSES)
        return f"Of note, the patient had {cause}, which the reporting clinician noted as a possible alternative explanation."
    if kind == "minor":
        return f"Past medical history was notable for {rng.choice(MINOR_CONFOUNDERS)}."
    return "No confounding medications or comorbidities were reported."


def build_narrative(
    rng: random.Random,
    *,
    age: int,
    sex: str,
    drug: str,
    event: str,
    onset_days: int | None,
    dechallenge: str,
    rechallenge: str,
    confounder_kind: str,
    extra_notes: str | None = None,
) -> str:
    sex_word = {"Female": "female", "Male": "male", "Unknown": "patient of unspecified sex"}[sex]
    opening = rng.choice([
        f"A {age}-year-old {sex_word} was started on {drug} and subsequently developed {event.lower()}.",
        f"This {age}-year-old {sex_word} patient reported {event.lower()} while receiving {drug}.",
        f"Case concerns a {age}-year-old {sex_word} treated with {drug} who experienced {event.lower()}.",
    ])
    parts = [opening, _onset_phrase(rng, onset_days), _dechallenge_phrase(rng, dechallenge)]
    rech = _rechallenge_phrase(rng, rechallenge)
    if rech:
        parts.append(rech)
    parts.append(_confounder_phrase(rng, confounder_kind))
    if extra_notes:
        parts.append(extra_notes)
    parts.append(rng.choice([
        "The reporter classified the case as noted above.",
        "Follow-up information was requested from the reporting physician.",
        "No additional information was available at the time of this report.",
    ]))
    return " ".join(parts)
