"""End-to-end integration tests — real LLM calls, real HTTP, real DB queries.

These tests exercise the full pipeline with actual provider calls.
They are skipped when API keys or DB are not available.

Run with: pytest tests/test_e2e_integration.py -v -s
"""

from __future__ import annotations

import os

import pytest

from q3_ai_assistant.config import settings

# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

HAS_OPENAI_KEY = bool(settings.openai_api_key)
HAS_ANTHROPIC_KEY = bool(settings.anthropic_api_key)
HAS_ANY_LLM_KEY = HAS_OPENAI_KEY or HAS_ANTHROPIC_KEY

skip_no_llm = pytest.mark.skipif(not HAS_ANY_LLM_KEY, reason="No LLM API key configured")
skip_no_openai = pytest.mark.skipif(not HAS_OPENAI_KEY, reason="Q3_AI_OPENAI_API_KEY not set")
skip_no_anthropic = pytest.mark.skipif(not HAS_ANTHROPIC_KEY, reason="Q3_AI_ANTHROPIC_API_KEY not set")


def _has_db() -> bool:
    """Check if DB is reachable."""
    try:
        from q3_ai_assistant.db.session import SessionLocal
        with SessionLocal() as session:
            session.execute("SELECT 1")
        return True
    except Exception:
        return False


