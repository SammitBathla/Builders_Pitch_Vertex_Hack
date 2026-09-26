"""Requirement 6: deterministic, versioned signal recommendation.

Combines the (already-deterministic) disproportionality statistics with the causality
category distribution across the signal's cases. Pure function — recomputed from scratch
whenever a case is overridden (Requirement 6.2), never mutated in place.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

RULESET_VERSION = "recommendation-v1"

# Thresholds (documented so they can be surfaced verbatim — Requirement 6.3)
SUPPORTIVE_CATEGORIES = ("Certain", "Probable")
UNSUPPORTIVE_CATEGORIES = ("Unlikely",)
SUPPORTIVE_FRACTION_THRESHOLD = 0.5
UNSUPPORTIVE_FRACTION_THRESHOLD = 0.5
UNASSESSABLE_FRACTION_THRESHOLD = 0.4


@dataclass(frozen=True)
class RecommendationResult:
    recommendation: str
    rule_id: str
    ruleset_version: str
    thresholds: dict
    explanation: str
    causality_counts: dict
    supportive_fraction: float
    unsupportive_fraction: float
    unassessable_fraction: float


def compute_recommendation(is_statistical_signal: bool, causality_categories: list[str]) -> RecommendationResult:
    thresholds = {
        "supportive_fraction_threshold": SUPPORTIVE_FRACTION_THRESHOLD,
        "unsupportive_fraction_threshold": UNSUPPORTIVE_FRACTION_THRESHOLD,
        "unassessable_fraction_threshold": UNASSESSABLE_FRACTION_THRESHOLD,
        "supportive_categories": list(SUPPORTIVE_CATEGORIES),
        "unsupportive_categories": list(UNSUPPORTIVE_CATEGORIES),
    }

    counts = Counter(causality_categories)
    total = len(causality_categories)
    if total == 0:
        return RecommendationResult(
            "Insufficient information – request follow-up", "REC0-no-cases", RULESET_VERSION,
            thresholds, "No cases have been assessed yet.", dict(counts), 0.0, 0.0, 0.0,
        )

    supportive = sum(counts[c] for c in SUPPORTIVE_CATEGORIES)
    unsupportive = sum(counts[c] for c in UNSUPPORTIVE_CATEGORIES)
    unassessable = counts.get("Unassessable", 0)

    supportive_fraction = supportive / total
    unsupportive_fraction = unsupportive / total
    unassessable_fraction = unassessable / total

    if not is_statistical_signal:
        return RecommendationResult(
            "Not confirmed – confounded, continue monitoring", "REC1-not-statistical-signal",
            RULESET_VERSION, thresholds,
            "The drug-event pair does not meet the Evans disproportionality criteria, "
            "regardless of case-level causality.",
            dict(counts), supportive_fraction, unsupportive_fraction, unassessable_fraction,
        )

    if unassessable_fraction >= UNASSESSABLE_FRACTION_THRESHOLD:
        return RecommendationResult(
            "Insufficient information – request follow-up", "REC2-insufficient-data",
            RULESET_VERSION, thresholds,
            f"{unassessable_fraction:.0%} of cases could not be assessed for causality "
            f"(>= {UNASSESSABLE_FRACTION_THRESHOLD:.0%} threshold); more case follow-up is "
            "needed before a conclusion can be drawn.",
            dict(counts), supportive_fraction, unsupportive_fraction, unassessable_fraction,
        )

    if is_statistical_signal and supportive_fraction >= SUPPORTIVE_FRACTION_THRESHOLD:
        return RecommendationResult(
            "Validated – escalate to Safety Review Committee", "REC3-validated",
            RULESET_VERSION, thresholds,
            f"The pair meets the Evans statistical signal criteria and {supportive_fraction:.0%} "
            f"of assessed cases are Certain or Probable (>= {SUPPORTIVE_FRACTION_THRESHOLD:.0%} "
            "threshold).",
            dict(counts), supportive_fraction, unsupportive_fraction, unassessable_fraction,
        )

    if unsupportive_fraction >= UNSUPPORTIVE_FRACTION_THRESHOLD:
        return RecommendationResult(
            "Not confirmed – confounded, continue monitoring", "REC4-confounded",
            RULESET_VERSION, thresholds,
            f"Although the pair is a statistical signal, {unsupportive_fraction:.0%} of "
            f"assessed cases are Unlikely (>= {UNSUPPORTIVE_FRACTION_THRESHOLD:.0%} threshold), "
            "indicating the statistical excess is likely explained by confounding.",
            dict(counts), supportive_fraction, unsupportive_fraction, unassessable_fraction,
        )

    return RecommendationResult(
        "Insufficient information – request follow-up", "REC5-mixed-inconclusive",
        RULESET_VERSION, thresholds,
        "The statistical signal is not clearly supported or refuted by case-level causality "
        "(no threshold was decisively met); further review is recommended.",
        dict(counts), supportive_fraction, unsupportive_fraction, unassessable_fraction,
    )
