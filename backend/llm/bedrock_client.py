"""Thin wrapper around Amazon Bedrock (Assumption A6: Nova Lite, ap-south-1, temperature 0).

Uses the Converse API's toolConfig to force structured JSON output (Requirement 3.2):
the model must call the single provided tool, whose input schema is the extraction schema,
rather than returning free text we'd have to parse hopefully.
"""
from __future__ import annotations

import json
import threading

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from backend.config import get_settings


class BedrockUnavailableError(RuntimeError):
    """Raised whenever the LLM cannot be reached or returns something we cannot use.
    Requirement 11.2: the system must fail loudly per case, never silently."""


_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                settings = get_settings()
                kwargs = {"region_name": settings.aws_region}
                if settings.aws_access_key_id and settings.aws_secret_access_key:
                    kwargs["aws_access_key_id"] = settings.aws_access_key_id
                    kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
                    if settings.aws_session_token:
                        kwargs["aws_session_token"] = settings.aws_session_token
                _client = boto3.client("bedrock-runtime", **kwargs)
    return _client


def converse_with_tool(
    *,
    system_prompt: str,
    user_message: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict,
    model_id: str | None = None,
) -> dict:
    """Calls Bedrock Converse, forcing use of the given tool, at temperature 0.

    Returns the tool's `input` dict (already parsed JSON) on success. Raises
    BedrockUnavailableError on any transport/credentials/parsing failure — callers must
    treat that as an extraction/answer failure, never silently substitute a guess.
    """
    settings = get_settings()
    model = model_id or settings.bedrock_model_id
    client = _get_client()

    tool_config = {
        "tools": [
            {
                "toolSpec": {
                    "name": tool_name,
                    "description": tool_description,
                    "inputSchema": {"json": input_schema},
                }
            }
        ],
        "toolChoice": {"tool": {"name": tool_name}},
    }

    try:
        response = client.converse(
            modelId=model,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_message}]}],
            toolConfig=tool_config,
            inferenceConfig={"temperature": 0, "maxTokens": 1500},
        )
    except NoCredentialsError as e:
        raise BedrockUnavailableError(
            "AWS credentials not configured — cannot reach Bedrock. "
            "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY (or the standard boto3 credential "
            "chain) for region ap-south-1."
        ) from e
    except (ClientError, BotoCoreError) as e:
        raise BedrockUnavailableError(f"Bedrock call failed: {e}") from e

    content = response.get("output", {}).get("message", {}).get("content", [])
    for block in content:
        if "toolUse" in block:
            tool_input = block["toolUse"].get("input")
            if isinstance(tool_input, str):
                try:
                    tool_input = json.loads(tool_input)
                except json.JSONDecodeError as e:
                    raise BedrockUnavailableError(f"Model tool input was not valid JSON: {e}") from e
            return tool_input
    raise BedrockUnavailableError("Model response did not include the requested tool call.")


def converse_text(*, system_prompt: str, user_message: str, model_id: str | None = None) -> str:
    """Plain (non-tool-forced) Converse call, used for the chatbot answer and the summary
    draft, both of which need free text rather than a fixed schema. Still temperature 0."""
    settings = get_settings()
    model = model_id or settings.bedrock_model_id
    client = _get_client()
    try:
        response = client.converse(
            modelId=model,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_message}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 1500},
        )
    except NoCredentialsError as e:
        raise BedrockUnavailableError(
            "AWS credentials not configured — cannot reach Bedrock."
        ) from e
    except (ClientError, BotoCoreError) as e:
        raise BedrockUnavailableError(f"Bedrock call failed: {e}") from e

    content = response.get("output", {}).get("message", {}).get("content", [])
    texts = [b["text"] for b in content if "text" in b]
    if not texts:
        raise BedrockUnavailableError("Model response contained no text.")
    return "\n".join(texts)


def embed_text(text: str, model_id: str | None = None) -> list[float]:
    settings = get_settings()
    model = model_id or settings.bedrock_embedding_model_id
    client = _get_client()
    try:
        response = client.invoke_model(
            modelId=model,
            body=json.dumps({"inputText": text[:8000]}),
            contentType="application/json",
            accept="application/json",
        )
    except NoCredentialsError as e:
        raise BedrockUnavailableError("AWS credentials not configured — cannot reach Bedrock.") from e
    except (ClientError, BotoCoreError) as e:
        raise BedrockUnavailableError(f"Bedrock embedding call failed: {e}") from e

    body = json.loads(response["body"].read())
    embedding = body.get("embedding")
    if not embedding:
        raise BedrockUnavailableError("Embedding response contained no vector.")
    return embedding
