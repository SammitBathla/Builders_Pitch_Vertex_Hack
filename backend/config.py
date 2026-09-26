"""Central configuration. Reads .env (if present) then process env.

Assumption A6 pins the model/region; Assumption A4 makes the manual-minutes-per-case
figure an explicit, overridable, labelled assumption (Requirement 10.1).
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    aws_region: str = "ap-south-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None

    bedrock_model_id: str = "apac.amazon.nova-lite-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    manual_minutes_per_case: float = 17.0

    dataset_seed: int = 42
    dataset_size: int = 1000

    data_dir: str = "./data"

    extraction_prompt_version: str = "extract-v1"
    causality_ruleset_version: str = "causality-v1"
    recommendation_ruleset_version: str = "recommendation-v1"
    summary_prompt_version: str = "summary-v1"
    chat_prompt_version: str = "chat-v1"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def sqlite_path(self) -> Path:
        return self.data_path / "copilot.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
