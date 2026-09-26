"""Requirement 2: deterministic disproportionality analysis. Pure functions only — no
LLM, no randomness, no hidden state. Identical input data always yields identical output.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from scipy import stats as scipy_stats

EVANS_MIN_PRR = 2.0
EVANS_MIN_CHI_SQUARE = 4.0
EVANS_MIN_CASES = 3


@dataclass(frozen=True)
class ContingencyTable:
    a: int  # drug of interest + event of interest
    b: int  # drug of interest + all other events
    c: int  # all other drugs + event of interest
    d: int  # all other drugs + all other events


@dataclass(frozen=True)
class SignalStats:
    drug: str
    event: str
    a: int
    b: int
    c: int
    d: int
    prr: float | None
    ror: float | None
    ror_ci_low: float | None
    ror_ci_high: float | None
    chi_square: float | None
    is_signal: bool

    def as_dict(self) -> dict:
        return asdict(self)


def build_contingency_table(reports: list[dict], drug: str, event: str) -> ContingencyTable:
    a = b = c = d = 0
    for r in reports:
        drug_match = r["drug"] == drug
        event_match = r["event"] == event
        if drug_match and event_match:
            a += 1
        elif drug_match and not event_match:
            b += 1
        elif not drug_match and event_match:
            c += 1
        else:
            d += 1
    return ContingencyTable(a=a, b=b, c=c, d=d)


def compute_signal_stats(reports: list[dict], drug: str, event: str) -> SignalStats:
    t = build_contingency_table(reports, drug, event)
    return stats_from_contingency(drug, event, t.a, t.b, t.c, t.d)


def stats_from_contingency(drug: str, event: str, a: int, b: int, c: int, d: int) -> SignalStats:
    """Same PRR/ROR/chi-square math as `compute_signal_stats`, starting directly from
    already-computed 2x2 counts. Lets a caller source those counts from a cheap SQL
    aggregation (a handful of rows) instead of transferring every report row over the
    network just to re-derive counts in Python — see services/investigation.py."""
    prr = None
    ror = None
    ror_lo = None
    ror_hi = None
    chi2 = None

    if a > 0 and (a + b) > 0 and c > 0 and (c + d) > 0:
        prr = (a / (a + b)) / (c / (c + d))

    if a > 0 and b > 0 and c > 0 and d > 0:
        ror = (a * d) / (b * c)
        # 95% CI via Woolf's method on the log-odds ratio
        import math
        se_log_ror = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        log_ror = math.log(ror)
        ror_lo = math.exp(log_ror - 1.96 * se_log_ror)
        ror_hi = math.exp(log_ror + 1.96 * se_log_ror)

    n = a + b + c + d
    if n > 0 and (a + b) > 0 and (c + d) > 0 and (a + c) > 0 and (b + d) > 0:
        chi2, _p, _dof, _expected = scipy_stats.chi2_contingency(
            [[a, b], [c, d]], correction=True
        )

    is_signal = bool(
        prr is not None and prr >= EVANS_MIN_PRR
        and chi2 is not None and chi2 >= EVANS_MIN_CHI_SQUARE
        and a >= EVANS_MIN_CASES
    )

    return SignalStats(
        drug=drug, event=event, a=a, b=b, c=c, d=d,
        prr=prr, ror=ror, ror_ci_low=ror_lo, ror_ci_high=ror_hi,
        chi_square=chi2, is_signal=is_signal,
    )


def compute_all_signals(reports: list[dict]) -> list[SignalStats]:
    """Compute stats for every observed drug-event pair with >=1 report."""
    pairs = sorted({(r["drug"], r["event"]) for r in reports})
    results = [compute_signal_stats(reports, drug, event) for drug, event in pairs]
    return results


def rank_flagged_signals(reports: list[dict]) -> list[SignalStats]:
    all_stats = compute_all_signals(reports)
    flagged = [s for s in all_stats if s.is_signal]
    flagged.sort(key=lambda s: (s.prr is None, -(s.prr or 0)))
    return flagged
