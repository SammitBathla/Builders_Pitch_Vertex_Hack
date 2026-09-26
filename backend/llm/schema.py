"""Requirement 4.5 / 3.2: the forced-output schema, validated strictly. Anything that does
not conform is an extraction failure — it is never coerced into a best guess."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

__all__ = ["ExtractionOutput", "ConfounderItem", "ExtractionSchemaError", "validate_extraction"]


class ExtractionSchemaError(Exception):
    def __init__(self, message: str, raw: dict | None = None):
        super().__init__(message)
        self.raw = raw


class ConfounderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    quote: str


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_to_onset_days: int | None = None
    time_to_onset_quote: str | None = None
    onset_order: Literal["after_drug_start", "before_drug_start", "unclear"]
    onset_order_quote: str | None = None
    dechallenge: Literal["positive", "negative", "not_done", "unknown"]
    dechallenge_quote: str | None = None
    rechallenge: Literal["positive", "negative", "not_done", "unknown"]
    rechallenge_quote: str | None = None
    confounders: list[ConfounderItem] = []
    data_gaps: list[str] = []


def validate_extraction(raw: dict) -> ExtractionOutput:
    try:
        return ExtractionOutput.model_validate(raw)
    except ValidationError as e:
        raise ExtractionSchemaError(f"Extraction output failed schema validation: {e}", raw=raw) from e
