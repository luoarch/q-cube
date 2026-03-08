"""Pre-configured cascade pools for Q3.

Pool configurations:
  - orchestrator_pool: premium reasoning (gpt-5.4-pro -> opus-4-6 -> gemini-2.5-pro)
  - specialist_pool:   balanced (gpt-5.4 -> sonnet-4-6 -> gemini-2.5-pro)
  - huge_context_pool: max context (gemini-2.5-pro -> gpt-5.4 -> opus-4-6)

Each pool is a list[ProviderEntry] sorted by priority.
"""

from __future__ import annotations

import logging

from q3_ai_assistant.config import Settings
from q3_ai_assistant.llm.cascade import CascadeRouter, ProviderEntry

logger = logging.getLogger(__name__)


def _try_openai(settings: Settings, model: str) -> ProviderEntry | None:
    if not settings.openai_api_key:
        return None
    from q3_ai_assistant.llm.openai_adapter import OpenAIAdapter
    adapter = OpenAIAdapter.__new__(OpenAIAdapter)
    from openai import OpenAI
    adapter.client = OpenAI(api_key=settings.openai_api_key)
    adapter.model = model
    adapter.max_tokens = settings.max_tokens
    adapter.temperature = settings.temperature
    adapter._retry_attempts = settings.retry_max_attempts
    return ProviderEntry(provider_name="openai", adapter=adapter, priority=0)


def _try_anthropic(settings: Settings, model: str) -> ProviderEntry | None:
    if not settings.anthropic_api_key:
        return None
    from q3_ai_assistant.llm.anthropic_adapter import AnthropicAdapter
    adapter = AnthropicAdapter.__new__(AnthropicAdapter)
    from anthropic import Anthropic
    adapter.client = Anthropic(api_key=settings.anthropic_api_key)
    adapter.model = model
    adapter.max_tokens = settings.max_tokens
    adapter.temperature = settings.temperature
    return ProviderEntry(provider_name="anthropic", adapter=adapter, priority=0)


def _try_google(settings: Settings, model: str) -> ProviderEntry | None:
    if not settings.google_api_key:
        return None
    from q3_ai_assistant.llm.google_adapter import GoogleAdapter
    adapter = GoogleAdapter.__new__(GoogleAdapter)
    from google import genai
    adapter.client = genai.Client(api_key=settings.google_api_key)
    adapter.model = model
    adapter.max_tokens = settings.max_tokens
    adapter.temperature = settings.temperature
    return ProviderEntry(provider_name="google", adapter=adapter, priority=0)


def build_orchestrator_pool(settings: Settings) -> CascadeRouter:
    """Build the orchestrator cascade: gpt-5.4-pro -> opus-4-6 -> gemini-2.5-pro."""
    entries: list[ProviderEntry] = []

    e = _try_openai(settings, settings.orchestrator_openai_model)
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=1, latency_sla_ms=60_000)
        entries.append(e)

    e = _try_anthropic(settings, settings.orchestrator_anthropic_model)
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=2, latency_sla_ms=60_000)
        entries.append(e)

    e = _try_google(settings, settings.orchestrator_google_model)
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=3, latency_sla_ms=90_000)
        entries.append(e)

    if not entries:
        raise ValueError("No providers configured for orchestrator pool. Set at least one API key.")

    logger.info("orchestrator_pool providers=%s", [e.provider_name for e in entries])
    return CascadeRouter(entries)


def build_specialist_pool(settings: Settings) -> CascadeRouter:
    """Build the specialist cascade: gpt-5.4 -> sonnet-4-6 -> gemini-2.5-pro."""
    entries: list[ProviderEntry] = []

    e = _try_openai(settings, settings.specialist_openai_model)
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=1, latency_sla_ms=45_000)
        entries.append(e)

    e = _try_anthropic(settings, settings.specialist_anthropic_model)
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=2, latency_sla_ms=45_000)
        entries.append(e)

    e = _try_google(settings, settings.specialist_google_model)
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=3, latency_sla_ms=60_000)
        entries.append(e)

    if not entries:
        raise ValueError("No providers configured for specialist pool. Set at least one API key.")

    logger.info("specialist_pool providers=%s", [e.provider_name for e in entries])
    return CascadeRouter(entries)


def build_huge_context_pool(settings: Settings) -> CascadeRouter:
    """Build the huge context cascade: gemini-2.5-pro -> gpt-5.4 -> opus-4-6."""
    entries: list[ProviderEntry] = []

    e = _try_google(settings, "gemini-2.5-pro")
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=1, latency_sla_ms=120_000)
        entries.append(e)

    e = _try_openai(settings, settings.specialist_openai_model)
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=2, latency_sla_ms=90_000)
        entries.append(e)

    e = _try_anthropic(settings, settings.orchestrator_anthropic_model)
    if e:
        e = ProviderEntry(e.provider_name, e.adapter, priority=3, latency_sla_ms=90_000)
        entries.append(e)

    if not entries:
        raise ValueError("No providers configured for huge context pool. Set at least one API key.")

    logger.info("huge_context_pool providers=%s", [e.provider_name for e in entries])
    return CascadeRouter(entries)
