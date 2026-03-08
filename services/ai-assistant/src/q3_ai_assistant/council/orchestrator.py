"""Council Orchestrator — Mediator pattern for routing chat modes.

Routes:
  - free_chat:   tools + LLM synthesis
  - agent_solo:  single specialist agent
  - roundtable:  all 4 specialists + moderator
  - debate:      selected agents, 4-round protocol
  - comparison:  deterministic compare + agent opinions
"""

from __future__ import annotations

import logging
import uuid

from q3_ai_assistant.council.agent_factory import create_agent, create_specialists
from q3_ai_assistant.council.agents.moderator import ModeratorAgent
from q3_ai_assistant.council.debate.protocol import (
    build_contestation_prompt,
    build_reply_prompt,
    parse_contestations,
    parse_replies,
)
from q3_ai_assistant.council.packet import AssetAnalysisPacket
from q3_ai_assistant.council.types import (
    AgentOpinion,
    AuditTrail,
    ConflictEntry,
    CouncilMode,
    CouncilResult,
    CouncilScoreboard,
    DebateRound,
    ModeratorSynthesis,
)
from q3_ai_assistant.llm.cascade import CascadeRouter

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Este conteudo e meramente educacional e analitico, nao constituindo "
    "recomendacao de investimento personalizada. Os agentes sao inspirados "
    "em filosofias de investimento e nao representam pessoas reais. "
    "Consulte um profissional certificado antes de tomar decisoes de investimento."
)


