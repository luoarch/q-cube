from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://127.0.0.1:5432/q3"
    redis_url: str = "redis://localhost:6379/0"

    # Legacy single-provider (still works for existing modules)
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    max_tokens: int = 2000
    temperature: float = 0.0

    # Multi-provider cascade keys
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    google_api_key: str = ""

    # Orchestrator pool models (premium reasoning)
    orchestrator_openai_model: str = "gpt-5.4-pro"
    orchestrator_anthropic_model: str = "claude-opus-4-6"
    orchestrator_google_model: str = "gemini-2.5-pro"

    # Specialist pool models (balanced quality/cost)
    specialist_openai_model: str = "gpt-5.4"
    specialist_anthropic_model: str = "claude-sonnet-4-6"
    specialist_google_model: str = "gemini-2.5-pro"

    # Web tools
    brave_search_api_key: str = ""
    web_browse_enabled: bool = True
    web_search_timeout_seconds: int = 10
    web_browse_timeout_seconds: int = 15

    quant_engine_url: str = "http://localhost:8100"
    scan_interval_seconds: int = 30
    enabled: bool = True

    cache_ttl_seconds: int = 86400
    max_input_chars: int = 50_000
    cost_limit_usd_daily: float = 10.0
    retry_max_attempts: int = 3

    model_config = {
        "env_prefix": "Q3_AI_",
        "env_file": "../../.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
