"""Tests for CouncilOrchestrator — mode routing, scoreboard, conflicts, audit trail."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from q3_ai_assistant.council.orchestrator import (
    CouncilOrchestrator,
    DISCLAIMER,
    _build_scoreboard,
    _detect_conflicts,
    _extract_synthesis,
    _build_audit,
    _empty_synthesis,
    _opinion_to_dict,
)
from q3_ai_assistant.council.packet import AssetAnalysisPacket, PeriodValue
from q3_ai_assistant.council.types import (
    AgentOpinion,
    AgentVerdict,
    CouncilMode,
)
from q3_ai_assistant.llm.adapter import LLMResponse
from q3_ai_assistant.llm.cascade import CascadeRouter, ProviderEntry


def _make_packet() -> AssetAnalysisPacket:
    return AssetAnalysisPacket(
        issuer_id="id1",
        ticker="WEGE3",
        sector="Bens Industriais",
        subsector="Maquinas",
        classification="non_financial",
        fundamentals={"roe": 0.15, "ebit": 100_000},
        trends={"roe": [PeriodValue("2024-12-31", 0.15)]},
        refiner_scores=None,
        flags=None,
        market_cap=1e9,
        avg_daily_volume=1e6,
    )


def _make_opinion(agent_id: str, verdict: AgentVerdict = AgentVerdict.watch) -> AgentOpinion:
    return AgentOpinion(
        agent_id=agent_id,
        profile_version=1,
        prompt_version=1,
        verdict=verdict,
        confidence=70,
        data_reliability="high",
        thesis=f"Thesis from {agent_id}",
        reasons_for=["reason for"],
        reasons_against=["reason against"],
        key_metrics_used=["roe"],
        hard_rejects_triggered=[],
        unknowns=["some unknown"],
        what_would_change_my_mind=["condition"],
        investor_fit=["moderate"],
        provider_used="openai",
        model_used="gpt-5.4",
        fallback_level=0,
        tokens_used=100,
        cost_usd=0.01,
    )


def _mock_cascade() -> CascadeRouter:
    """Create a mock cascade that returns valid JSON opinions."""
    adapter = MagicMock()
    adapter.model = "mock-model"

    valid_json = json.dumps({
        "verdict": "watch",
        "confidence": 60,
        "thesis": "Mock thesis",
        "reasonsFor": ["reason"],
        "reasonsAgainst": ["risk"],
        "keyMetricsUsed": ["roe"],
        "unknowns": ["unknown"],
        "whatWouldChangeMyMind": ["condition"],
        "investorFit": ["moderate"],
    })
    adapter.generate.return_value = LLMResponse(
        text=valid_json,
        model="mock-model",
        model_version="1",
        tokens_used=50,
        prompt_tokens=30,
        completion_tokens=20,
        cost_usd=0.005,
        latency_ms=500,
    )

    entry = ProviderEntry(provider_name="mock", adapter=adapter, priority=0)
    return CascadeRouter(pool=[entry])


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------

class TestBuildScoreboard:
    def test_single_opinion(self):
        opinions = [_make_opinion("barsi", AgentVerdict.buy)]
        sb = _build_scoreboard(opinions)
        assert len(sb.entries) == 1
        assert sb.consensus == AgentVerdict.buy
        assert sb.consensus_strength == 1.0

    def test_unanimous_consensus(self):
        opinions = [
            _make_opinion("barsi", AgentVerdict.watch),
            _make_opinion("graham", AgentVerdict.watch),
            _make_opinion("greenblatt", AgentVerdict.watch),
        ]
        sb = _build_scoreboard(opinions)
        assert sb.consensus == AgentVerdict.watch
        assert sb.consensus_strength == 1.0

    def test_majority_consensus(self):
        opinions = [
            _make_opinion("barsi", AgentVerdict.buy),
            _make_opinion("graham", AgentVerdict.buy),
            _make_opinion("greenblatt", AgentVerdict.avoid),
            _make_opinion("buffett", AgentVerdict.watch),
        ]
        sb = _build_scoreboard(opinions)
        assert sb.consensus == AgentVerdict.buy
        assert sb.consensus_strength == 0.5

    def test_moderator_excluded_from_consensus(self):
        opinions = [
            _make_opinion("barsi", AgentVerdict.buy),
            _make_opinion("moderator", AgentVerdict.watch),
        ]
        sb = _build_scoreboard(opinions)
        assert sb.consensus == AgentVerdict.buy  # only barsi counted


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------

class TestDetectConflicts:
    def test_no_conflicts(self):
        opinions = [
            _make_opinion("barsi", AgentVerdict.watch),
            _make_opinion("graham", AgentVerdict.watch),
        ]
        assert _detect_conflicts(opinions) == []

    def test_detects_conflict(self):
        opinions = [
            _make_opinion("barsi", AgentVerdict.buy),
            _make_opinion("graham", AgentVerdict.avoid),
        ]
        conflicts = _detect_conflicts(opinions)
        assert len(conflicts) == 1
        assert conflicts[0].agent1 == "barsi"
        assert conflicts[0].agent2 == "graham"

    def test_moderator_excluded(self):
        opinions = [
            _make_opinion("barsi", AgentVerdict.buy),
            _make_opinion("moderator", AgentVerdict.watch),
        ]
        # Moderator is excluded from conflict detection
        assert _detect_conflicts(opinions) == []

    def test_multiple_conflicts(self):
        opinions = [
            _make_opinion("barsi", AgentVerdict.buy),
            _make_opinion("graham", AgentVerdict.avoid),
            _make_opinion("greenblatt", AgentVerdict.watch),
        ]
        conflicts = _detect_conflicts(opinions)
        # barsi vs graham, barsi vs greenblatt, graham vs greenblatt
        assert len(conflicts) == 3


# ---------------------------------------------------------------------------
# Synthesis extraction
# ---------------------------------------------------------------------------

class TestExtractSynthesis:
    def test_extracts_from_opinion(self):
        opinion = _make_opinion("moderator")
        synthesis = _extract_synthesis(opinion)
        assert synthesis.convergences == opinion.reasons_for
        assert synthesis.divergences == opinion.reasons_against
        assert synthesis.biggest_risk == opinion.unknowns[0]
        assert synthesis.entry_conditions == opinion.what_would_change_my_mind
        assert synthesis.overall_assessment == opinion.thesis

    def test_empty_unknowns(self):
        opinion = _make_opinion("moderator")
        opinion.unknowns = []
        synthesis = _extract_synthesis(opinion)
        assert synthesis.biggest_risk == ""


class TestEmptySynthesis:
    def test_empty(self):
        s = _empty_synthesis()
        assert s.convergences == []
        assert s.overall_assessment == ""


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class TestBuildAudit:
    def test_audit_aggregation(self):
        opinions = [
            _make_opinion("barsi"),
            _make_opinion("graham"),
        ]
        audit = _build_audit(opinions)
        assert audit.total_tokens == 200
        assert abs(audit.total_cost_usd - 0.02) < 0.001
        assert audit.prompt_versions["barsi"] == 1
        assert audit.providers_used["graham"] == "openai"
        assert audit.fallback_levels["barsi"] == 0


# ---------------------------------------------------------------------------
# Opinion serialization
# ---------------------------------------------------------------------------

class TestOpinionToDict:
    def test_camelcase_keys(self):
        opinion = _make_opinion("barsi")
        d = _opinion_to_dict(opinion)
        assert "agentId" in d
        assert "reasonsFor" in d
        assert "reasonsAgainst" in d
        assert "keyMetricsUsed" in d
        assert d["agentId"] == "barsi"


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------

class TestDisclaimer:
    def test_disclaimer_present(self):
        assert "educacional" in DISCLAIMER
        assert "recomendacao" in DISCLAIMER
        assert "investimento" in DISCLAIMER


# ---------------------------------------------------------------------------
# Orchestrator integration (with mock cascade)
# ---------------------------------------------------------------------------

class TestOrchestratorSolo:
    def test_run_solo_returns_result(self):
        cascade = _mock_cascade()
        orch = CouncilOrchestrator(
            specialist_cascade=cascade,
            orchestrator_cascade=cascade,
        )
        result = orch.run_solo("greenblatt", _make_packet())
        assert result.mode == CouncilMode.solo
        assert len(result.opinions) == 1
        assert result.opinions[0].agent_id == "greenblatt"
        assert result.disclaimer == DISCLAIMER
        assert result.debate_log is None


class TestOrchestratorRoundtable:
    def test_run_roundtable_returns_5_opinions(self):
        cascade = _mock_cascade()
        orch = CouncilOrchestrator(
            specialist_cascade=cascade,
            orchestrator_cascade=cascade,
        )
        result = orch.run_roundtable(_make_packet())
        assert result.mode == CouncilMode.roundtable
        assert len(result.opinions) == 5  # 4 specialists + moderator
        agent_ids = {o.agent_id for o in result.opinions}
        assert "moderator" in agent_ids
        assert result.scoreboard is not None
        assert result.audit_trail.total_tokens > 0


class TestOrchestratorDebate:
    def test_run_debate_returns_result(self):
        cascade = _mock_cascade()
        orch = CouncilOrchestrator(
            specialist_cascade=cascade,
            orchestrator_cascade=cascade,
        )
        result = orch.run_debate(["barsi", "graham"], _make_packet())
        assert result.mode == CouncilMode.debate
        assert len(result.opinions) == 3  # 2 debaters + moderator
        assert result.debate_log is not None
        assert len(result.debate_log) >= 2  # at least round 1 entries

    def test_debate_too_few_agents(self):
        cascade = _mock_cascade()
        orch = CouncilOrchestrator(
            specialist_cascade=cascade,
            orchestrator_cascade=cascade,
        )
        with pytest.raises(ValueError, match="at least 2"):
            orch.run_debate(["barsi"], _make_packet())
