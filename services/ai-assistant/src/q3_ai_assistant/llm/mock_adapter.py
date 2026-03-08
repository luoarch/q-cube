from __future__ import annotations

import json

from q3_ai_assistant.llm.adapter import LLMResponse

MOCK_RANKING_OUTPUT = json.dumps({
    "summary": "The ranking shows a diversified portfolio across multiple sectors with strong earnings yield and return on capital metrics.",
    "sector_analysis": "Technology leads with 25% of positions, followed by Financials at 20%. No sector exceeds the 30% concentration threshold.",
    "outlier_notes": [],
    "position_explanations": [
        {"ticker": "MOCK3", "explanation": "Ranks highly due to strong earnings yield of 15% and ROC of 25%."},
    ],
})

MOCK_BACKTEST_OUTPUT = json.dumps({
    "narrative": "The backtest shows a CAGR of 18.5% with a maximum drawdown of -22.3%, indicating moderate risk-adjusted returns over the test period.",
    "highlights": [
        {"metric": "cagr", "value": 0.185, "interpretation": "Strong absolute return above the benchmark."},
        {"metric": "sharpe", "value": 1.2, "interpretation": "Acceptable risk-adjusted performance."},
    ],
    "concerns": [],
})


class MockAdapter:
    def __init__(self, model: str = "mock-v1") -> None:
        self.model = model
        self._call_count = 0

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        self._call_count += 1

        if "ranking" in system_prompt.lower() or "ranking" in user_prompt.lower():
            text = MOCK_RANKING_OUTPUT
        else:
            text = MOCK_BACKTEST_OUTPUT

        return LLMResponse(
            text=text,
            model=self.model,
            model_version="mock-v1.0",
            tokens_used=150,
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=5.0,
            cost_usd=0.0,
        )
