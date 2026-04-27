from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOW_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://flow:flow@localhost:55432/flow"
    jwt_secret: str = "dev-change-me-16b"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_json: bool = False
    otel_endpoint: str | None = None
    sentry_dsn: str | None = None
    prometheus_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"
    sandbox_driver: str = "unsafe"  # FLOW_SANDBOX_DRIVER — "e2b" | "docker" | "unsafe"
    e2b_api_key: str | None = None  # FLOW_E2B_API_KEY


@lru_cache
def get_settings() -> Settings:
    return Settings()
