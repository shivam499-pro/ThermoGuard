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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (constructed once per process)."""
    return Settings()