HAS_DB = _has_db()
skip_no_db = pytest.mark.skipif(not HAS_DB, reason="Database not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cascade(provider: str = "openai"):
    """Create a real CascadeRouter with a single provider."""
    from q3_ai_assistant.llm.cascade import CascadeRouter, ProviderEntry
    from q3_ai_assistant.llm.factory import create_adapter

    # Override provider temporarily
    original = settings.llm_provider
    settings.llm_provider = provider
    try:
        adapter = create_adapter(settings)
    finally:
        settings.llm_provider = original

    entry = ProviderEntry(provider_name=provider, adapter=adapter, priority=0)
    return CascadeRouter([entry])


# ---------------------------------------------------------------------------
# 1. LLM Adapter direct tests
# ---------------------------------------------------------------------------


class TestOpenAIAdapterE2E:
    @skip_no_openai
    def test_generate_returns_response(self):
        """OpenAI adapter returns a valid LLMResponse with real API call."""
        from q3_ai_assistant.llm.openai_adapter import OpenAIAdapter

        adapter = OpenAIAdapter(settings)
        response = adapter.generate(
            "You are a helpful assistant. Reply in one sentence.",
            "What is 2+2?",
        )
        assert response.text
        assert "4" in response.text
        assert response.tokens_used > 0
        assert response.latency_ms > 0
        assert response.model

    @skip_no_anthropic
    def test_anthropic_adapter_generates(self):
        """Anthropic adapter returns a valid LLMResponse."""
        from q3_ai_assistant.llm.anthropic_adapter import AnthropicAdapter

        adapter = AnthropicAdapter(settings)
        response = adapter.generate(
            "You are a helpful assistant. Reply in one sentence.",
            "What is the capital of Brazil?",
        )
        assert response.text
        assert "bras" in response.text.lower()  # handles accented "Brasília"
        assert response.tokens_used > 0


# ---------------------------------------------------------------------------
# 2. Cascade failover tests
# ---------------------------------------------------------------------------


class TestCascadeE2E:
    @skip_no_openai
    def test_cascade_openai_success(self):
        """Cascade with OpenAI primary succeeds on first try."""
        cascade = _make_cascade("openai")
        result = cascade.generate(
            "Reply with exactly: OK",
            "Say OK",
        )
        assert result.response.text
        assert result.fallback_level == 0
        assert result.provider_used == "openai"

    @skip_no_anthropic
    def test_cascade_anthropic_success(self):
        """Cascade with Anthropic primary succeeds."""
        cascade = _make_cascade("anthropic")
        result = cascade.generate(
            "Reply with exactly: OK",
            "Say OK",
        )
        assert result.response.text
        assert result.provider_used == "anthropic"

    @skip_no_llm
    def test_cascade_failover_to_secondary(self):
        """Cascade falls back when primary has invalid key."""
        from q3_ai_assistant.llm.cascade import CascadeRouter, ProviderEntry
        from q3_ai_assistant.llm.openai_adapter import OpenAIAdapter

        # Create a broken primary (invalid key)
        broken_settings = type(settings)()
        broken_settings.openai_api_key = "sk-invalid-key-for-testing"
        broken_settings.openai_model = settings.openai_model
        broken_settings.max_tokens = settings.max_tokens
        broken_settings.temperature = settings.temperature
        broken_settings.retry_max_attempts = 1
        broken_adapter = OpenAIAdapter(broken_settings)

        # Create a working secondary
        from q3_ai_assistant.llm.factory import create_adapter
        working_provider = "openai" if HAS_OPENAI_KEY else "anthropic"
        original = settings.llm_provider
        settings.llm_provider = working_provider
        try:
            working_adapter = create_adapter(settings)
        finally:
            settings.llm_provider = original

        cascade = CascadeRouter([
            ProviderEntry(provider_name="broken", adapter=broken_adapter, priority=0),
            ProviderEntry(provider_name=working_provider, adapter=working_adapter, priority=1),
        ])

        result = cascade.generate("Reply: OK", "Say OK")
        assert result.response.text
        assert result.fallback_level == 1
        assert result.provider_used == working_provider
        assert len(result.attempts) == 2
        assert not result.attempts[0].success
        assert result.attempts[1].success


# ---------------------------------------------------------------------------
# 3. Free chat E2E
# ---------------------------------------------------------------------------


class TestFreeChatE2E:
    @skip_no_llm
    def test_free_chat_general_query(self):
        """Free chat handles a general question with LLM synthesis."""
        from q3_ai_assistant.modules.free_chat import handle_free_chat

        provider = "openai" if HAS_OPENAI_KEY else "anthropic"
        cascade = _make_cascade(provider)

        # Use None session — tools that need DB will be skipped gracefully
        # We test the LLM synthesis path, not DB queries
        class FakeSession:
            """Minimal session stub for tools that won't find data."""
            def query(self, *a, **kw):
                class Q:
                    def filter_by(self, **kw):
                        return self
                    def order_by(self, *a):
                        return self
                    def limit(self, n):
                        return self
                    def first(self):
                        return None
                    def all(self):
                        return []
                return Q()

        result = handle_free_chat(
            FakeSession(),
            "O que e a Magic Formula de Greenblatt?",
            cascade,
        )
        assert result.response
        assert len(result.response) > 50  # Should be a substantive answer
        assert result.provider_used == provider
        assert result.tokens_used > 0
        # Should mention Magic Formula concepts
        text_lower = result.response.lower()
        assert "magic formula" in text_lower or "greenblatt" in text_lower or "earnings" in text_lower

    @skip_no_llm
    def test_free_chat_with_history(self):
        """Free chat uses conversation history for context."""
        from q3_ai_assistant.modules.free_chat import handle_free_chat

        provider = "openai" if HAS_OPENAI_KEY else "anthropic"
        cascade = _make_cascade(provider)

        class FakeSession:
            def query(self, *a, **kw):
                class Q:
                    def filter_by(self, **kw): return self
                    def order_by(self, *a): return self
                    def limit(self, n): return self
                    def first(self): return None
                    def all(self): return []
                return Q()

        history = [
            {"role": "user", "content": "O que e ROIC?"},
            {"role": "assistant", "content": "ROIC é o retorno sobre capital investido."},
        ]

        result = handle_free_chat(
            FakeSession(),
            "E como ele se compara ao ROE?",
            cascade,
            history=history,
        )
        assert result.response
        # Should reference ROE or ROIC from context
        text_lower = result.response.lower()
        assert "roe" in text_lower or "roic" in text_lower


# ---------------------------------------------------------------------------
# 4. Council solo E2E
# ---------------------------------------------------------------------------


class TestCouncilSoloE2E:
    @skip_no_llm
    def test_solo_agent_produces_opinion(self):
        """A single agent produces a structured AgentOpinion via real LLM."""
        from q3_ai_assistant.council.agent_factory import create_agent
        from q3_ai_assistant.council.packet import AssetAnalysisPacket, PeriodValue
        from q3_ai_assistant.council.types import AgentVerdict

        provider = "openai" if HAS_OPENAI_KEY else "anthropic"
        cascade = _make_cascade(provider)

        packet = AssetAnalysisPacket(
            issuer_id="test-issuer-001",
            ticker="WEGE3",
            sector="Bens Industriais",
            subsector="Maquinas e Equipamentos",
            classification="non_financial",
            fundamentals={
                "roic": 0.25,
                "roe": 0.30,
                "earnings_yield": 0.08,
                "gross_margin": 0.35,
                "ebit_margin": 0.18,
                "net_margin": 0.14,
                "debt_to_ebitda": 1.2,
                "cash_conversion": 0.9,
            },
            trends={
                "roic": [
                    PeriodValue(reference_date="2022-12-31", value=0.22),
                    PeriodValue(reference_date="2023-12-31", value=0.24),
                    PeriodValue(reference_date="2024-12-31", value=0.25),
                ],
            },
            refiner_scores={"earnings_quality": 0.8, "safety": 0.7, "operating_consistency": 0.85, "capital_discipline": 0.75},
            flags={"red": [], "strength": ["ebit_growing", "strong_cash_conversion"]},
            market_cap=50_000_000_000,
            avg_daily_volume=100_000_000,
            score_reliability="high",
        )

        agent = create_agent("greenblatt")
        opinion = agent.analyze(packet, cascade)

        assert opinion.agent_id == "greenblatt"
        assert opinion.verdict in list(AgentVerdict)
        assert 0 <= opinion.confidence <= 100
        assert opinion.thesis
        assert len(opinion.thesis) > 20
        assert opinion.provider_used == provider
        assert opinion.tokens_used > 0


# ---------------------------------------------------------------------------
# 5. Web tools E2E (real HTTP)
# ---------------------------------------------------------------------------


class TestWebToolsE2E:
    def test_web_browse_extracts_content(self):
        """Web browse fetches real URL and extracts text."""
        from q3_ai_assistant.council.tools.web_browse import web_browse

        result = web_browse("https://httpbin.org/html")
        assert result.error is None
        assert "Herman Melville" in result.content
        assert result.source_type == "web"

    def test_web_browse_handles_404(self):
        """Web browse handles HTTP errors gracefully."""
        from q3_ai_assistant.council.tools.web_browse import web_browse

        result = web_browse("https://httpbin.org/status/404")
        assert result.error is not None
        assert "404" in result.error

    def test_web_browse_handles_unreachable(self):
        """Web browse handles DNS failures."""
        from q3_ai_assistant.council.tools.web_browse import web_browse

        result = web_browse("https://this-will-never-resolve-e2e.invalid")
        assert result.error is not None

    @pytest.mark.skipif(
        not settings.brave_search_api_key,
        reason="Q3_AI_BRAVE_SEARCH_API_KEY not set",
    )
    def test_web_search_returns_results(self):
        """Web search returns real results from Brave API."""
        from q3_ai_assistant.council.tools.web_search import web_search

        result = web_search("B3 bolsa de valores", max_results=3)
        assert result.error is None
        assert len(result.results) > 0
        assert result.results[0].url.startswith("http")


# ---------------------------------------------------------------------------
# 6. Intent detection completeness
# ---------------------------------------------------------------------------


class TestIntentDetectionE2E:
    """Tests that the intent detection pipeline correctly identifies
    patterns that would trigger internal tool usage."""

    def test_strategy_intent_triggers_tool(self):
        from q3_ai_assistant.modules.free_chat import _detect_intent, _gather_tool_context

        intent = _detect_intent("Explique a Magic Formula")
        assert intent["type"] == "strategy"

        # Verify the context builder would call get_strategy_definition
        class FakeSession:
            def query(self, *a, **kw):
                class Q:
                    def filter_by(self, **kw): return self
                    def first(self): return None
                return Q()

        context, tools = _gather_tool_context(FakeSession(), intent)
        assert "get_strategy_definition" in tools

    def test_company_intent_triggers_tools(self):
        from q3_ai_assistant.modules.free_chat import _detect_intent

        intent = _detect_intent("Analise a empresa RENT3")
        assert intent["type"] == "company"
        assert "RENT3" in intent["tickers"]

    def test_lineage_intent_detected(self):
        from q3_ai_assistant.modules.free_chat import _detect_intent

        intent = _detect_intent("De onde vem o dado de ROIC de BBAS3?")
        assert intent["type"] == "lineage"
        assert "BBAS3" in intent["tickers"]
        assert "roic" in intent["metrics"]
