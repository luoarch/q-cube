"""Template Method — fixed analysis pipeline for all council agents.

Pipeline:
  1. Load packet data (already done before agent is called)
  2. Check hard rejects (deterministic)
  3. Analyze with LLM (if not rejected or if rejected, analyze with locked verdict)
  4. Format opinion (fixed AgentOpinion schema)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from q3_ai_assistant.council.packet import AssetAnalysisPacket
from q3_ai_assistant.council.types import AgentOpinion, AgentVerdict
from q3_ai_assistant.llm.adapter import LLMResponse
from q3_ai_assistant.llm.cascade import CascadeResult, CascadeRouter
from q3_ai_assistant.security.output_sanitizer import sanitize_llm_output

logger = logging.getLogger(__name__)


class BaseCouncilAgent(ABC):
    """Base class for all council specialist agents (Template Method pattern)."""

    agent_id: str
    profile_version: int = 1
    prompt_version: int = 1

    @abstractmethod
    def get_hard_rejects(self) -> list[HardReject]:
        """Return hard reject rules for this agent."""
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        ...

    @abstractmethod
    def build_user_prompt(self, packet: AssetAnalysisPacket) -> str:
        """Build the user prompt from the asset packet."""
        ...

    def analyze(
        self,
        packet: AssetAnalysisPacket,
        cascade: CascadeRouter,
    ) -> AgentOpinion:
        """Template method: run the full analysis pipeline."""
        # Step 1: Check hard rejects (deterministic)
        triggered_rejects = self._check_hard_rejects(packet)

        # Step 2: Determine if verdict is locked
        verdict_locked = AgentVerdict.avoid if triggered_rejects else None

        # Step 3: Build prompts
        system_prompt = self.get_system_prompt()
        if triggered_rejects:
            system_prompt += (
                "\n\nIMPORTANT: The following hard reject rules were triggered. "
                "Your verdict MUST be 'avoid'. Explain why these rejects apply:\n"
                + "\n".join(f"- {r.code}: {r.description}" for r in triggered_rejects)
            )

        user_prompt = self.build_user_prompt(packet)

        # Step 4: Call LLM via cascade
        try:
            result = cascade.generate(
                system_prompt,
                user_prompt,
                validate_output=self._validate_output,
            )
            opinion = self._parse_response(result, packet, triggered_rejects, verdict_locked)
        except Exception as exc:
            logger.error("Agent %s failed for %s: %s", self.agent_id, packet.ticker, exc)
            opinion = self._fallback_opinion(packet, triggered_rejects, str(exc))

        return opinion

    def _check_hard_rejects(self, packet: AssetAnalysisPacket) -> list[HardReject]:
        """Run deterministic hard reject checks."""
        triggered: list[HardReject] = []
        for reject in self.get_hard_rejects():
            if reject.check(packet):
                triggered.append(reject)
        return triggered

    def _validate_output(self, response: LLMResponse) -> bool:
        """Validate LLM output can be parsed."""
        parsed = sanitize_llm_output(response.text)
        return parsed is not None and "thesis" in parsed

    def _parse_response(
        self,
        result: CascadeResult,
        packet: AssetAnalysisPacket,
        rejects: list[HardReject],
        locked_verdict: AgentVerdict | None,
    ) -> AgentOpinion:
        """Parse LLM response into structured AgentOpinion."""
        parsed = sanitize_llm_output(result.response.text)
        if parsed is None:
            return self._fallback_opinion(packet, rejects, "unparseable_output")

        verdict_str = parsed.get("verdict", "watch")
        if locked_verdict is not None:
            verdict = locked_verdict
        else:
            try:
                verdict = AgentVerdict(verdict_str)
            except ValueError:
                verdict = AgentVerdict.watch

        # Validate key_metrics_used against packet
        claimed_metrics = parsed.get("keyMetricsUsed", [])
        available_metrics = set(packet.fundamentals.keys()) | set(packet.trends.keys())
        if packet.refiner_scores:
            available_metrics |= set(packet.refiner_scores.keys())
        validated_metrics = [m for m in claimed_metrics if m in available_metrics]

        return AgentOpinion(
            agent_id=self.agent_id,
            profile_version=self.profile_version,
            prompt_version=self.prompt_version,
            verdict=verdict,
            confidence=min(100, max(0, int(parsed.get("confidence", 50)))),
            data_reliability=packet.score_reliability,
            thesis=str(parsed.get("thesis", "")),
            reasons_for=parsed.get("reasonsFor", []),
            reasons_against=parsed.get("reasonsAgainst", []),
            key_metrics_used=validated_metrics,
            hard_rejects_triggered=[r.code for r in rejects],
            unknowns=parsed.get("unknowns", []),
            what_would_change_my_mind=parsed.get("whatWouldChangeMyMind", []),
            investor_fit=parsed.get("investorFit", []),
            provider_used=result.provider_used,
            model_used=result.model_used,
            fallback_level=result.fallback_level,
            tokens_used=result.response.tokens_used,
            cost_usd=result.response.cost_usd,
            latency_ms=result.response.latency_ms,
        )

    def _fallback_opinion(
        self,
        packet: AssetAnalysisPacket,
        rejects: list[HardReject],
        error: str,
    ) -> AgentOpinion:
        """Generate a safe fallback opinion when LLM fails."""
        if rejects:
            verdict = AgentVerdict.avoid
            thesis = f"Hard rejects triggered: {', '.join(r.code for r in rejects)}"
        else:
            verdict = AgentVerdict.insufficient_data
            thesis = f"Analysis unavailable due to: {error}"

        return AgentOpinion(
            agent_id=self.agent_id,
            profile_version=self.profile_version,
            prompt_version=self.prompt_version,
            verdict=verdict,
            confidence=0,
            data_reliability=packet.score_reliability,
            thesis=thesis,
            reasons_for=[],
            reasons_against=[],
            key_metrics_used=[],
            hard_rejects_triggered=[r.code for r in rejects],
            unknowns=["LLM analysis failed"],
            what_would_change_my_mind=[],
            investor_fit=[],
        )


class HardReject:
    """Deterministic rejection rule."""

    def __init__(self, code: str, description: str, check_fn: callable) -> None:
        self.code = code
        self.description = description
        self._check_fn = check_fn

    def check(self, packet: AssetAnalysisPacket) -> bool:
        """Returns True if this reject should trigger (verdict = avoid)."""
        try:
            return self._check_fn(packet)
        except Exception:
            return False
