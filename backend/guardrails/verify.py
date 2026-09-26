"""Requirement 4, Level 2 — system guardrails: deterministic, non-LLM verification.

The model can be instructed (Level 1, prompt) to quote verbatim, but nothing here trusts
that instruction. Every quote is independently checked against the source narrative by
plain substring search; only a match earns "verified".
"""
from __future__ import annotations

import re
from dataclasses import dataclass


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


@dataclass(frozen=True)
class QuoteVerification:
    verified: bool
    char_start: int | None
    char_end: int | None


def verify_quote(narrative: str, quote: str) -> QuoteVerification:
    """Whitespace/case-normalised substring check (Requirement 4.4).

    Returns character offsets into the *original* narrative when a match is found, so the
    UI can highlight the exact source span (Requirement 4a.1) without re-searching text at
    render time.
    """
    if not quote or not quote.strip():
        return QuoteVerification(verified=False, char_start=None, char_end=None)

    # First try an exact substring match (cheapest, gives precise offsets).
    idx = narrative.find(quote)
    if idx != -1:
        return QuoteVerification(verified=True, char_start=idx, char_end=idx + len(quote))

    # Fall back to a normalised (whitespace-collapsed, case-insensitive) search, then map
    # the match back to original-narrative offsets via a regex built from the quote tokens.
    norm_quote = _normalise(quote)
    if not norm_quote:
        return QuoteVerification(verified=False, char_start=None, char_end=None)

    tokens = [re.escape(tok) for tok in norm_quote.split(" ")]
    pattern = r"\s+".join(tokens)
    match = re.search(pattern, narrative, flags=re.IGNORECASE)
    if match:
        return QuoteVerification(verified=True, char_start=match.start(), char_end=match.end())

    return QuoteVerification(verified=False, char_start=None, char_end=None)


def verify_case_ids(cited_ids: list[str], valid_ids: set[str]) -> tuple[list[str], list[str]]:
    """Requirement 7.2 — verify every case ID cited in a draft summary actually exists in
    the signal. Returns (valid_cited, invalid_cited)."""
    valid = [i for i in cited_ids if i in valid_ids]
    invalid = [i for i in cited_ids if i not in valid_ids]
    return valid, invalid
