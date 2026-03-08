from __future__ import annotations

from q3_ai_assistant.prompts import backtest as backtest_prompts
from q3_ai_assistant.prompts import ranking as ranking_prompts
from tests.conftest import SAMPLE_BACKTEST_CONFIG, SAMPLE_BACKTEST_METRICS, SAMPLE_RANKED_ASSETS


class TestRankingPrompts:
    def test_system_prompt_has_governance(self):
        assert "Never recommend trades" in ranking_prompts.SYSTEM_PROMPT
        assert "AI-generated" in ranking_prompts.SYSTEM_PROMPT
        assert "human review" in ranking_prompts.SYSTEM_PROMPT

    def test_system_prompt_specifies_json_schema(self):
        assert '"summary"' in ranking_prompts.SYSTEM_PROMPT
        assert '"sector_analysis"' in ranking_prompts.SYSTEM_PROMPT
        assert '"position_explanations"' in ranking_prompts.SYSTEM_PROMPT

    def test_user_prompt_includes_assets(self):
        analysis = {"sector_distribution": {}, "concentration_alerts": [], "outliers": [], "top5": [], "bottom5": []}
        prompt = ranking_prompts.build_user_prompt(SAMPLE_RANKED_ASSETS, analysis)
        assert "PETR4" in prompt
        assert "Ranked Assets" in prompt

    def test_user_prompt_includes_concentration(self):
        analysis = {
            "sector_distribution": {"Tech": {"count": 5, "pct": 0.5}},
            "concentration_alerts": ["Tech: 50% of positions (5/10)"],
            "outliers": [],
            "top5": [],
            "bottom5": [],
        }
        prompt = ranking_prompts.build_user_prompt(SAMPLE_RANKED_ASSETS[:5], analysis)
        assert "Concentration Alerts" in prompt
        assert "Tech: 50%" in prompt

    def test_user_prompt_includes_outliers(self):
        analysis = {
            "sector_distribution": {},
            "concentration_alerts": [],
            "outliers": [{"ticker": "OUT3", "metric": "earningsYield", "value": 0.9, "z_score": 3.5}],
            "top5": [],
            "bottom5": [],
        }
        prompt = ranking_prompts.build_user_prompt([], analysis)
        assert "Statistical Outliers" in prompt
        assert "OUT3" in prompt

    def test_empty_ranked_list(self):
        analysis = {"sector_distribution": {}, "concentration_alerts": [], "outliers": [], "top5": [], "bottom5": []}
        prompt = ranking_prompts.build_user_prompt([], analysis)
        assert "Ranked Assets" in prompt
        assert "JSON explanation" in prompt

    def test_prompt_version_defined(self):
        assert ranking_prompts.PROMPT_VERSION == "v1"


class TestBacktestPrompts:
    def test_system_prompt_has_governance(self):
        assert "Never recommend trades" in backtest_prompts.SYSTEM_PROMPT
        assert "AI-generated" in backtest_prompts.SYSTEM_PROMPT
        assert "human review" in backtest_prompts.SYSTEM_PROMPT

    def test_system_prompt_specifies_json_schema(self):
        assert '"narrative"' in backtest_prompts.SYSTEM_PROMPT
        assert '"highlights"' in backtest_prompts.SYSTEM_PROMPT
        assert '"concerns"' in backtest_prompts.SYSTEM_PROMPT

    def test_user_prompt_includes_metrics(self):
        prompt = backtest_prompts.build_user_prompt(SAMPLE_BACKTEST_METRICS, SAMPLE_BACKTEST_CONFIG, [])
        assert "cagr" in prompt
        assert "sharpe" in prompt
        assert "Backtest Metrics" in prompt

    def test_user_prompt_includes_config(self):
        prompt = backtest_prompts.build_user_prompt(SAMPLE_BACKTEST_METRICS, SAMPLE_BACKTEST_CONFIG, [])
        assert "magic_formula_brazil" in prompt
        assert "Backtest Configuration" in prompt

    def test_user_prompt_includes_concerns(self):
        concerns = [{"type": "overfitting", "description": "Sharpe too high", "severity": "high"}]
        prompt = backtest_prompts.build_user_prompt(SAMPLE_BACKTEST_METRICS, SAMPLE_BACKTEST_CONFIG, concerns)
        assert "Pre-computed Concerns" in prompt
        assert "overfitting" in prompt

    def test_empty_metrics(self):
        prompt = backtest_prompts.build_user_prompt({}, {}, [])
        assert "Backtest Metrics" in prompt
        assert "JSON narrative" in prompt

    def test_prompt_version_defined(self):
        assert backtest_prompts.PROMPT_VERSION == "v1"
