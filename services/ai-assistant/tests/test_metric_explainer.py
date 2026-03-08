"""Tests for the metric explainer module (Sprint 2)."""

from __future__ import annotations



from q3_ai_assistant.modules.metric_explainer import (
    compute_input_hash,
    pre_analyze,
)
from q3_ai_assistant.prompts.metric import (
    METRIC_DEFINITIONS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    _flag_relates_to_metric,
    build_user_prompt,
)
from q3_ai_assistant.evaluation.evaluator import evaluate_metric_explanation


# ---------------------------------------------------------------------------
# pre_analyze
# ---------------------------------------------------------------------------

class TestPreAnalyze:
    def test_improving_trend(self):
        result = pre_analyze(
            "roic",
            0.15,
            [{"referenceDate": "2022-12-31", "value": 0.10},
             {"referenceDate": "2023-12-31", "value": 0.12},
             {"referenceDate": "2024-12-31", "value": 0.15}],
            None,
        )
        assert result["trend_direction"] == "improving"
        assert result["has_data"] is True
        assert result["periods_available"] == 3
        assert result["velocity_pct"] == 50.0

    def test_deteriorating_trend(self):
        result = pre_analyze(
            "gross_margin",
            0.20,
            [{"referenceDate": "2022-12-31", "value": 0.40},
             {"referenceDate": "2023-12-31", "value": 0.30},
             {"referenceDate": "2024-12-31", "value": 0.20}],
            None,
        )
        assert result["trend_direction"] == "deteriorating"
        assert result["velocity_pct"] == -50.0

    def test_stable_trend(self):
        result = pre_analyze(
            "net_margin",
            0.10,
            [{"referenceDate": "2022-12-31", "value": 0.10},
             {"referenceDate": "2024-12-31", "value": 0.10}],
            None,
        )
        assert result["trend_direction"] == "stable"

    def test_insufficient_data(self):
        result = pre_analyze("roic", 0.15, [{"referenceDate": "2024-12-31", "value": 0.15}], None)
        assert result["trend_direction"] == "insufficient_data"

    def test_no_data(self):
        result = pre_analyze("roic", None, [], None)
        assert result["has_data"] is False
        assert result["periods_available"] == 0

    def test_related_flags_detected(self):
        result = pre_analyze(
            "debt_to_ebitda",
            3.5,
            [{"referenceDate": "2024-12-31", "value": 3.5}],
            {"red": ["debt_ebitda_worsening", "ebit_deterioration"], "strength": ["deleveraging"]},
        )
        assert "debt_ebitda_worsening" in result["related_red_flags"]
        assert "ebit_deterioration" not in result["related_red_flags"]  # not related to debt_to_ebitda
        assert "deleveraging" in result["related_strength_flags"]

    def test_no_flags(self):
        result = pre_analyze("roic", 0.10, [], None)
        assert result["related_red_flags"] == []
        assert result["related_strength_flags"] == []


# ---------------------------------------------------------------------------
# compute_input_hash
# ---------------------------------------------------------------------------

class TestComputeInputHash:
    def test_deterministic(self):
        h1 = compute_input_hash("roic", 0.15, [{"referenceDate": "2024", "value": 0.15}])
        h2 = compute_input_hash("roic", 0.15, [{"referenceDate": "2024", "value": 0.15}])
        assert h1 == h2

    def test_different_metric(self):
        h1 = compute_input_hash("roic", 0.15, [])
        h2 = compute_input_hash("roe", 0.15, [])
        assert h1 != h2


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

class TestPrompts:
    def test_system_prompt_has_schema(self):
        assert "metricCode" in SYSTEM_PROMPT
        assert "definition" in SYSTEM_PROMPT
        assert "companyReading" in SYSTEM_PROMPT
        assert "trendInterpretation" in SYSTEM_PROMPT

    def test_system_prompt_educational(self):
        assert "nunca" in SYSTEM_PROMPT.lower() or "never" in SYSTEM_PROMPT.lower()

    def test_prompt_version(self):
        assert PROMPT_VERSION == "v1"

    def test_metric_definitions_exist(self):
        assert len(METRIC_DEFINITIONS) >= 10
        assert "roic" in METRIC_DEFINITIONS
        assert "debt_to_ebitda" in METRIC_DEFINITIONS

    def test_build_user_prompt_includes_metric(self):
        prompt = build_user_prompt(
            "roic", 0.15,
            [{"referenceDate": "2024-12-31", "value": 0.15}],
            None,
            {"ticker": "WEGE3", "sector": "Industrials", "classification": "non_financial"},
        )
        assert "roic" in prompt
        assert "WEGE3" in prompt
        assert "0.15" in prompt

    def test_build_user_prompt_includes_flags(self):
        prompt = build_user_prompt(
            "ebit_margin", 0.12,
            [{"referenceDate": "2024-12-31", "value": 0.12}],
            {"red": ["ebit_deterioration"], "strength": ["margin_resilient"]},
            {"ticker": "TEST3"},
        )
        assert "ebit_deterioration" in prompt
        assert "margin_resilient" in prompt

    def test_build_user_prompt_no_flags(self):
        prompt = build_user_prompt("roic", 0.15, [], None, {"ticker": "TEST3"})
        assert "Flags" not in prompt


# ---------------------------------------------------------------------------
# Flag-metric mapping
# ---------------------------------------------------------------------------

class TestFlagMetricMapping:
    def test_known_mapping(self):
        assert _flag_relates_to_metric("margin_compression", "gross_margin") is True
        assert _flag_relates_to_metric("margin_compression", "ebit_margin") is True
        assert _flag_relates_to_metric("margin_compression", "roic") is False

    def test_unknown_flag(self):
        assert _flag_relates_to_metric("unknown_flag", "roic") is False

    def test_deleveraging(self):
        assert _flag_relates_to_metric("deleveraging", "debt_to_ebitda") is True
        assert _flag_relates_to_metric("deleveraging", "net_debt") is True


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class TestEvaluateMetricExplanation:
    def test_complete_output(self):
        output = {
            "metricCode": "roic",
            "definition": "Retorno sobre capital investido",
            "companyReading": "A empresa apresenta ROIC de 15%, acima da media setorial",
            "trendInterpretation": "Tendencia de melhoria nos ultimos 3 anos",
            "implication": "Indica eficiencia crescente no uso do capital",
        }
        score = evaluate_metric_explanation({"metric_code": "roic"}, output)
        assert score.completeness == 1.0
        assert score.groundedness == 1.0
        assert score.overall >= 0.7

    def test_missing_fields(self):
        output = {"metricCode": "roic"}
        score = evaluate_metric_explanation({"metric_code": "roic"}, output)
        assert score.completeness < 1.0

    def test_wrong_metric_code(self):
        output = {
            "metricCode": "roe",
            "definition": "test",
            "companyReading": "test reading with enough chars",
            "trendInterpretation": "stable",
        }
        score = evaluate_metric_explanation({"metric_code": "roic"}, output)
        assert score.groundedness == 0.0
