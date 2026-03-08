"""Tests for council agent factory, base pipeline, and orchestrator (Sprint 4)."""

from __future__ import annotations

import pytest

from q3_ai_assistant.council.agent_factory import (
    ALL_AGENT_IDS,
    SPECIALIST_IDS,
    create_agent,
    create_specialists,
)
from q3_ai_assistant.council.agent_base import BaseCouncilAgent
from q3_ai_assistant.council.agents.barsi import BarsiAgent
from q3_ai_assistant.council.agents.graham import GrahamAgent
from q3_ai_assistant.council.agents.greenblatt import GreenblattAgent
from q3_ai_assistant.council.agents.buffett import BuffettAgent
from q3_ai_assistant.council.agents.moderator import ModeratorAgent
from q3_ai_assistant.council.packet import AssetAnalysisPacket, PeriodValue
from q3_ai_assistant.council.types import AgentVerdict


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestAgentFactory:
    def test_create_all_agents(self):
        for aid in ALL_AGENT_IDS:
            agent = create_agent(aid)
            assert isinstance(agent, BaseCouncilAgent)
            assert agent.agent_id == aid

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            create_agent("unknown_agent")

    def test_create_specialists_returns_4(self):
        specs = create_specialists()
        assert len(specs) == 4
        ids = {a.agent_id for a in specs}
        assert ids == set(SPECIALIST_IDS)

    def test_specialist_ids(self):
        assert SPECIALIST_IDS == ["barsi", "graham", "greenblatt", "buffett"]

    def test_all_agent_ids(self):
        assert "moderator" in ALL_AGENT_IDS
        assert len(ALL_AGENT_IDS) == 5


# ---------------------------------------------------------------------------
# Agent types
# ---------------------------------------------------------------------------

class TestAgentTypes:
    def test_barsi_type(self):
        assert isinstance(create_agent("barsi"), BarsiAgent)

    def test_graham_type(self):
        assert isinstance(create_agent("graham"), GrahamAgent)

    def test_greenblatt_type(self):
        assert isinstance(create_agent("greenblatt"), GreenblattAgent)

    def test_buffett_type(self):
        assert isinstance(create_agent("buffett"), BuffettAgent)

    def test_moderator_type(self):
        assert isinstance(create_agent("moderator"), ModeratorAgent)


# ---------------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------------

class TestAgentConfig:
    @pytest.mark.parametrize("agent_id", SPECIALIST_IDS)
    def test_specialists_have_hard_rejects(self, agent_id: str):
        agent = create_agent(agent_id)
        rejects = agent.get_hard_rejects()
        assert len(rejects) >= 1, f"{agent_id} should have at least 1 hard reject"

    def test_moderator_has_no_hard_rejects(self):
        agent = create_agent("moderator")
        assert agent.get_hard_rejects() == []

    @pytest.mark.parametrize("agent_id", ALL_AGENT_IDS)
    def test_all_agents_have_system_prompt(self, agent_id: str):
        agent = create_agent(agent_id)
        prompt = agent.get_system_prompt()
        assert len(prompt) > 50
        # Should not recommend buy/sell
        assert "DEVE retornar um JSON" in prompt or "Voce e o Moderador" in prompt

    @pytest.mark.parametrize("agent_id", ALL_AGENT_IDS)
    def test_all_agents_have_version(self, agent_id: str):
        agent = create_agent(agent_id)
        assert agent.profile_version >= 1
        assert agent.prompt_version >= 1


# ---------------------------------------------------------------------------
# Packet SSOT
# ---------------------------------------------------------------------------

class TestPacket:
    def test_to_dict_basic(self):
        packet = AssetAnalysisPacket(
            issuer_id="id1",
            ticker="WEGE3",
            sector="Bens Industriais",
            subsector="Maquinas",
            classification="non_financial",
            fundamentals={"roe": 0.15},
            trends={"roe": [PeriodValue("2024-12-31", 0.15)]},
            refiner_scores=None,
            flags=None,
            market_cap=1e9,
            avg_daily_volume=1e6,
        )
        d = packet.to_dict()
        assert d["ticker"] == "WEGE3"
        assert d["classification"] == "non_financial"
        assert d["fundamentals"]["roe"] == 0.15
        assert len(d["trends"]["roe"]) == 1
        assert d["trends"]["roe"][0]["value"] == 0.15

    def test_to_dict_camelcase_keys(self):
        packet = AssetAnalysisPacket(
            issuer_id="id1",
            ticker="TEST3",
            sector="s",
            subsector="ss",
            classification="non_financial",
            fundamentals={},
            trends={},
            refiner_scores={"earnings_quality": 0.8},
            flags={"red": ["flag1"], "strength": []},
            market_cap=None,
            avg_daily_volume=None,
            score_reliability="high",
        )
        d = packet.to_dict()
        assert "refinerScores" in d
        assert "marketCap" in d
        assert "scoreReliability" in d
        assert "avgDailyVolume" in d


# ---------------------------------------------------------------------------
# Debate protocol
# ---------------------------------------------------------------------------

class TestDebateProtocol:
    def test_validate_too_few(self):
        from q3_ai_assistant.council.debate.protocol import validate_debate_config
        with pytest.raises(ValueError, match="at least 2"):
            validate_debate_config(["barsi"])

    def test_validate_too_many(self):
        from q3_ai_assistant.council.debate.protocol import validate_debate_config
        with pytest.raises(ValueError, match="at most 4"):
            validate_debate_config(["barsi", "graham", "greenblatt", "buffett", "extra"])

    def test_validate_moderator_excluded(self):
        from q3_ai_assistant.council.debate.protocol import validate_debate_config
        with pytest.raises(ValueError, match="Moderator"):
            validate_debate_config(["barsi", "moderator"])

    def test_validate_ok(self):
        from q3_ai_assistant.council.debate.protocol import validate_debate_config
        validate_debate_config(["barsi", "graham"])  # no exception

    def test_constants(self):
        from q3_ai_assistant.council.debate.protocol import MAX_ROUNDS, MAX_CONTESTATIONS_PER_AGENT
        assert MAX_ROUNDS == 4
        assert MAX_CONTESTATIONS_PER_AGENT == 2


# ---------------------------------------------------------------------------
# Council types
# ---------------------------------------------------------------------------

class TestCouncilTypes:
    def test_verdict_values(self):
        assert AgentVerdict.buy.value == "buy"
        assert AgentVerdict.watch.value == "watch"
        assert AgentVerdict.avoid.value == "avoid"
        assert AgentVerdict.insufficient_data.value == "insufficient_data"

    def test_verdict_from_string(self):
        assert AgentVerdict("buy") == AgentVerdict.buy

    def test_verdict_invalid_raises(self):
        with pytest.raises(ValueError):
            AgentVerdict("hold")
