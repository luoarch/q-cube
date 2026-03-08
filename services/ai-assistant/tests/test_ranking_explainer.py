from __future__ import annotations

import uuid

from q3_ai_assistant.llm.mock_adapter import MockAdapter
from q3_ai_assistant.models.entities import AIModule, ConfidenceLevel, ExplanationType, NoteType
from q3_ai_assistant.modules.ranking_explainer import (
    compute_input_hash,
    explain_ranking,
    pre_analyze,
)
from tests.conftest import SAMPLE_RANKED_ASSETS


class TestPreAnalyze:
    def test_sector_distribution(self):
        analysis = pre_analyze(SAMPLE_RANKED_ASSETS)
        assert "sector_distribution" in analysis
        assert "Financeiro" in analysis["sector_distribution"]
        assert analysis["sector_distribution"]["Financeiro"]["count"] == 3

    def test_concentration_alert_triggered(self):
        # 4 out of 10 in same sector = 40% > 30%
        concentrated = [
            {"rank": i, "ticker": f"T{i}", "name": f"Name{i}", "sector": "Tech", "earningsYield": 0.1, "returnOnCapital": 0.2}
            for i in range(1, 5)
        ] + [
            {"rank": i, "ticker": f"T{i}", "name": f"Name{i}", "sector": f"Other{i}", "earningsYield": 0.1, "returnOnCapital": 0.2}
            for i in range(5, 11)
        ]
        analysis = pre_analyze(concentrated)
        assert len(analysis["concentration_alerts"]) > 0
        assert "Tech" in analysis["concentration_alerts"][0]

    def test_no_concentration_alert(self):
        analysis = pre_analyze(SAMPLE_RANKED_ASSETS)
        # Financeiro has 3/10 = 30%, exactly at threshold, not above
        assert all("Financeiro" not in a for a in analysis["concentration_alerts"])

    def test_outlier_detection(self):
        assets = SAMPLE_RANKED_ASSETS.copy()
        # Add extreme outlier
        assets.append({"rank": 11, "ticker": "OUT3", "name": "Outlier", "sector": "X", "earningsYield": 0.90, "returnOnCapital": 0.10})
        analysis = pre_analyze(assets)
        outlier_tickers = [o["ticker"] for o in analysis["outliers"]]
        assert "OUT3" in outlier_tickers

    def test_top5_bottom5(self):
        analysis = pre_analyze(SAMPLE_RANKED_ASSETS)
        assert len(analysis["top5"]) == 5
        assert analysis["top5"][0]["rank"] == 1
        assert len(analysis["bottom5"]) == 5

    def test_empty_list(self):
        analysis = pre_analyze([])
        assert analysis["sector_distribution"] == {}
        assert analysis["concentration_alerts"] == []
        assert analysis["outliers"] == []
        assert analysis["top5"] == []
        assert analysis["bottom5"] == []


class TestComputeInputHash:
    def test_deterministic(self):
        h1 = compute_input_hash(SAMPLE_RANKED_ASSETS)
        h2 = compute_input_hash(SAMPLE_RANKED_ASSETS)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_input_different_hash(self):
        h1 = compute_input_hash(SAMPLE_RANKED_ASSETS)
        h2 = compute_input_hash(SAMPLE_RANKED_ASSETS[:5])
        assert h1 != h2


class TestExplainRanking:
    def test_full_pipeline(self, session):
        adapter = MockAdapter()
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()

        suggestion = explain_ranking(
            session, adapter, None,
            tenant_id=tenant_id,
            strategy_run_id=run_id,
            ranked_assets=SAMPLE_RANKED_ASSETS,
        )

        assert suggestion.module == AIModule.ranking_explainer
        assert suggestion.tenant_id == tenant_id
        assert suggestion.trigger_entity_id == run_id
        assert suggestion.confidence in (ConfidenceLevel.high, ConfidenceLevel.medium, ConfidenceLevel.low)
        assert suggestion.structured_output is not None
        assert "quality_score" in suggestion.structured_output
        assert suggestion.tokens_used > 0
        assert suggestion.model_used == "mock-v1"

    def test_creates_explanations(self, session):
        adapter = MockAdapter()
        suggestion = explain_ranking(
            session, adapter, None,
            tenant_id=uuid.uuid4(),
            strategy_run_id=uuid.uuid4(),
            ranked_assets=SAMPLE_RANKED_ASSETS,
        )
        session.flush()

        # MockAdapter returns at least one position_explanation
        assert len(suggestion.explanations) >= 1
        assert suggestion.explanations[0].explanation_type == ExplanationType.position

    def test_creates_research_notes(self, session):
        adapter = MockAdapter()
        suggestion = explain_ranking(
            session, adapter, None,
            tenant_id=uuid.uuid4(),
            strategy_run_id=uuid.uuid4(),
            ranked_assets=SAMPLE_RANKED_ASSETS,
        )
        session.flush()

        note_types = [n.note_type for n in suggestion.research_notes]
        assert NoteType.summary in note_types

    def test_empty_ranked_assets(self, session):
        adapter = MockAdapter()
        suggestion = explain_ranking(
            session, adapter, None,
            tenant_id=uuid.uuid4(),
            strategy_run_id=uuid.uuid4(),
            ranked_assets=[],
        )
        assert suggestion.input_snapshot["ranked_assets"] == []

    def test_idempotent_hash(self, session):
        """Same input produces same input_hash."""
        adapter = MockAdapter()
        s1 = explain_ranking(
            session, adapter, None,
            tenant_id=uuid.uuid4(),
            strategy_run_id=uuid.uuid4(),
            ranked_assets=SAMPLE_RANKED_ASSETS,
        )
        # Compute hash independently
        from q3_ai_assistant.modules.ranking_explainer import compute_input_hash
        from q3_ai_assistant.security.input_guard import validate_ranking_input
        expected_hash = compute_input_hash(validate_ranking_input(SAMPLE_RANKED_ASSETS))
        assert s1.input_hash == expected_hash
