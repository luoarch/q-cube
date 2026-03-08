from __future__ import annotations

import logging
import time

from openai import APIError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from q3_ai_assistant.config import Settings
from q3_ai_assistant.llm.adapter import LLMResponse

logger = logging.getLogger(__name__)

# Approximate pricing per 1M tokens (USD) — gpt-4o-mini as of 2026-03
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


class OpenAIAdapter:
    def __init__(self, settings: Settings) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature
        self._retry_attempts = settings.retry_max_attempts

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((RateLimitError, APIError)),
    )
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        start = time.monotonic()
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        latency_ms = (time.monotonic() - start) * 1000

        usage = resp.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        tokens_used = prompt_tokens + completion_tokens
        cost_usd = self._estimate_cost(prompt_tokens, completion_tokens)

        text = resp.choices[0].message.content or ""

        logger.info(
            "llm_response",
            extra={
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
        input_rate, output_rate = _PRICING.get(self.model, (0.15, 0.60))
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
