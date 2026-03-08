from __future__ import annotations

from q3_ai_assistant.config import Settings
from q3_ai_assistant.llm.adapter import LLMResponse
from q3_ai_assistant.llm.factory import create_adapter
from q3_ai_assistant.llm.mock_adapter import MockAdapter


class TestMockAdapter:
    def test_returns_llm_response(self):
        adapter = MockAdapter()
        resp = adapter.generate("system", "user")
        assert isinstance(resp, LLMResponse)
        assert resp.model == "mock-v1"
        assert resp.tokens_used == 150
        assert resp.cost_usd == 0.0

    def test_ranking_prompt_returns_ranking_output(self):
        adapter = MockAdapter()
        resp = adapter.generate("You explain ranking results", "Ranked assets: ...")
        import json
        parsed = json.loads(resp.text)
        assert "summary" in parsed
        assert "sector_analysis" in parsed
        assert "position_explanations" in parsed

    def test_backtest_prompt_returns_backtest_output(self):
        adapter = MockAdapter()
        resp = adapter.generate("You narrate backtest results", "Backtest metrics: ...")
        import json
        parsed = json.loads(resp.text)
        assert "narrative" in parsed
        assert "highlights" in parsed
        assert "concerns" in parsed

    def test_call_count_increments(self):
        adapter = MockAdapter()
        assert adapter._call_count == 0
        adapter.generate("sys", "usr")
        assert adapter._call_count == 1
        adapter.generate("sys", "usr")
        assert adapter._call_count == 2


class TestFactory:
    def test_creates_mock_adapter(self):
        s = Settings(llm_provider="mock")
        adapter = create_adapter(s)
        assert isinstance(adapter, MockAdapter)

    def test_unknown_provider_raises(self):
        s = Settings(llm_provider="unknown")
        try:
            create_adapter(s)
            assert False, "Should have raised"
        except ValueError as e:
            assert "Unknown LLM provider" in str(e)


class TestLLMResponse:
    def test_frozen_dataclass(self):
        resp = LLMResponse(
            text="hello",
            model="test",
            model_version="v1",
            tokens_used=10,
            prompt_tokens=5,
            completion_tokens=5,
            latency_ms=1.0,
            cost_usd=0.001,
        )
        assert resp.text == "hello"
        try:
            resp.text = "modified"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_cost_tracking(self):
        resp = LLMResponse(
            text="test",
            model="gpt-4o-mini",
            model_version="gpt-4o-mini-2024-07-18",
            tokens_used=1100,
            prompt_tokens=1000,
            completion_tokens=100,
            latency_ms=500.0,
            cost_usd=0.00021,
        )
        assert resp.cost_usd == 0.00021
        assert resp.prompt_tokens + resp.completion_tokens == resp.tokens_used
