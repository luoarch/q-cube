from __future__ import annotations

from q3_ai_assistant.config import Settings
from q3_ai_assistant.llm.adapter import LLMAdapter
from q3_ai_assistant.llm.mock_adapter import MockAdapter
from q3_ai_assistant.llm.openai_adapter import OpenAIAdapter


def create_adapter(settings: Settings) -> LLMAdapter:
    """Create a single LLM adapter (legacy, for existing modules)."""
    if settings.llm_provider == "openai":
        return OpenAIAdapter(settings)
    if settings.llm_provider == "anthropic":
        from q3_ai_assistant.llm.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter(settings)
    if settings.llm_provider == "google":
        from q3_ai_assistant.llm.google_adapter import GoogleAdapter
        return GoogleAdapter(settings)
    if settings.llm_provider == "mock":
        return MockAdapter()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
