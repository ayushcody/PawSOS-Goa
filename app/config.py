"""Settings, read from environment variables (and .env in development)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    port: int = 8040
    public_base_url: str = "http://localhost:8040"
    channel: Literal["simulator", "whatsapp"] = "simulator"
    escalation_timeout_seconds: int = 600

    # Default points at the local Docker database (docker-compose.yml).
    database_url: str = "postgresql+psycopg://pawsos:pawsos@localhost:5440/pawsos"
    media_dir: str = "uploads"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
