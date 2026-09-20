"""
ThermoGuard backend configuration.

Reads settings from environment variables with safe defaults.
No secrets are hardcoded here; supply real values via a .env file
(which is excluded from version control by .gitignore).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "ThermoGuard"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── API ──────────────────────────────────────────────────────────────────
    api_prefix: str = "/api"
    cors_origins: list[str] = ["*"]

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    json_logs: bool = True

    # ── Storage / AWS serverless ─────────────────────────────────────────────
    storage_backend: str = "file"  # file | dynamodb
    aws_region: str = "ap-south-1"
    events_table: str = "thermoguard-events"
    jobs_table: str = "thermoguard-jobs"
    cache_table: str = "thermoguard-semantic-cache"
    vectors_table: str = "thermoguard-vectors"
    sqs_queue_url: str = ""
    bedrock_enabled: bool = False
    bedrock_model_id: str = "amazon.nova-lite-v1:0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (constructed once per process)."""
    return Settings()
