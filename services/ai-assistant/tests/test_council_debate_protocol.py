"""Tests for the 4-round debate protocol (Sprint 4)."""

from __future__ import annotations

import json


from q3_ai_assistant.council.debate.protocol import (
    MAX_CONTESTATIONS_PER_AGENT,
    build_contestation_prompt,
    build_reply_prompt,
    parse_contestations,
    parse_replies,
)
from q3_ai_assistant.council.types import AgentOpinion, AgentVerdict


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
        unknowns=["unknown"],
        what_would_change_my_mind=["condition"],
        investor_fit=["moderate"],
    )


# ---------------------------------------------------------------------------
# build_contestation_prompt
# ---------------------------------------------------------------------------

class TestBuildContestationPrompt:
    def test_includes_agent_id(self):
        own = _make_opinion("barsi", AgentVerdict.buy)
        others = [_make_opinion("graham", AgentVerdict.avoid)]
        prompt = build_contestation_prompt("barsi", own, others)
        assert "barsi" in prompt
        assert "CONTESTACAO" in prompt

    def test_includes_other_opinions(self):
        own = _make_opinion("barsi", AgentVerdict.buy)
        others = [
            _make_opinion("graham", AgentVerdict.avoid),
            _make_opinion("greenblatt", AgentVerdict.watch),
        ]
        prompt = build_contestation_prompt("barsi", own, others)
        assert "graham" in prompt
        assert "greenblatt" in prompt
        assert "avoid" in prompt

    def test_includes_max_contestations(self):
        own = _make_opinion("barsi")
        others = [_make_opinion("graham")]
        prompt = build_contestation_prompt("barsi", own, others)
        assert str(MAX_CONTESTATIONS_PER_AGENT) in prompt


# ---------------------------------------------------------------------------
# build_reply_prompt
# ---------------------------------------------------------------------------

class TestBuildReplyPrompt:
    def test_includes_agent_id(self):
        own = _make_opinion("graham")
        contestations = [{"fromAgent": "barsi", "point": "roe too low", "counterArgument": "disagree"}]
        prompt = build_reply_prompt("graham", own, contestations)
        assert "graham" in prompt
        assert "REPLICA" in prompt

    def test_includes_contestations(self):
        own = _make_opinion("graham")
        contestations = [{"fromAgent": "barsi", "point": "test point", "counterArgument": "test arg"}]
        prompt = build_reply_prompt("graham", own, contestations)
        assert "test point" in prompt

    def test_includes_current_confidence(self):
        own = _make_opinion("graham")
        own_confidence = own.confidence
        prompt = build_reply_prompt("graham", own, [])
        assert str(own_confidence) in prompt


# ---------------------------------------------------------------------------
# parse_contestations
# ---------------------------------------------------------------------------

class TestParseContestations:
    def test_valid_json(self):
        raw = json.dumps({
            "contestations": [
                {"targetAgent": "graham", "point": "high leverage", "counterArgument": "not really"}
            ]
        })
        result = parse_contestations(raw)
        assert len(result) == 1
        assert result[0]["targetAgent"] == "graham"

    def test_limits_to_max(self):
        raw = json.dumps({
            "contestations": [
                {"targetAgent": "a", "point": "p1", "counterArgument": "c1"},
                {"targetAgent": "b", "point": "p2", "counterArgument": "c2"},
                {"targetAgent": "c", "point": "p3", "counterArgument": "c3"},
            ]
        })
        result = parse_contestations(raw)
        assert len(result) == MAX_CONTESTATIONS_PER_AGENT

    def test_invalid_json(self):
        assert parse_contestations("not json at all") == []

    def test_empty_contestations(self):
        raw = json.dumps({"contestations": []})
        assert parse_contestations(raw) == []

    def test_json_embedded_in_text(self):
        raw = 'Here is my response:\n{"contestations": [{"targetAgent": "x", "point": "y", "counterArgument": "z"}]}\nEnd.'
        result = parse_contestations(raw)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# parse_replies
# ---------------------------------------------------------------------------

class TestParseReplies:
    def test_valid_json(self):
        raw = json.dumps({
            "replies": [
                {"fromAgent": "barsi", "response": "I maintain my position", "confidenceAdjustment": 0}
            ],
            "adjustedConfidence": 65,
        })
        replies, conf = parse_replies(raw, 70)
        assert len(replies) == 1
        assert conf == 65

    def test_default_confidence_on_missing(self):
        raw = json.dumps({"replies": []})
        replies, conf = parse_replies(raw, 70)
        assert conf == 70

    def test_invalid_json(self):
        replies, conf = parse_replies("garbage", 70)
        assert replies == []
        assert conf == 70

    def test_clamps_confidence(self):
        raw = json.dumps({"replies": [], "adjustedConfidence": 150})
        _, conf = parse_replies(raw, 70)
        assert conf == 100

        raw2 = json.dumps({"replies": [], "adjustedConfidence": -10})
        _, conf2 = parse_replies(raw2, 70)
        assert conf2 == 0
