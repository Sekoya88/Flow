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
    # Pretty console logs (Docker often has no TTY — set FORCE_COLOR=1 or FLOW_LOG_FORCE_COLORS=true).
    log_force_colors: bool = False
    # LangSmith: traces for LangChain/LangGraph (worker + API when graphs run).
    # LangSmith: when API key is set, tracing is on unless FLOW_LANGSMITH_TRACING=false
    langsmith_tracing: bool = True
    langsmith_api_key: str | None = None  # mapped to LANGCHAIN_API_KEY
    langsmith_project: str = "flow-local"
    # EU hosted Smith: https://eu.api.smith.langchain.com
    langsmith_endpoint: str | None = None
    otel_endpoint: str | None = None
    sentry_dsn: str | None = None
    prometheus_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"
    sandbox_driver: str = "unsafe"  # FLOW_SANDBOX_DRIVER — "e2b" | "docker" | "unsafe"
    e2b_api_key: str | None = None  # FLOW_E2B_API_KEY
    # Agentic RAG (Qdrant hybrid + audit). When enabled and FLOW_QDRANT_URL is set, worker retrieval uses the pipeline.
    qdrant_url: str | None = None  # FLOW_QDRANT_URL e.g. http://localhost:16333
    qdrant_collection: str = "flow_knowledge"
    agentic_rag_enabled: bool = False
    tavily_api_key: str | None = None  # FLOW_TAVILY_API_KEY — optional web fallback


@lru_cache
def get_settings() -> Settings:
    return Settings()
