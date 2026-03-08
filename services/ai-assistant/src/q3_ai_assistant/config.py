from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://127.0.0.1:5432/q3"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    max_tokens: int = 2000
    temperature: float = 0.0

    scan_interval_seconds: int = 30
    enabled: bool = True

    cache_ttl_seconds: int = 86400
    max_input_chars: int = 50_000
    cost_limit_usd_daily: float = 10.0
    retry_max_attempts: int = 3

    model_config = {"env_prefix": "Q3_AI_"}


settings = Settings()
