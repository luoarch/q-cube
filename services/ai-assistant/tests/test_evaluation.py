from __future__ import annotations

from q3_ai_assistant.evaluation.evaluator import (
    RegressionDetector,
    evaluate_backtest_narrative,
    evaluate_ranking_explanation,
)


class TestRankingEvaluation:
    def test_perfect_output(self):
        input_data = {"ranked_assets": [{"ticker": "PETR4"}, {"ticker": "VALE3"}]}
        output = {
            "summary": "A comprehensive ranking analysis showing diversified sector allocation with strong metrics across the portfolio positions reviewed.",
            "sector_analysis": "Technology and Financials lead the ranking.",
            "position_explanations": [
                {"ticker": "PETR4", "explanation": "High earnings yield."},
                {"ticker": "VALE3", "explanation": "Strong ROC."},
            ],
        }
        score = evaluate_ranking_explanation(input_data, output)
        assert score.completeness == 1.0
        assert score.parseable is True
        assert score.coherence == 1.0
        assert score.groundedness == 1.0
        assert score.overall >= 0.9

    def test_missing_fields(self):
        input_data = {"ranked_assets": [{"ticker": "PETR4"}]}
        output = {"summary": "Short analysis of this ranking with diversified portfolio across sectors."}
        score = evaluate_ranking_explanation(input_data, output)
        assert score.completeness < 1.0
        assert score.overall < 0.9

    def test_empty_output(self):
        score = evaluate_ranking_explanation({"ranked_assets": []}, {})
        assert score.completeness == 0.0
        assert score.overall == 0.0

    def test_ungrounded_tickers(self):
        input_data = {"ranked_assets": [{"ticker": "PETR4"}]}
        output = {
            "summary": "A comprehensive ranking analysis showing diversified sector allocation with strong metrics across the portfolio positions reviewed.",
            "sector_analysis": "Analysis",
            "position_explanations": [
                {"ticker": "FAKE3", "explanation": "Not in input."},
            ],
        }
        score = evaluate_ranking_explanation(input_data, output)
        assert score.groundedness == 0.0

    def test_short_summary_penalized(self):
        input_data = {"ranked_assets": []}
        output = {
            "summary": "Short.",
            "sector_analysis": "OK",
            "position_explanations": [],
        }
        score = evaluate_ranking_explanation(input_data, output)
        assert score.coherence < 1.0


class TestBacktestEvaluation:
    def test_perfect_output(self):
        input_data = {"metrics": {"cagr": 0.18, "sharpe": 1.2}}
        output = {
            "narrative": "The backtest demonstrates strong risk-adjusted returns over the test period with acceptable drawdown levels across different market conditions.",
            "highlights": [
                {"metric": "cagr", "value": 0.18, "interpretation": "Strong."},
                {"metric": "sharpe", "value": 1.2, "interpretation": "Good."},
            ],
            "concerns": [{"type": "none", "description": "No concerns", "severity": "low"}],
        }
        score = evaluate_backtest_narrative(input_data, output)
        assert score.completeness == 1.0
        assert score.groundedness == 1.0
        assert score.overall >= 0.9

    def test_missing_fields(self):
        input_data = {"metrics": {}}
        output = {"narrative": "The backtest shows some interesting results that merit further investigation by the research team."}
        score = evaluate_backtest_narrative(input_data, output)
        assert score.completeness < 1.0

    def test_empty_output(self):
        score = evaluate_backtest_narrative({"metrics": {}}, {})
        assert score.completeness == 0.0


class TestRegressionDetector:
    def test_no_regression(self):
        detector = RegressionDetector(threshold=0.1)
        assert not detector.check([0.85, 0.90, 0.88], baseline_mean=0.85)

    def test_regression_detected(self):
        detector = RegressionDetector(threshold=0.1)
        assert detector.check([0.50, 0.55, 0.52], baseline_mean=0.85)

    def test_empty_recent_scores(self):
        detector = RegressionDetector(threshold=0.1)
        assert not detector.check([], baseline_mean=0.85)

    def test_zero_baseline(self):
        detector = RegressionDetector(threshold=0.1)
        assert not detector.check([0.5], baseline_mean=0.0)

    def test_exact_threshold(self):
        """10% drop from baseline should trigger."""
        detector = RegressionDetector(threshold=0.1)
        # baseline 1.0, recent 0.89 → drop = 0.11 > 0.1 → True
        assert detector.check([0.89], baseline_mean=1.0)

    def test_custom_threshold(self):
        detector = RegressionDetector(threshold=0.2)
        # 15% drop, threshold 20% → not triggered
        assert not detector.check([0.85], baseline_mean=1.0)
