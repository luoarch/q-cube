"""Tests for quality evaluation framework."""

from __future__ import annotations

from q3_ai_assistant.evaluation.quality import (
    BANNED_PHRASES,
    evaluate_council_result,
    evaluate_opinion,
)


def _complete_opinion(**overrides) -> dict:
    """Create a complete valid opinion for testing."""
    base = {
        "agentId": "greenblatt",
        "profileVersion": 1,
        "promptVersion": 1,
        "verdict": "buy",
        "confidence": 75,
        "dataReliability": "high",
        "thesis": "Strong ROIC and earnings yield indicate a quality company at a fair price.",
        "reasonsFor": ["High ROIC", "Attractive earnings yield"],
        "reasonsAgainst": ["Moderate debt levels"],
        "keyMetricsUsed": ["roic", "earnings_yield"],
        "hardRejectsTriggered": [],
        "unknowns": ["Future capex plans"],
        "whatWouldChangeMyMind": ["ROIC drops below 10%"],
        "investorFit": ["Quantitative value investors"],
    }
    base.update(overrides)
    return base


class TestEvaluateOpinion:
    def test_complete_opinion_scores_high(self):
        score = evaluate_opinion(_complete_opinion())
        assert score.completeness == 1.0
        assert score.overall >= 0.8

    def test_missing_fields_lowers_completeness(self):
        opinion = {"agentId": "greenblatt", "verdict": "buy"}
        score = evaluate_opinion(opinion)
        assert score.completeness < 1.0
        assert any("Missing fields" in i for i in score.issues)

    def test_unknown_metrics_lower_groundedness(self):
        opinion = _complete_opinion(keyMetricsUsed=["made_up_metric", "fake_ratio"])
        score = evaluate_opinion(opinion)
        assert score.groundedness < 1.0

    def test_valid_metrics_high_groundedness(self):
        opinion = _complete_opinion(keyMetricsUsed=["roic", "earnings_yield", "debt_to_ebitda"])
        score = evaluate_opinion(opinion)
        assert score.groundedness == 1.0

    def test_no_metrics_referenced(self):
        opinion = _complete_opinion(keyMetricsUsed=[])
        score = evaluate_opinion(opinion)
        assert score.groundedness == 0.5
        assert any("No key metrics" in i for i in score.issues)

    def test_packet_metrics_validation(self):
        packet = {"roic", "earnings_yield"}
        opinion = _complete_opinion(keyMetricsUsed=["roic", "roe"])
        score = evaluate_opinion(opinion, packet_metrics=packet)
        assert score.groundedness == 0.5  # 1 of 2 metrics valid

    def test_short_thesis_lowers_consistency(self):
        opinion = _complete_opinion(thesis="Short.")
        score = evaluate_opinion(opinion)
        assert score.consistency < 1.0

    def test_avoid_without_reasons_against(self):
        opinion = _complete_opinion(verdict="avoid", reasonsAgainst=[])
        score = evaluate_opinion(opinion)
        assert score.consistency < 1.0

    def test_buy_without_reasons_for(self):
        opinion = _complete_opinion(verdict="buy", reasonsFor=[])
        score = evaluate_opinion(opinion)
        assert score.consistency < 1.0

    def test_contradicting_reasons(self):
        opinion = _complete_opinion(
            reasonsFor=["High ROIC", "Strong margins"],
            reasonsAgainst=["High ROIC"],
        )
        score = evaluate_opinion(opinion)
        assert score.contradiction_free == 0.0

    def test_no_contradictions(self):
        opinion = _complete_opinion(
            reasonsFor=["High ROIC"],
            reasonsAgainst=["High debt"],
        )
        score = evaluate_opinion(opinion)
        assert score.contradiction_free == 1.0

    def test_banned_phrases_fail_regulatory(self):
        for phrase in BANNED_PHRASES[:3]:
            opinion = _complete_opinion(thesis=f"This is great. {phrase}! Do it.")
            score = evaluate_opinion(opinion)
            assert score.regulatory_compliance == 0.0, f"Failed for phrase: {phrase}"
            assert any("Banned phrases" in i for i in score.issues)

    def test_clean_text_passes_regulatory(self):
        opinion = _complete_opinion()
        score = evaluate_opinion(opinion)
        assert score.regulatory_compliance == 1.0

    def test_overall_is_weighted_average(self):
        opinion = _complete_opinion()
        score = evaluate_opinion(opinion)
        expected = (
            0.20 * score.completeness
            + 0.25 * score.groundedness
            + 0.20 * score.consistency
            + 0.15 * score.contradiction_free
            + 0.20 * score.regulatory_compliance
        )
        assert abs(score.overall - expected) < 0.001


class TestEvaluateCouncilResult:
    def test_no_opinions(self):
        result = evaluate_council_result({"opinions": []})
        assert result["overall"] == 0.0

    def test_with_opinions_and_disclaimer(self):
        result = evaluate_council_result({
            "opinions": [_complete_opinion(agentId="greenblatt"), _complete_opinion(agentId="buffett")],
            "disclaimer": "Este conteudo e educacional.",
        })
        assert result["overall"] > 0.7
        assert "greenblatt" in result["per_agent"]
        assert "buffett" in result["per_agent"]

    def test_missing_disclaimer_penalizes(self):
        result_with = evaluate_council_result({
            "opinions": [_complete_opinion()],
            "disclaimer": "Disclaimer text.",
        })
        result_without = evaluate_council_result({
            "opinions": [_complete_opinion()],
        })
        assert result_without["overall"] < result_with["overall"]
        assert any("Missing disclaimer" in i for i in result_without["issues"])

    def test_issues_include_agent_prefix(self):
        opinion = _complete_opinion(agentId="graham", thesis="Short.")
        result = evaluate_council_result({"opinions": [opinion], "disclaimer": "ok"})
        assert any("[graham]" in i for i in result["issues"])
