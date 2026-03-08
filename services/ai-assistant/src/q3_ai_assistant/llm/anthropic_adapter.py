"""Anthropic (Claude) LLM adapter."""

from __future__ import annotations

import logging
import time

from anthropic import Anthropic, APIError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from q3_ai_assistant.config import Settings
from q3_ai_assistant.llm.adapter import LLMResponse

logger = logging.getLogger(__name__)

_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
}


class AnthropicAdapter:
    def __init__(self, settings: Settings) -> None:
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((RateLimitError, APIError)),
    )
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        start = time.monotonic()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        latency_ms = (time.monotonic() - start) * 1000

        prompt_tokens = resp.usage.input_tokens
        completion_tokens = resp.usage.output_tokens
        tokens_used = prompt_tokens + completion_tokens
        cost_usd = self._estimate_cost(prompt_tokens, completion_tokens)

        text = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text

        logger.info(
            "llm_response",
            extra={
                "provider": "anthropic",
                "model": self.model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": round(latency_ms, 1),
                "cost_usd": round(cost_usd, 6),
            },
        )

        return LLMResponse(
            text=text,
            model=self.model,
            model_version=resp.model,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=round(latency_ms, 1),
            cost_usd=round(cost_usd, 6),
        )

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_rate, output_rate = _PRICING.get(self.model, (3.00, 15.00))
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
