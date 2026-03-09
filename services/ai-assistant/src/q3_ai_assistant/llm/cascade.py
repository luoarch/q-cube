"""Multi-provider cascade with automatic failover.

Implements the Q3 provider cascade strategy:
  Orchestrator: OpenAI gpt-5.4-pro -> Anthropic claude-opus-4-6 -> Google gemini-2.5-pro
  Specialist:   OpenAI gpt-5.4     -> Anthropic claude-sonnet-4-6 -> Google gemini-2.5-pro
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from q3_ai_assistant.llm.adapter import LLMAdapter, LLMResponse

logger = logging.getLogger(__name__)


class FailoverReason(str, Enum):
    none = "none"
    timeout = "timeout"
    server_error = "server_error"
    rate_limit = "rate_limit"
    auth_error = "auth_error"
    invalid_output = "invalid_output"
    latency_sla = "latency_sla"
    cost_budget = "cost_budget"
    unknown = "unknown"


@dataclass(frozen=True)
class CascadeResult:
    """Result from cascade with audit metadata."""
    response: LLMResponse
    provider_used: str
    model_used: str
    fallback_level: int  # 0 = primary, 1 = secondary, 2 = tertiary
    reason_for_fallback: str
    attempts: list[CascadeAttempt] = field(default_factory=list)


@dataclass(frozen=True)
class CascadeAttempt:
    provider: str
    model: str
    success: bool
    latency_ms: float
    error: str | None = None
    reason: str = "none"


@dataclass
class ProviderEntry:
    """A single provider in a cascade pool."""
    provider_name: str
    adapter: LLMAdapter
    priority: int
    latency_sla_ms: float = 30_000.0
    cost_budget_usd: float | None = None


class CascadeRouter:
    """Routes LLM calls through a prioritized cascade of providers.

    Tries each provider in priority order. On hard fail (timeout, 5xx, rate limit,
    auth error), falls back to the next. Preserves the same response contract
    regardless of which provider responds.
    """

    def __init__(self, pool: list[ProviderEntry]) -> None:
        self._pool = sorted(pool, key=lambda e: e.priority)
        if not self._pool:
            raise ValueError("Cascade pool must have at least one provider")

    @property
    def primary(self) -> ProviderEntry:
        return self._pool[0]

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        validate_output: Callable[[LLMResponse], bool] | None = None,
    ) -> CascadeResult:
        """Generate with automatic failover."""
        from q3_ai_assistant.observability.tracing import trace_span

        with trace_span("llm.cascade", pool_size=len(self._pool)) as span:
            result = self._generate_inner(system_prompt, user_prompt, validate_output=validate_output)
            span.attributes["provider"] = result.provider_used
            span.attributes["model"] = result.model_used
            span.attributes["fallback_level"] = result.fallback_level
            span.attributes["tokens"] = result.response.tokens_used
            span.attributes["cost_usd"] = result.response.cost_usd
            return result

    def _generate_inner(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        validate_output: Callable[[LLMResponse], bool] | None = None,
    ) -> CascadeResult:
        attempts: list[CascadeAttempt] = []
        last_error = ""

        for level, entry in enumerate(self._pool):
            start = time.monotonic()
            try:
                response = entry.adapter.generate(system_prompt, user_prompt)
                elapsed_ms = (time.monotonic() - start) * 1000

                # Soft fail: latency SLA exceeded
                if elapsed_ms > entry.latency_sla_ms:
                    logger.warning(
                        "cascade_latency_sla provider=%s model=%s elapsed=%.0fms sla=%.0fms",
                        entry.provider_name, entry.adapter.model,
                        elapsed_ms, entry.latency_sla_ms,
                    )
                    attempts.append(CascadeAttempt(
                        provider=entry.provider_name,
                        model=entry.adapter.model,
                        success=False,
                        latency_ms=elapsed_ms,
                        reason=FailoverReason.latency_sla.value,
                    ))
                    last_error = f"latency_sla:{elapsed_ms:.0f}ms>{entry.latency_sla_ms:.0f}ms"
                    continue

                # Soft fail: cost budget exceeded
                if entry.cost_budget_usd is not None and response.cost_usd > entry.cost_budget_usd:
                    logger.warning(
                        "cascade_cost_budget provider=%s cost=%.4f budget=%.4f",
                        entry.provider_name, response.cost_usd, entry.cost_budget_usd,
                    )
                    attempts.append(CascadeAttempt(
                        provider=entry.provider_name,
                        model=entry.adapter.model,
                        success=False,
                        latency_ms=response.latency_ms,
                        reason=FailoverReason.cost_budget.value,
                    ))
                    last_error = f"cost_budget:{response.cost_usd:.4f}>{entry.cost_budget_usd:.4f}"
                    continue

                # Soft fail: output validation
                if validate_output is not None and not validate_output(response):
                    logger.warning(
                        "cascade_invalid_output provider=%s model=%s",
                        entry.provider_name, entry.adapter.model,
                    )
                    attempts.append(CascadeAttempt(
                        provider=entry.provider_name,
                        model=entry.adapter.model,
                        success=False,
                        latency_ms=response.latency_ms,
                        reason=FailoverReason.invalid_output.value,
                    ))
                    last_error = "invalid_output"
                    continue

                # Success
                attempts.append(CascadeAttempt(
                    provider=entry.provider_name,
                    model=entry.adapter.model,
                    success=True,
                    latency_ms=response.latency_ms,
                ))

                reason = last_error if level > 0 else "none"
                return CascadeResult(
                    response=response,
                    provider_used=entry.provider_name,
                    model_used=entry.adapter.model,
                    fallback_level=level,
                    reason_for_fallback=reason,
                    attempts=attempts,
                )

            except Exception as exc:  # noqa: BLE001
                elapsed_ms = (time.monotonic() - start) * 1000
                reason = _classify_error(exc)
                logger.warning(
                    "cascade_error provider=%s model=%s reason=%s error=%s",
                    entry.provider_name, entry.adapter.model, reason, str(exc)[:200],
                )
                attempts.append(CascadeAttempt(
                    provider=entry.provider_name,
                    model=entry.adapter.model,
                    success=False,
                    latency_ms=elapsed_ms,
                    error=str(exc)[:200],
                    reason=reason,
                ))
                last_error = f"{reason}:{str(exc)[:100]}"

        # All providers failed
        raise CascadeExhaustedError(
            f"All {len(self._pool)} providers failed. Last error: {last_error}",
            attempts=attempts,
        )


class CascadeExhaustedError(Exception):
    def __init__(self, message: str, attempts: list[CascadeAttempt] | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts or []


def _classify_error(exc: Exception) -> str:
    """Classify exception into a FailoverReason."""
    exc_type = type(exc).__name__.lower()
    exc_msg = str(exc).lower()

    if "timeout" in exc_type or "timeout" in exc_msg:
        return FailoverReason.timeout.value
    if "ratelimit" in exc_type or "rate_limit" in exc_msg or "429" in exc_msg:
        return FailoverReason.rate_limit.value
    if "auth" in exc_type or "401" in exc_msg or "403" in exc_msg:
        return FailoverReason.auth_error.value
    if "500" in exc_msg or "502" in exc_msg or "503" in exc_msg or "server" in exc_msg:
        return FailoverReason.server_error.value
    return FailoverReason.unknown.value
