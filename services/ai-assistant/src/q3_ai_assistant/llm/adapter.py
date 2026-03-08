from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    model_version: str
    tokens_used: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float


class LLMAdapter(Protocol):
    model: str

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse: ...
