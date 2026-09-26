"""Central configuration. Reads .env (if present) then process env.

Assumption A6 originally pinned Bedrock Nova Lite; this deployment runs on the Anthropic
Claude API instead (see README "LLM provider" section) because that's the credential
available in this environment — the Bedrock settings are kept below, unused, in case AWS
credentials are supplied later. Assumption A4 makes the manual-minutes-per-case figure an
explicit, overridable, labelled assumption (Requirement 10.1). Persistence is Postgres
(Supabase) via DATABASE_URL — see README "Database" section.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Kept for a possible future switch back to Bedrock; unused while llm_provider="anthropic".
    aws_region: str = "ap-south-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    bedrock_model_id: str = "apac.amazon.nova-lite-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    # Active provider for this deployment (Requirement A6 deviation — see README).
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model_id: str = "claude-opus-5"
    # Effort tuning (a cost/latency lever, not a model downgrade — see claude-api skill
    # guidance): "low" for high-volume structured extraction across many cases, "high"
    # (the model default) for the low-volume chat/summary calls where quality matters more.
    anthropic_extraction_effort: str = "low"
    anthropic_default_effort: str = "high"

    manual_minutes_per_case: float = 17.0

    dataset_seed: int = 42
    dataset_size: int = 1000

    # Postgres connection string (Supabase's "Session pooler" URI, or any Postgres).
    # Required — there is no local-file fallback (see backend/db.py docstring).
    database_url: str | None = None

    extraction_prompt_version: str = "extract-v1"
    causality_ruleset_version: str = "causality-v1"
    recommendation_ruleset_version: str = "recommendation-v1"
    summary_prompt_version: str = "summary-v1"
    chat_prompt_version: str = "chat-v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
