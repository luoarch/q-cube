"""Tests for Plan 2 monitoring module."""

from __future__ import annotations

from datetime import date, timedelta

from q3_quant_engine.thesis.monitoring import (
    IssuerRunData,
    ReviewQueue,
    RubricAgingReport,
    RubricRecord,
    RunDrift,
    RunMonitoringSummary,
    compute_review_queue,
    compute_rubric_aging,
    compute_run_drift,
    compute_run_monitoring,
)
from q3_quant_engine.thesis.types import ScoreConfidence, ScoreProvenance, ScoreSourceType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prov(src: str, conf: str = "low") -> ScoreProvenance:
    return ScoreProvenance(
        source_type=ScoreSourceType(src),
        source_version="test-v1",
        assessed_at="2026-03-01",
        confidence=ScoreConfidence(conf),
    )


def _rubric(
    issuer_id: str = "iss-1",
    ticker: str = "TEST3",
    dim: str = "usd_debt_exposure",
    src: str = "AI_ASSISTED",
    conf: str = "low",
    assessed_at: date | None = None,
    score: float = 45.0,
) -> RubricRecord:
    return RubricRecord(
        issuer_id=issuer_id,
        ticker=ticker,
        dimension_key=dim,
        source_type=src,
        confidence=conf,
        assessed_at=assessed_at,
        assessed_by="test",
        score=score,
    )


# ---------------------------------------------------------------------------
# Block 1: Run Monitoring Summary
# ---------------------------------------------------------------------------

class TestComputeRunMonitoring:
    def test_basic_summary(self):
        provenance = {
            "iss-1": {
                "direct_commodity_exposure_score": _prov("SECTOR_PROXY"),
                "usd_debt_exposure_score": _prov("RUBRIC_MANUAL", "medium"),
                "refinancing_stress_score": _prov("QUANTITATIVE", "high"),
            },
            "iss-2": {
                "direct_commodity_exposure_score": _prov("SECTOR_PROXY"),
                "usd_debt_exposure_score": _prov("DEFAULT"),
                "refinancing_stress_score": _prov("QUANTITATIVE", "high"),
            },
        }

        result = compute_run_monitoring("run-1", provenance)

        assert isinstance(result, RunMonitoringSummary)
        assert result.total_eligible == 2
        assert result.run_id == "run-1"
        # 3 dimensions
        assert len(result.dimension_coverage) == 3

    def test_provenance_mix_counts(self):
        provenance = {
            "iss-1": {
                "dim_a": _prov("QUANTITATIVE"),
                "dim_b": _prov("DEFAULT"),
            },
            "iss-2": {
                "dim_a": _prov("QUANTITATIVE"),
                "dim_b": _prov("SECTOR_PROXY"),
            },
        }

        result = compute_run_monitoring("run-1", provenance)

        assert result.provenance_mix["QUANTITATIVE"] == 2
        assert result.provenance_mix["DEFAULT"] == 1
        assert result.provenance_mix["SECTOR_PROXY"] == 1

    def test_evidence_quality_distribution(self):
        # iss-1: 2/3 QUANTITATIVE -> HIGH_EVIDENCE
        # iss-2: 0/3 quant/manual -> LOW_EVIDENCE
        provenance = {
            "iss-1": {
                "dim_a": _prov("QUANTITATIVE"),
                "dim_b": _prov("RUBRIC_MANUAL"),
                "dim_c": _prov("SECTOR_PROXY"),
            },
            "iss-2": {
                "dim_a": _prov("SECTOR_PROXY"),
                "dim_b": _prov("DEFAULT"),
                "dim_c": _prov("DERIVED"),
            },
        }

        result = compute_run_monitoring("run-1", provenance)

        assert result.evidence_quality_distribution["HIGH_EVIDENCE"] == 1
        assert result.evidence_quality_distribution["LOW_EVIDENCE"] == 1

    def test_empty_provenance(self):
        result = compute_run_monitoring("run-1", {})
        assert result.total_eligible == 0
        assert result.dimension_coverage == []

    def test_dimension_coverage_non_default_pct(self):
        provenance = {
            "iss-1": {"dim_a": _prov("QUANTITATIVE")},
            "iss-2": {"dim_a": _prov("DEFAULT")},
            "iss-3": {"dim_a": _prov("SECTOR_PROXY")},
        }

        result = compute_run_monitoring("run-1", provenance)

        dim_a = result.dimension_coverage[0]
        assert dim_a.dimension_key == "dim_a"
        assert dim_a.total_issuers == 3
        assert dim_a.non_default_pct == 66.7  # 2/3


# ---------------------------------------------------------------------------
# Block 2: Run Drift
# ---------------------------------------------------------------------------