class CouncilOrchestrator:
    """Central orchestrator for all council modes (Mediator pattern)."""

    def __init__(
        self,
        specialist_cascade: CascadeRouter,
        orchestrator_cascade: CascadeRouter,
    ) -> None:
        self._specialist_cascade = specialist_cascade
        self._orchestrator_cascade = orchestrator_cascade

    def run_solo(
        self,
        agent_id: str,
        packet: AssetAnalysisPacket,
    ) -> CouncilResult:
        """Single agent analysis."""
        agent = create_agent(agent_id)
        opinion = agent.analyze(packet, self._specialist_cascade)

        scoreboard = _build_scoreboard([opinion])
        return CouncilResult(
            session_id=str(uuid.uuid4()),
            mode=CouncilMode.solo,
            asset_ids=[packet.issuer_id],
            opinions=[opinion],
            scoreboard=scoreboard,
            conflict_matrix=[],
            moderator_synthesis=_empty_synthesis(),
            debate_log=None,
            disclaimer=DISCLAIMER,
            audit_trail=_build_audit([opinion]),
        )

    def run_roundtable(
        self,
        packet: AssetAnalysisPacket,
    ) -> CouncilResult:
        """All 4 specialists + moderator synthesis."""
        specialists = create_specialists()

        # Run all specialists (could be parallelized in future)
        opinions: list[AgentOpinion] = []
        for agent in specialists:
            opinion = agent.analyze(packet, self._specialist_cascade)
            opinions.append(opinion)

        # Run moderator synthesis
        moderator = ModeratorAgent()
        opinion_dicts = [_opinion_to_dict(o) for o in opinions]
        moderator.build_synthesis_prompt(packet, opinion_dicts)
        mod_opinion = moderator.analyze(packet, self._orchestrator_cascade)
        opinions.append(mod_opinion)

        scoreboard = _build_scoreboard(opinions)
        conflicts = _detect_conflicts(opinions)
        synthesis = _extract_synthesis(mod_opinion)

        return CouncilResult(
            session_id=str(uuid.uuid4()),
            mode=CouncilMode.roundtable,
            asset_ids=[packet.issuer_id],
            opinions=opinions,
            scoreboard=scoreboard,
            conflict_matrix=conflicts,
            moderator_synthesis=synthesis,
            debate_log=None,
            disclaimer=DISCLAIMER,
            audit_trail=_build_audit(opinions),
        )

    def run_debate(
        self,
        agent_ids: list[str],
        packet: AssetAnalysisPacket,
    ) -> CouncilResult:
        """Selected agents, 4-round debate protocol."""
        if len(agent_ids) < 2:
            raise ValueError("Debate requires at least 2 agents")

        agents = [create_agent(aid) for aid in agent_ids if aid != "moderator"]
        debate_log: list[DebateRound] = []

        # Round 1: Initial verdicts (independent)
        opinions: list[AgentOpinion] = []
        opinion_map: dict[str, AgentOpinion] = {}

        for agent in agents:
            opinion = agent.analyze(packet, self._specialist_cascade)
            opinions.append(opinion)
            opinion_map[agent.agent_id] = opinion
            debate_log.append(DebateRound(
                round_number=1,
                agent_id=agent.agent_id,
                content=opinion.thesis,
                target_agent_id=None,
                timestamp="",
            ))

        # Round 2: Contestation — each agent contests up to 2 points from others
        all_contestations: dict[str, list[dict]] = {}  # target_agent -> list of contestation dicts
        for agent in agents:
            own = opinion_map[agent.agent_id]
            others = [o for o in opinions if o.agent_id != agent.agent_id]
            prompt = build_contestation_prompt(agent.agent_id, own, others)
            try:
                result = self._specialist_cascade.generate(
                    agent.get_system_prompt(), prompt,
                )
                contestations = parse_contestations(result.response.text)
            except Exception:
                logger.warning("Contestation failed for %s", agent.agent_id)
                contestations = []

            for c in contestations:
                target = c.get("targetAgent", "")
                debate_log.append(DebateRound(
                    round_number=2,
                    agent_id=agent.agent_id,
                    content=c.get("counterArgument", ""),
                    target_agent_id=target,
                    timestamp="",
                ))
                all_contestations.setdefault(target, []).append({
                    "fromAgent": agent.agent_id,
                    "point": c.get("point", ""),
                    "counterArgument": c.get("counterArgument", ""),
                })

        # Round 3: Brief reply — each agent responds to contestations received
        for agent in agents:
            received = all_contestations.get(agent.agent_id, [])
            if not received:
                continue
            own = opinion_map[agent.agent_id]
            prompt = build_reply_prompt(agent.agent_id, own, received)
            try:
                result = self._specialist_cascade.generate(
                    agent.get_system_prompt(), prompt,
                )
                replies, adjusted_conf = parse_replies(result.response.text, own.confidence)
            except Exception:
                logger.warning("Reply failed for %s", agent.agent_id)
                replies = []
                adjusted_conf = own.confidence

            for r in replies:
                debate_log.append(DebateRound(
                    round_number=3,
                    agent_id=agent.agent_id,
                    content=r.get("response", ""),
                    target_agent_id=r.get("fromAgent"),
                    timestamp="",
                ))

            # Update confidence if adjusted
            if adjusted_conf != own.confidence:
                opinion_map[agent.agent_id] = AgentOpinion(
                    agent_id=own.agent_id,
                    profile_version=own.profile_version,
                    prompt_version=own.prompt_version,
                    verdict=own.verdict,
                    confidence=adjusted_conf,
                    data_reliability=own.data_reliability,
                    thesis=own.thesis,
                    reasons_for=own.reasons_for,
                    reasons_against=own.reasons_against,
                    key_metrics_used=own.key_metrics_used,
                    hard_rejects_triggered=own.hard_rejects_triggered,
                    unknowns=own.unknowns,
                    what_would_change_my_mind=own.what_would_change_my_mind,
                    investor_fit=own.investor_fit,
                    provider_used=own.provider_used,
                    model_used=own.model_used,
                    fallback_level=own.fallback_level,
                    tokens_used=own.tokens_used,
                    cost_usd=own.cost_usd,
                )

        # Rebuild opinions list with potentially adjusted confidence
        final_opinions = [opinion_map[a.agent_id] for a in agents]

        # Round 4: Moderator synthesis
        moderator = ModeratorAgent()
        mod_opinion = moderator.analyze(packet, self._orchestrator_cascade)
        final_opinions.append(mod_opinion)

        scoreboard = _build_scoreboard(final_opinions)
        conflicts = _detect_conflicts(final_opinions)
        synthesis = _extract_synthesis(mod_opinion)

        return CouncilResult(
            session_id=str(uuid.uuid4()),
            mode=CouncilMode.debate,
            asset_ids=[packet.issuer_id],
            opinions=final_opinions,
            scoreboard=scoreboard,
            conflict_matrix=conflicts,
            moderator_synthesis=synthesis,
            debate_log=debate_log,
            disclaimer=DISCLAIMER,
            audit_trail=_build_audit(final_opinions),
        )


