from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Flow API (internal Docker network)
    flow_api_url: str = "http://api:8000"
    flow_jwt_secret: str = "changeme"

    # Obsidian vault mode: filesystem | api | cloud
    obsidian_mode: str = "filesystem"
    obsidian_vault_path: str = "/vault"
    obsidian_api_url: str = "http://localhost:27123"
    obsidian_api_key: Optional[str] = None

    # Cloud vault (S3-compatible)
    obsidian_bucket: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_endpoint_url: Optional[str] = None
    aws_region: str = "us-east-1"

    # GitHub
    github_token: Optional[str] = None

    # Research
    tavily_api_key: Optional[str] = None
    hf_papers_enabled: bool = True
    arxiv_categories: str = "cs.AI,cs.LG,cs.CL"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
