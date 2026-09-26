"""Requirement 5: deterministic, versioned causality assignment.

A simplified, WHO-UMC-inspired rule set (Assumption A3 — not a validated clinical
algorithm). Pure functions only: given the same verified facts, the same category, rule ID
and explanation are produced every time. No LLM involvement (Requirement 5.3).

Rules are evaluated in priority order; the first rule whose condition holds wins. Every
rule records which facts it fired on, in plain language, for Requirement 5.2.
"""
from __future__ import annotations

from dataclasses import dataclass

RULESET_VERSION = "causality-v1"

CATEGORIES = ["Certain", "Probable", "Possible", "Unlikely", "Unassessable"]


@dataclass(frozen=True)
class CaseFacts:
    """Only VERIFIED facts should ever reach this rule engine (Requirement 4.6 downgrades
    unverified quotes to 'unknown' before this point)."""
    time_to_onset_days: int | None
    onset_order: str  # "after_drug_start" | "before_drug_start" | "unclear"
    dechallenge: str  # "positive" | "negative" | "not_done" | "unknown"
    rechallenge: str  # "positive" | "negative" | "not_done" | "unknown"
    has_confounders: bool


@dataclass(frozen=True)
class CausalityResult:
    category: str
    rule_id: str
    ruleset_version: str
    explanation: str


def assign_causality(facts: CaseFacts) -> CausalityResult:
    onset_known = facts.onset_order != "unclear" or facts.time_to_onset_days is not None
    dechallenge_known = facts.dechallenge in ("positive", "negative")
    rechallenge_positive = facts.rechallenge == "positive"

    # R1 — implausible temporal relationship rules the drug out regardless of other facts.
    if facts.onset_order == "before_drug_start":
        return CausalityResult(
            "Unlikely", "R1-temporal-implausible", RULESET_VERSION,
            "Event onset was reported as occurring before the drug was started, which is "
            "temporally implausible for a causal relationship.",
        )

    # R2 — essentially no usable information at all.
    if not onset_known and facts.dechallenge == "unknown" and facts.rechallenge in ("unknown", "not_done"):
        return CausalityResult(
            "Unassessable", "R2-insufficient-data", RULESET_VERSION,
            "Onset timing, dechallenge and rechallenge are all unknown or undocumented; "
            "there are not enough verified facts to assess causality.",
        )

    # R3 — the strongest evidence: plausible timing, positive dechallenge, positive
    # rechallenge, and no stated alternative cause.
    if (
        facts.onset_order == "after_drug_start"
        and facts.dechallenge == "positive"
        and rechallenge_positive
        and not facts.has_confounders
    ):
        return CausalityResult(
            "Certain", "R3-certain", RULESET_VERSION,
            "Onset followed drug initiation, the event resolved on dechallenge, it recurred "
            "on rechallenge, and no alternative cause was documented.",
        )

    # R4 — plausible timing, positive dechallenge, no rechallenge information, no confounders.
    if (
        facts.onset_order == "after_drug_start"
        and facts.dechallenge == "positive"
        and not facts.has_confounders
    ):
        return CausalityResult(
            "Probable", "R4-probable", RULESET_VERSION,
            "Onset followed drug initiation and the event resolved on dechallenge, with no "
            "alternative cause documented (rechallenge not performed or not reported).",
        )

    # R5 — plausible timing but either dechallenge is inconclusive or a confounder exists.
    if facts.onset_order == "after_drug_start" and (
        facts.dechallenge in ("not_done", "unknown") or facts.has_confounders
    ) and facts.dechallenge != "negative":
        reason_bits = []
        if facts.dechallenge in ("not_done", "unknown"):
            reason_bits.append("dechallenge was not performed or not documented")
        if facts.has_confounders:
            reason_bits.append("an alternative cause/confounder was documented")
        return CausalityResult(
            "Possible", "R5-possible", RULESET_VERSION,
            "Onset followed drug initiation, but " + " and ".join(reason_bits) + ", so "
            "causality cannot be more strongly supported.",
        )

    # R6 — negative dechallenge (event persisted despite stopping the drug) or a confounder
    # combined with anything less than a clean plausible/positive pattern.
    if facts.dechallenge == "negative" or facts.has_confounders:
        reason_bits = []
        if facts.dechallenge == "negative":
            reason_bits.append("the event did not resolve after the drug was stopped")
        if facts.has_confounders:
            reason_bits.append("an alternative cause/confounder was documented")
        return CausalityResult(
            "Unlikely", "R6-unlikely", RULESET_VERSION,
            "; ".join(reason_bits).capitalize() + ", weighing against a causal relationship.",
        )

    # R7 — fallback: unclear onset order with no other disqualifying or supporting facts.
    return CausalityResult(
        "Unassessable", "R7-fallback-insufficient-data", RULESET_VERSION,
        "The verified facts do not clearly establish a temporal pattern or dechallenge "
        "outcome sufficient to assign a more specific causality category.",
    )