def _build_scoreboard(opinions: list[AgentOpinion]) -> CouncilScoreboard:
    entries = [
        {"agentId": o.agent_id, "verdict": o.verdict.value, "confidence": o.confidence}
        for o in opinions
    ]
    verdicts = [o.verdict for o in opinions if o.agent_id != "moderator"]
    consensus = None
    consensus_strength = None
    if verdicts:
        from collections import Counter
        counts = Counter(verdicts)
        most_common = counts.most_common(1)[0]
        if most_common[1] / len(verdicts) >= 0.5:
            consensus = most_common[0]
            consensus_strength = most_common[1] / len(verdicts)

    return CouncilScoreboard(
        entries=entries,
        consensus=consensus,
        consensus_strength=consensus_strength,
    )


def _detect_conflicts(opinions: list[AgentOpinion]) -> list[ConflictEntry]:
    conflicts: list[ConflictEntry] = []
    specialist_opinions = [o for o in opinions if o.agent_id != "moderator"]

    for i, o1 in enumerate(specialist_opinions):
        for o2 in specialist_opinions[i + 1:]:
            if o1.verdict != o2.verdict:
                conflicts.append(ConflictEntry(
                    agent1=o1.agent_id,
                    agent2=o2.agent_id,
                    topic="verdict",
                    agent1_position=f"{o1.verdict.value} (confidence: {o1.confidence})",
                    agent2_position=f"{o2.verdict.value} (confidence: {o2.confidence})",
                ))
    return conflicts


def _extract_synthesis(mod_opinion: AgentOpinion) -> ModeratorSynthesis:
    """Extract structured synthesis from moderator opinion if available."""
    return ModeratorSynthesis(
        convergences=mod_opinion.reasons_for,
        divergences=mod_opinion.reasons_against,
        biggest_risk=mod_opinion.unknowns[0] if mod_opinion.unknowns else "",
        entry_conditions=mod_opinion.what_would_change_my_mind,
        exit_conditions=[],
        overall_assessment=mod_opinion.thesis,
    )


def _empty_synthesis() -> ModeratorSynthesis:
    return ModeratorSynthesis(
        convergences=[],
        divergences=[],
        biggest_risk="",
        entry_conditions=[],
        exit_conditions=[],
        overall_assessment="",
    )


def _opinion_to_dict(o: AgentOpinion) -> dict:
    return {
        "agentId": o.agent_id,
        "verdict": o.verdict.value,
        "confidence": o.confidence,
        "thesis": o.thesis,
        "reasonsFor": o.reasons_for,
        "reasonsAgainst": o.reasons_against,
        "keyMetricsUsed": o.key_metrics_used,
    }


def _build_audit(opinions: list[AgentOpinion]) -> AuditTrail:
    return AuditTrail(
        input_hash="",
        prompt_versions={o.agent_id: o.prompt_version for o in opinions},
        profile_versions={o.agent_id: o.profile_version for o in opinions},
        models_used={o.agent_id: o.model_used for o in opinions},
        providers_used={o.agent_id: o.provider_used for o in opinions},
        fallback_levels={o.agent_id: o.fallback_level for o in opinions},
        total_tokens=sum(o.tokens_used for o in opinions),
        total_cost_usd=sum(o.cost_usd for o in opinions),
        total_latency_ms=0,
    )
