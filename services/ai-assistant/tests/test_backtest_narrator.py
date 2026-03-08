from __future__ import annotations

import uuid

from q3_ai_assistant.llm.mock_adapter import MockAdapter
from q3_ai_assistant.models.entities import AIModule, ConfidenceLevel, NoteType
from q3_ai_assistant.modules.backtest_narrator import (
    compute_input_hash,
    detect_concerns,
    narrate_backtest,
)
from tests.conftest import SAMPLE_BACKTEST_CONFIG, SAMPLE_BACKTEST_METRICS


class TestDetectConcerns:
    def test_no_concerns_normal_metrics(self):
        concerns = detect_concerns(SAMPLE_BACKTEST_METRICS)
        assert len(concerns) == 0

    def test_overfitting_signal(self):
        metrics = {**SAMPLE_BACKTEST_METRICS, "sharpe": 2.5}
        concerns = detect_concerns(metrics)
        types = [c["type"] for c in concerns]
        assert "overfitting" in types

    def test_drawdown_risk(self):
        metrics = {**SAMPLE_BACKTEST_METRICS, "max_drawdown": -0.45}
        concerns = detect_concerns(metrics)
        types = [c["type"] for c in concerns]
        assert "drawdown_risk" in types

    def test_low_hit_rate(self):
        metrics = {**SAMPLE_BACKTEST_METRICS, "hit_rate": 0.35}
        concerns = detect_concerns(metrics)
        types = [c["type"] for c in concerns]
        assert "low_hit_rate" in types

    def test_cost_sensitivity(self):
        metrics = {**SAMPLE_BACKTEST_METRICS, "turnover": 2.5}
        concerns = detect_concerns(metrics)
        types = [c["type"] for c in concerns]
        assert "cost_sensitivity" in types

    def test_data_quality(self):
        metrics = {**SAMPLE_BACKTEST_METRICS, "cagr": 0.60}
        concerns = detect_concerns(metrics)
        types = [c["type"] for c in concerns]
        assert "data_quality" in types

    def test_multiple_concerns(self):
        metrics = {"sharpe": 3.0, "max_drawdown": -0.50, "cagr": 0.80, "hit_rate": 0.30, "turnover": 3.0}
        concerns = detect_concerns(metrics)
        assert len(concerns) == 5

    def test_boundary_values(self):
        # Exactly at thresholds — should NOT trigger
        metrics = {"sharpe": 2.0, "max_drawdown": -0.30, "hit_rate": 0.40, "turnover": 2.0, "cagr": 0.50}
        concerns = detect_concerns(metrics)
        assert len(concerns) == 0

    def test_empty_metrics(self):
        concerns = detect_concerns({})
        assert concerns == []


class TestComputeInputHash:
    def test_deterministic(self):
        h1 = compute_input_hash(SAMPLE_BACKTEST_METRICS, SAMPLE_BACKTEST_CONFIG)
        h2 = compute_input_hash(SAMPLE_BACKTEST_METRICS, SAMPLE_BACKTEST_CONFIG)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_input(self):
        h1 = compute_input_hash(SAMPLE_BACKTEST_METRICS, SAMPLE_BACKTEST_CONFIG)
        h2 = compute_input_hash({**SAMPLE_BACKTEST_METRICS, "cagr": 0.99}, SAMPLE_BACKTEST_CONFIG)
        assert h1 != h2


class TestNarrateBacktest:
    def test_full_pipeline(self, session):
        adapter = MockAdapter()
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()

        suggestion = narrate_backtest(
            session, adapter, None,
            tenant_id=tenant_id,
            backtest_run_id=run_id,
            metrics=SAMPLE_BACKTEST_METRICS,
            config=SAMPLE_BACKTEST_CONFIG,
        )

        assert suggestion.module == AIModule.backtest_narrator
        assert suggestion.tenant_id == tenant_id
        assert suggestion.trigger_entity_id == run_id
        assert suggestion.confidence in (ConfidenceLevel.high, ConfidenceLevel.medium, ConfidenceLevel.low)
        assert suggestion.structured_output is not None
        assert "quality_score" in suggestion.structured_output

    def test_creates_research_notes(self, session):
        adapter = MockAdapter()
        suggestion = narrate_backtest(
            session, adapter, None,
            tenant_id=uuid.uuid4(),
            backtest_run_id=uuid.uuid4(),
            metrics=SAMPLE_BACKTEST_METRICS,
            config=SAMPLE_BACKTEST_CONFIG,
        )
        session.flush()

        note_types = [n.note_type for n in suggestion.research_notes]
        assert NoteType.summary in note_types

    def test_concerns_persisted_as_notes(self, session):
        adapter = MockAdapter()
        metrics_with_concerns = {**SAMPLE_BACKTEST_METRICS, "sharpe": 3.0, "max_drawdown": -0.50}
        suggestion = narrate_backtest(
            session, adapter, None,
            tenant_id=uuid.uuid4(),
            backtest_run_id=uuid.uuid4(),
            metrics=metrics_with_concerns,
            config=SAMPLE_BACKTEST_CONFIG,
        )
        session.flush()

        concern_notes = [n for n in suggestion.research_notes if n.note_type == NoteType.concern]
        assert len(concern_notes) >= 2

    def test_empty_metrics(self, session):
        adapter = MockAdapter()
        suggestion = narrate_backtest(
            session, adapter, None,
            tenant_id=uuid.uuid4(),
            backtest_run_id=uuid.uuid4(),
            metrics={},
            config=SAMPLE_BACKTEST_CONFIG,
        )
        assert suggestion.input_snapshot["metrics"] == {}

    def test_input_snapshot_includes_concerns(self, session):
        adapter = MockAdapter()
        metrics_with_concerns = {**SAMPLE_BACKTEST_METRICS, "sharpe": 3.0}
        suggestion = narrate_backtest(
            session, adapter, None,
            tenant_id=uuid.uuid4(),
            backtest_run_id=uuid.uuid4(),
            metrics=metrics_with_concerns,
            config=SAMPLE_BACKTEST_CONFIG,
        )
        assert len(suggestion.input_snapshot["concerns"]) > 0
