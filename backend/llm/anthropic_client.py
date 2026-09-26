"""Active LLM provider for this deployment: the Anthropic Claude API (see README "LLM
provider" for why this deviates from the original Bedrock assumption A6).

Structured extraction uses `output_config.format` (JSON-schema-constrained output) rather
than tool-use — Requirement 3.2 calls for "forced structured output (tool/JSON schema)" and
this is the more direct of the two for pure extraction (no multi-turn tool loop needed).
The response is still independently re-validated by our own Pydantic schema in
`backend/llm/schema.py` (Requirement 4.5's Level 2 guardrail must not simply trust that the
API's own schema constraint held).

Anthropic has no embeddings endpoint, so `embed_text` here is a local, dependency-free,
deterministic hashing vectorizer — not a trained semantic embedding model. It's a known,
documented simplification (see README) that keeps Requirement 12's RAG pipeline runnable
end-to-end with only an Anthropic key; retrieval quality is keyword-driven, not semantic.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading

import anthropic
import numpy as np

from backend.config import get_settings
from backend.llm.errors import LLMUnavailableError

_client: anthropic.Anthropic | None = None
_client_lock = threading.Lock()


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                settings = get_settings()
                kwargs = {}
                if settings.anthropic_api_key:
                    kwargs["api_key"] = settings.anthropic_api_key
                _client = anthropic.Anthropic(**kwargs)
    return _client


def _extract_text(response) -> str:
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise LLMUnavailableError(f"Claude declined the request (refusal, category={category}).")
    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        raise LLMUnavailableError(f"Model response contained no text block (stop_reason={response.stop_reason}).")
    if response.stop_reason == "max_tokens":
        raise LLMUnavailableError("Model hit the max_tokens limit before finishing its response.")
    return text_block.text


def _call(*, system_prompt: str, user_message: str, model: str, max_tokens: int,
          output_format: dict | None, effort: str):
    client = _get_client()
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
        "output_config": {"effort": effort, **({"format": output_format} if output_format else {})},
    }
    try:
        return client.messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        raise LLMUnavailableError(f"Invalid Anthropic API key: {e}") from e
    except anthropic.PermissionDeniedError as e:
        raise LLMUnavailableError(f"Anthropic API key lacks permission for this model: {e}") from e
    except anthropic.NotFoundError as e:
        raise LLMUnavailableError(f"Unknown model '{model}': {e}") from e
    except anthropic.RateLimitError as e:
        raise LLMUnavailableError(f"Anthropic rate limit hit: {e}") from e
    except anthropic.APIConnectionError as e:
        raise LLMUnavailableError(f"Cannot reach the Anthropic API: {e}") from e
    except anthropic.APIStatusError as e:
        raise LLMUnavailableError(f"Anthropic API error ({e.status_code}): {e.message}") from e


def converse_with_tool(
    *,
    system_prompt: str,
    user_message: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict,
    model_id: str | None = None,
) -> dict:
    """Kept for interface parity with the (unused) Bedrock client — forced structured
    output here, via `output_config.format` with `input_schema` as the JSON schema."""
    settings = get_settings()
    model = model_id or settings.anthropic_model_id
    response = _call(
        system_prompt=system_prompt, user_message=user_message, model=model, max_tokens=2000,
        output_format={"type": "json_schema", "schema": input_schema},
        effort=settings.anthropic_extraction_effort,
    )
    text = _extract_text(response)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMUnavailableError(f"Model output was not valid JSON: {e}") from e


def converse_text(*, system_prompt: str, user_message: str, model_id: str | None = None) -> str:
    settings = get_settings()
    model = model_id or settings.anthropic_model_id
    response = _call(
        system_prompt=system_prompt, user_message=user_message, model=model, max_tokens=2000,
        output_format=None, effort=settings.anthropic_default_effort,
    )
    return _extract_text(response)


# --- Local fallback embeddings (no Anthropic embeddings endpoint exists) ----------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_EMBED_DIM = 512


def embed_text(text: str, model_id: str | None = None) -> list[float]:
    """Deterministic hashing-based bag-of-words vector (feature hashing), L2-normalised.
    Not a semantic embedding — see module docstring. Same text always yields the same
    vector, and vectors sharing vocabulary get nonzero cosine similarity, which is enough
    for this demo's small, single-signal retrieval scope."""
    vec = np.zeros(_EMBED_DIM, dtype=np.float64)
    tokens = _TOKEN_RE.findall(text.lower())
    for tok in tokens:
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % _EMBED_DIM
        sign = 1.0 if (h // _EMBED_DIM) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()
