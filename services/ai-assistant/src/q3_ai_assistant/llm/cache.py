from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict

from q3_ai_assistant.llm.adapter import LLMAdapter, LLMResponse

logger = logging.getLogger(__name__)


class LLMCache:
    def __init__(self, redis_client: object, ttl_seconds: int = 86400) -> None:
        self.redis = redis_client
        self.ttl = ttl_seconds

    def cache_key(self, system_prompt: str, user_prompt: str, model: str) -> str:
        content = f"{model}:{system_prompt}:{user_prompt}"
        return f"ai:cache:{hashlib.sha256(content.encode()).hexdigest()}"

    def get_or_generate(
        self,
        adapter: LLMAdapter,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[LLMResponse, bool]:
        """Returns (response, cache_hit)."""
        key = self.cache_key(system_prompt, user_prompt, adapter.model)

        try:
            cached = self.redis.get(key)  # type: ignore[union-attr]
            if cached:
                data = json.loads(cached)
                logger.info("llm_cache_hit", extra={"key": key[:32]})
                return LLMResponse(**data), True
        except Exception:
            logger.warning("cache read failed, falling through to LLM")

        response = adapter.generate(system_prompt, user_prompt)

        try:
            self.redis.setex(key, self.ttl, json.dumps(asdict(response)))  # type: ignore[union-attr]
        except Exception:
            logger.warning("cache write failed")

        return response, False