class TestComputeRunDrift:
    def test_no_changes(self):
        current = [IssuerRunData("iss-1", "T1", "A_DIRECT", 30.0, 1)]
        previous = [IssuerRunData("iss-1", "T1", "A_DIRECT", 30.0, 1)]

        result = compute_run_drift("run-2", "run-1", current, previous)

        assert isinstance(result, RunDrift)
        assert result.bucket_changes == 0
        assert result.top10_entered == []
        assert result.top10_exited == []

    def test_bucket_change_detected(self):
        current = [IssuerRunData("iss-1", "T1", "C_NEUTRAL", 40.0, 5)]
        previous = [IssuerRunData("iss-1", "T1", "B_INDIRECT", 35.0, 3)]

        result = compute_run_drift("run-2", "run-1", current, previous)

        assert result.bucket_changes == 1
        assert len(result.bucket_change_details) == 1
        detail = result.bucket_change_details[0]
        assert detail.old_bucket == "B_INDIRECT"
        assert detail.new_bucket == "C_NEUTRAL"
        assert detail.fragility_delta == 5.0

    def test_new_and_dropped_issuers(self):
        current = [
            IssuerRunData("iss-1", "T1", "A_DIRECT", 30.0, 1),
            IssuerRunData("iss-3", "T3", "C_NEUTRAL", 50.0, 3),
        ]
        previous = [
            IssuerRunData("iss-1", "T1", "A_DIRECT", 30.0, 1),
            IssuerRunData("iss-2", "T2", "B_INDIRECT", 40.0, 2),
        ]

        result = compute_run_drift("run-2", "run-1", current, previous)

        assert result.new_issuers == ["T3"]
        assert result.dropped_issuers == ["T2"]

    def test_top10_changes(self):
        # Build 12 issuers, swap rank 10 and 11
        prev = [IssuerRunData(f"iss-{i}", f"T{i}", "C_NEUTRAL", 50.0, i) for i in range(1, 13)]
        curr = list(prev)
        # T10 drops to rank 12, T11 enters top 10
        curr[9] = IssuerRunData("iss-10", "T10", "C_NEUTRAL", 50.0, 12)
        curr[10] = IssuerRunData("iss-11", "T11", "C_NEUTRAL", 50.0, 10)
        curr[11] = IssuerRunData("iss-12", "T12", "C_NEUTRAL", 50.0, 11)

        result = compute_run_drift("run-2", "run-1", curr, prev)

        assert "T11" in result.top10_entered
        assert "T10" in result.top10_exited

    def test_fragility_delta_stats(self):
        current = [
            IssuerRunData("iss-1", "T1", "A_DIRECT", 35.0, 1),
            IssuerRunData("iss-2", "T2", "C_NEUTRAL", 60.0, 2),
        ]
        previous = [
            IssuerRunData("iss-1", "T1", "A_DIRECT", 30.0, 1),
            IssuerRunData("iss-2", "T2", "C_NEUTRAL", 50.0, 2),
        ]

        result = compute_run_drift("run-2", "run-1", current, previous)

        assert result.fragility_delta_avg == 7.5  # (5+10)/2
        assert result.fragility_delta_max == 10.0
        assert result.fragility_delta_min == 5.0

    def test_empty_runs(self):
        result = compute_run_drift("run-2", "run-1", [], [])
        assert result.bucket_changes == 0
        assert result.fragility_delta_avg is None


# ---------------------------------------------------------------------------
# Block 3: Rubric Aging
# ---------------------------------------------------------------------------

class TestComputeRubricAging:
    def test_fresh_rubrics_not_stale(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(assessed_at=date(2026, 3, 10)),
            _rubric(issuer_id="iss-2", ticker="T2", assessed_at=date(2026, 3, 1)),
        ]

        result = compute_rubric_aging(rubrics, stale_days=30, as_of=today)

        assert isinstance(result, RubricAgingReport)
        assert result.stale_count == 0
        assert result.stale_pct == 0.0

    def test_old_rubrics_flagged(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(assessed_at=date(2026, 1, 1)),  # 73 days old
            _rubric(issuer_id="iss-2", ticker="T2", assessed_at=date(2026, 3, 10)),  # 5 days
        ]

        result = compute_rubric_aging(rubrics, stale_days=30, as_of=today)

        assert result.stale_count == 1
        assert result.stale_rubrics[0].age_days == 73

    def test_no_assessed_at_is_stale(self):
        rubrics = [_rubric(assessed_at=None)]

        result = compute_rubric_aging(rubrics, stale_days=30, as_of=date(2026, 3, 15))

        assert result.stale_count == 1
        assert result.stale_rubrics[0].age_days is None

    def test_stale_by_dimension(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(dim="usd_debt_exposure", assessed_at=date(2025, 12, 1)),
            _rubric(issuer_id="iss-2", dim="usd_debt_exposure", assessed_at=date(2025, 12, 5)),
            _rubric(issuer_id="iss-3", dim="usd_import_dependence", assessed_at=date(2025, 11, 1)),
        ]

        result = compute_rubric_aging(rubrics, stale_days=30, as_of=today)

        assert result.stale_by_dimension["usd_debt_exposure"] == 2
        assert result.stale_by_dimension["usd_import_dependence"] == 1

    def test_empty_rubrics(self):
        result = compute_rubric_aging([], stale_days=30)
        assert result.total_active_rubrics == 0
        assert result.stale_count == 0


