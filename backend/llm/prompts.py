"""Versioned prompts (Requirement 4.2: every prompt-level guardrail is itself versioned
and recorded on every extraction/answer, so it is auditable)."""

EXTRACTION_PROMPT_VERSION = "extract-v1"

EXTRACTION_SYSTEM_PROMPT = """You are a pharmacovigilance case-narrative fact extractor.

Your ONLY job is to extract facts that are explicitly stated in the narrative below. You are
NOT a medical reviewer and you must NEVER assign causality, never judge whether the drug
caused the event, and never make a recommendation. Only the facts.

Rules you must follow exactly:
1. Every quote you provide MUST be copied VERBATIM (character-for-character) from the
   narrative. Do not paraphrase, summarise, correct spelling, or combine separate sentences.
2. If the narrative does not explicitly state a fact, you MUST use the "unknown" /
   "not_done" / null value for it — never guess or infer from typical clinical patterns.
3. Report facts only. Do not add opinions, severity judgements, or causality conclusions.
4. "onset_order" describes only what the narrative states about sequence (did the event
   start after or before the drug, or is it unclear) — this is a factual reading of the
   text, not a causality judgement.

You must call the extract_case_facts tool with your answer. Do not respond in free text.
"""

EXTRACTION_TOOL_NAME = "extract_case_facts"
EXTRACTION_TOOL_DESCRIPTION = (
    "Record the causality-relevant facts explicitly stated in a single adverse-event case "
    "narrative, each backed by a verbatim quote from that narrative."
)

EXTRACTION_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "time_to_onset_days": {
            "type": ["integer", "null"],
            "description": "Days between drug start and event onset, ONLY if a specific "
                            "number (or a range you can convert to a single best number, e.g. "
                            "'about 2 weeks' -> 14) is explicitly stated. Otherwise null.",
        },
        "time_to_onset_quote": {
            "type": ["string", "null"],
            "description": "Verbatim quote supporting time_to_onset_days, or null if that field is null.",
        },
        "onset_order": {
            "type": "string",
            "enum": ["after_drug_start", "before_drug_start", "unclear"],
            "description": "What the narrative states about whether the event started after "
                            "or before the drug, purely as a textual fact.",
        },
        "onset_order_quote": {
            "type": ["string", "null"],
            "description": "Verbatim quote supporting onset_order, or null if onset_order is 'unclear'.",
        },
        "dechallenge": {
            "type": "string",
            "enum": ["positive", "negative", "not_done", "unknown"],
            "description": "positive = event improved/resolved after stopping the drug; "
                            "negative = event did NOT improve after stopping; not_done = "
                            "narrative states drug was continued/not stopped; unknown = not stated.",
        },
        "dechallenge_quote": {
            "type": ["string", "null"],
            "description": "Verbatim quote supporting dechallenge, or null if dechallenge is 'unknown'.",
        },
        "rechallenge": {
            "type": "string",
            "enum": ["positive", "negative", "not_done", "unknown"],
            "description": "positive = event recurred on re-exposure; negative = did not "
                            "recur on re-exposure; not_done = narrative states no rechallenge "
                            "occurred; unknown = rechallenge not mentioned at all.",
        },
        "rechallenge_quote": {
            "type": ["string", "null"],
            "description": "Verbatim quote supporting rechallenge, or null if rechallenge is 'unknown'.",
        },
        "confounders": {
            "type": "array",
            "description": "Alternative causes, comorbidities, or concomitant medications the "
                            "narrative explicitly raises as possibly explaining the event. "
                            "Empty array if none are mentioned.",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Short plain-language label for the confounder."},
                    "quote": {"type": "string", "description": "Verbatim quote from the narrative."},
                },
                "required": ["text", "quote"],
                "additionalProperties": False,
            },
        },
        "data_gaps": {
            "type": "array",
            "description": "Short plain-language notes on what information is missing from "
                            "this narrative that would help assess causality (e.g. 'no lab "
                            "values reported'). Does not require a quote.",
            "items": {"type": "string"},
        },
    },
    "required": [
        "time_to_onset_days", "time_to_onset_quote", "onset_order", "onset_order_quote",
        "dechallenge", "dechallenge_quote", "rechallenge", "rechallenge_quote",
        "confounders", "data_gaps",
    ],
    "additionalProperties": False,
}


def build_extraction_user_message(report_id: str, drug: str, event: str, narrative: str) -> str:
    return (
        f"Case report ID: {report_id}\n"
        f"Drug of interest: {drug}\n"
        f"Event of interest: {event}\n\n"
        f"Narrative:\n{narrative}\n\n"
        "Extract only the facts stated above about this drug-event pair, per your instructions."
    )


# --- Summary draft prompt (Requirement 7) ---------------------------------------------

SUMMARY_PROMPT_VERSION = "summary-v1"

SUMMARY_SYSTEM_PROMPT = """You are drafting a pharmacovigilance signal investigation summary for
human review. You will be given: signal statistics, the causality category assigned to each
case (already decided by a deterministic rule engine — you do not change it), and the rule-
computed recommendation (already decided — you do not change it).

Write a concise, factual investigation narrative (250-400 words) that:
- States the drug-event pair and the statistical signal (PRR, chi-square, case count).
- Summarises the causality distribution across cases.
- Cites specific case IDs (format: RPT-#####) when referencing example cases — only IDs
  given to you in the input, never invented ones.
- States the recommendation exactly as given, attributing it to the rule that produced it.
- Does NOT change, second-guess, or add a different recommendation than the one given.
- Is written in a neutral, clinical register suitable for a regulatory audience.

This is a DRAFT for a human reviewer to edit and approve — do not claim it is final."""


def build_summary_user_message(context: dict) -> str:
    import json as _json
    return (
        "Signal and case data (JSON):\n" + _json.dumps(context, ensure_ascii=False, indent=2) +
        "\n\nWrite the draft investigation summary now."
    )


# --- Chatbot prompt (Requirement 12) ---------------------------------------------------

CHAT_PROMPT_VERSION = "chat-v1"

CHAT_SYSTEM_PROMPT = """You are a read-only pharmacovigilance investigation assistant. You answer
questions about ONE signal using ONLY the retrieved context chunks provided to you below —
never your general knowledge, and never information about any other drug or signal.

Rules:
1. If the retrieved context does not support an answer, say plainly that you cannot find
   supporting evidence for that question in this signal's case data. Do not guess.
2. Every substantive claim you make must be traceable to a specific retrieved chunk. After
   each claim, cite the chunk's case ID in square brackets, e.g. [RPT-00042].
3. You must NEVER assign causality, NEVER state or imply a recommendation, and NEVER claim
   to be a decision-maker. You are an assistant that surfaces evidence for a human reviewer.
4. Be concise and specific."""


def build_chat_user_message(question: str, context_chunks: list[dict]) -> str:
    import json as _json
    return (
        f"Question: {question}\n\n"
        "Retrieved context chunks (JSON list, each with chunk_id, case_id, text):\n" +
        _json.dumps(context_chunks, ensure_ascii=False, indent=2)
    )
