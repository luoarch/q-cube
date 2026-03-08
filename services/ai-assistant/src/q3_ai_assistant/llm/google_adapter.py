"""Google Gemini LLM adapter."""

from __future__ import annotations

import logging
import time

from google import genai
from google.genai.types import GenerateContentConfig
from tenacity import retry, stop_after_attempt, wait_exponential

from q3_ai_assistant.config import Settings
from q3_ai_assistant.llm.adapter import LLMResponse

logger = logging.getLogger(__name__)

_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
}


class GoogleAdapter:
    def __init__(self, settings: Settings) -> None:
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model = settings.google_model
        self.max_tokens = settings.max_tokens
        self.temperature = settings.temperature

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        start = time.monotonic()
        resp = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
            ),
        )
        latency_ms = (time.monotonic() - start) * 1000

        prompt_tokens = resp.usage_metadata.prompt_token_count if resp.usage_metadata else 0
        completion_tokens = resp.usage_metadata.candidates_token_count if resp.usage_metadata else 0
        tokens_used = prompt_tokens + completion_tokens
        cost_usd = self._estimate_cost(prompt_tokens, completion_tokens)

        text = resp.text or ""

        logger.info(
            "llm_response",
            extra={
                "provider": "google",
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
            model_version=self.model,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=round(latency_ms, 1),
            cost_usd=round(cost_usd, 6),
        )

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_rate, output_rate = _PRICING.get(self.model, (1.25, 10.00))
        return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
