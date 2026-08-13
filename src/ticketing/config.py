"""Ticketing settings from environment (optional ``.env`` file)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process config from environment (or an explicit constructor)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Env names are case-insensitive: DATABASE_URL → database_url, etc.
    database_url: str
    escalation_seconds: int = 86_400
    host: str = "0.0.0.0"
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    return Settings()