# ---------------------------------------------------------------------------
# Block 4: Review Queue
# ---------------------------------------------------------------------------

class TestComputeReviewQueue:
    def test_low_conf_and_stale_is_high_priority(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(conf="low", assessed_at=date(2025, 12, 1)),  # low + stale = HIGH
        ]

        result = compute_review_queue(rubrics, stale_days=30, as_of=today)

        assert isinstance(result, ReviewQueue)
        assert result.high_priority == 1
        assert result.items[0].priority == "HIGH"

    def test_low_conf_only_is_medium(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(conf="low", assessed_at=date(2026, 3, 10)),  # low conf, fresh = MEDIUM
        ]

        result = compute_review_queue(rubrics, stale_days=30, as_of=today)

        assert result.medium_priority == 1
        assert result.items[0].priority == "MEDIUM"

    def test_stale_only_is_medium(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(conf="medium", assessed_at=date(2025, 12, 1)),  # stale, medium conf = MEDIUM
        ]

        result = compute_review_queue(rubrics, stale_days=30, as_of=today)

        assert result.medium_priority == 1

    def test_bucket_changed_is_high_priority(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(issuer_id="iss-1", conf="medium", assessed_at=date(2026, 3, 10)),
        ]

        drift = RunDrift(
            current_run_id="run-2",
            previous_run_id="run-1",
            bucket_changes=1,
            bucket_change_details=[
                IssuerRunData("iss-1", "TEST3", "C_NEUTRAL", 50.0, 5),  # type: ignore[arg-type]
            ],
            top10_entered=[], top10_exited=[],
            top20_entered=[], top20_exited=[],
            new_issuers=[], dropped_issuers=[],
            fragility_delta_avg=None, fragility_delta_max=None, fragility_delta_min=None,
        )

        # We need IssuerDrift not IssuerRunData in bucket_change_details
        from q3_quant_engine.thesis.monitoring import IssuerDrift
        drift.bucket_change_details = [
            IssuerDrift(
                issuer_id="iss-1", ticker="TEST3",
                old_bucket="B_INDIRECT", new_bucket="C_NEUTRAL",
                bucket_changed=True,
                old_fragility=35.0, new_fragility=50.0,
                fragility_delta=15.0,
                old_rank=3, new_rank=5, rank_delta=2,
            ),
        ]

        result = compute_review_queue(rubrics, drift=drift, stale_days=30, as_of=today)

        assert result.high_priority == 1
        assert "bucket changed" in result.items[0].reasons

    def test_ai_assisted_is_low_priority(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(conf="medium", src="AI_ASSISTED", assessed_at=date(2026, 3, 10)),
        ]

        result = compute_review_queue(rubrics, stale_days=30, as_of=today)

        assert result.low_priority == 1
        assert "AI_ASSISTED" in result.items[0].reasons[0]

    def test_sorted_by_priority_then_age(self):
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(issuer_id="iss-1", conf="medium", src="AI_ASSISTED", assessed_at=date(2026, 3, 10)),  # LOW
            _rubric(issuer_id="iss-2", conf="low", assessed_at=date(2025, 12, 1)),  # HIGH (low + stale)
            _rubric(issuer_id="iss-3", conf="low", assessed_at=date(2026, 3, 5)),  # MEDIUM (low conf only)
        ]

        result = compute_review_queue(rubrics, stale_days=30, as_of=today)

        assert result.items[0].priority == "HIGH"
        assert result.items[0].issuer_id == "iss-2"
        assert result.items[1].priority == "MEDIUM"
        assert result.items[2].priority == "LOW"

    def test_no_rubrics_empty_queue(self):
        result = compute_review_queue([], stale_days=30)
        assert result.total_items == 0

    def test_high_conf_manual_fresh_not_in_queue(self):
        """RUBRIC_MANUAL with high confidence and fresh date should not appear."""
        today = date(2026, 3, 15)
        rubrics = [
            _rubric(conf="high", src="RUBRIC_MANUAL", assessed_at=date(2026, 3, 10)),
        ]

        result = compute_review_queue(rubrics, stale_days=30, as_of=today)

        # Should not be in queue (no low conf, not stale, no drift, not AI_ASSISTED)
        assert result.total_items == 0
