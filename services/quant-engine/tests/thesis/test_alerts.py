"""Tests for Plan 2 automated alerts (F3.3)."""

from __future__ import annotations

from q3_quant_engine.thesis.alerts import compute_run_alerts
from q3_quant_engine.thesis.monitoring import (
    IssuerDrift,
    ReviewQueue,
    RubricAgingReport,
    RunDrift,
    RunMonitoringSummary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_monitoring(
    total_eligible: int = 50,
    confidence_distribution: dict[str, int] | None = None,
) -> RunMonitoringSummary:
    return RunMonitoringSummary(
        run_id="run-1",
        total_eligible=total_eligible,
        dimension_coverage=[],
        provenance_mix={},
        provenance_mix_pct={},
        confidence_distribution=confidence_distribution or {"high": 30, "medium": 15, "low": 5},
        evidence_quality_distribution={},
        evidence_quality_pct={},
    )


def _make_drift(
    bucket_changes: int = 0,
    bucket_change_details: list[IssuerDrift] | None = None,
    top10_entered: list[str] | None = None,
    top10_exited: list[str] | None = None,
) -> RunDrift:
    return RunDrift(
        current_run_id="run-2",
        previous_run_id="run-1",
        bucket_changes=bucket_changes,
        bucket_change_details=bucket_change_details or [],
        top10_entered=top10_entered or [],
        top10_exited=top10_exited or [],
        top20_entered=[],
        top20_exited=[],
        new_issuers=[],
        dropped_issuers=[],
        fragility_delta_avg=None,
        fragility_delta_max=None,
        fragility_delta_min=None,
    )


def _make_aging(
    stale_count: int = 0,
    total_active: int = 100,
    stale_pct: float | None = None,
) -> RubricAgingReport:
    pct = stale_pct if stale_pct is not None else (stale_count / total_active * 100 if total_active > 0 else 0.0)
    return RubricAgingReport(
        stale_threshold_days=30,
        total_active_rubrics=total_active,
        stale_count=stale_count,
        stale_pct=round(pct, 1),
        stale_by_dimension={"direct_commodity_exposure": stale_count},
        stale_rubrics=[],
    )


def _make_review_queue(high: int = 0, medium: int = 0, low: int = 0) -> ReviewQueue:
    return ReviewQueue(
        total_items=high + medium + low,
        high_priority=high,
        medium_priority=medium,
        low_priority=low,
        items=[],
    )


def _make_issuer_drift(
    issuer_id: str = "iss-1",
    ticker: str = "TICK3",
    old_bucket: str = "A_DIRECT",
    new_bucket: str = "D_FRAGILE",
    bucket_changed: bool = True,
) -> IssuerDrift:
    return IssuerDrift(
        issuer_id=issuer_id,
        ticker=ticker,
        old_bucket=old_bucket,
        new_bucket=new_bucket,
        bucket_changed=bucket_changed,
        old_fragility=30.0,
        new_fragility=80.0,
        fragility_delta=50.0,
        old_rank=5,
        new_rank=15,
        rank_delta=10,
    )


# ---------------------------------------------------------------------------
# Tests: BUCKET_DRIFT_HIGH
# ---------------------------------------------------------------------------

class TestBucketDrift:
    def test_no_alert_below_threshold(self):
        drift = _make_drift(bucket_changes=4)
        monitoring = _make_monitoring(total_eligible=50)  # 8%
        alerts = compute_run_alerts(monitoring=monitoring, drift=drift)
        assert not any(a.code == "BUCKET_DRIFT_HIGH" for a in alerts)

    def test_warning_at_10_pct(self):
        drift = _make_drift(bucket_changes=5)
        monitoring = _make_monitoring(total_eligible=50)  # 10%
        alerts = compute_run_alerts(monitoring=monitoring, drift=drift)
        bucket_alerts = [a for a in alerts if a.code == "BUCKET_DRIFT_HIGH"]
        assert len(bucket_alerts) == 1
        assert bucket_alerts[0].severity == "WARNING"

    def test_critical_at_20_pct(self):
        drift = _make_drift(bucket_changes=10)
        monitoring = _make_monitoring(total_eligible=50)  # 20%
        alerts = compute_run_alerts(monitoring=monitoring, drift=drift)
        bucket_alerts = [a for a in alerts if a.code == "BUCKET_DRIFT_HIGH"]
        assert len(bucket_alerts) == 1
        assert bucket_alerts[0].severity == "CRITICAL"

    def test_no_alert_without_monitoring(self):
        """Without monitoring, total_eligible=0, so no bucket drift alert."""
        drift = _make_drift(bucket_changes=10)
        alerts = compute_run_alerts(drift=drift)
        assert not any(a.code == "BUCKET_DRIFT_HIGH" for a in alerts)


# ---------------------------------------------------------------------------
# Tests: TOP10_CHANGED
# ---------------------------------------------------------------------------

class TestTop10Changed:
    def test_no_alert_when_stable(self):
        drift = _make_drift()
        alerts = compute_run_alerts(drift=drift)
        assert not any(a.code == "TOP10_CHANGED" for a in alerts)

    def test_warning_on_any_change(self):
        drift = _make_drift(top10_entered=["VALE3"], top10_exited=["PETR4"])
        alerts = compute_run_alerts(drift=drift)
        top10 = [a for a in alerts if a.code == "TOP10_CHANGED"]
        assert len(top10) == 1
        assert top10[0].severity == "WARNING"

    def test_critical_on_3_changes(self):
        drift = _make_drift(
            top10_entered=["VALE3", "ITUB4", "BBDC4"],
            top10_exited=["PETR4", "ABEV3", "WEGE3"],
        )
        alerts = compute_run_alerts(drift=drift)
        top10 = [a for a in alerts if a.code == "TOP10_CHANGED"]
        assert len(top10) == 1
        assert top10[0].severity == "CRITICAL"
        assert top10[0].metric_value == 3.0


# ---------------------------------------------------------------------------
# Tests: LOW_CONFIDENCE_SURGE
# ---------------------------------------------------------------------------

class TestLowConfidenceSurge:
    def test_no_alert_below_threshold(self):
        monitoring = _make_monitoring(confidence_distribution={"high": 80, "medium": 15, "low": 5})
        alerts = compute_run_alerts(monitoring=monitoring)
        assert not any(a.code == "LOW_CONFIDENCE_SURGE" for a in alerts)

    def test_warning_at_10pp(self):
        monitoring = _make_monitoring(confidence_distribution={"high": 40, "medium": 40, "low": 20})
        # low = 20% of 100 total
        alerts = compute_run_alerts(monitoring=monitoring)
        low_conf = [a for a in alerts if a.code == "LOW_CONFIDENCE_SURGE"]
        assert len(low_conf) == 1
        assert low_conf[0].severity == "CRITICAL"  # 20% >= 20pp

    def test_warning_at_exact_10pp(self):
        monitoring = _make_monitoring(confidence_distribution={"high": 50, "medium": 40, "low": 10})
        alerts = compute_run_alerts(monitoring=monitoring)
        low_conf = [a for a in alerts if a.code == "LOW_CONFIDENCE_SURGE"]
        assert len(low_conf) == 1
        assert low_conf[0].severity == "WARNING"

    def test_critical_at_20pp(self):
        monitoring = _make_monitoring(confidence_distribution={"high": 30, "medium": 30, "low": 40})
        alerts = compute_run_alerts(monitoring=monitoring)
        low_conf = [a for a in alerts if a.code == "LOW_CONFIDENCE_SURGE"]
        assert len(low_conf) == 1
        assert low_conf[0].severity == "CRITICAL"


# ---------------------------------------------------------------------------
# Tests: STALE_RUBRICS_HIGH
# ---------------------------------------------------------------------------

class TestStaleRubrics:
    def test_no_alert_below_threshold(self):
        aging = _make_aging(stale_count=15, total_active=100)  # 15%
        alerts = compute_run_alerts(aging=aging)
        assert not any(a.code == "STALE_RUBRICS_HIGH" for a in alerts)

    def test_warning_at_20_pct(self):
        aging = _make_aging(stale_count=20, total_active=100)
        alerts = compute_run_alerts(aging=aging)
        stale = [a for a in alerts if a.code == "STALE_RUBRICS_HIGH"]
        assert len(stale) == 1
        assert stale[0].severity == "WARNING"

    def test_critical_at_35_pct(self):
        aging = _make_aging(stale_count=35, total_active=100)
        alerts = compute_run_alerts(aging=aging)
        stale = [a for a in alerts if a.code == "STALE_RUBRICS_HIGH"]
        assert len(stale) == 1
        assert stale[0].severity == "CRITICAL"


# ---------------------------------------------------------------------------
# Tests: REVIEW_QUEUE_HIGH_GROWTH
# ---------------------------------------------------------------------------

class TestReviewQueueGrowth:
    def test_no_alert_below_threshold(self):
        queue = _make_review_queue(high=5)
        alerts = compute_run_alerts(review_queue=queue)
        assert not any(a.code == "REVIEW_QUEUE_HIGH_GROWTH" for a in alerts)

    def test_warning_at_10(self):
        queue = _make_review_queue(high=10)
        alerts = compute_run_alerts(review_queue=queue)
        rq = [a for a in alerts if a.code == "REVIEW_QUEUE_HIGH_GROWTH"]
        assert len(rq) == 1
        assert rq[0].severity == "WARNING"

    def test_critical_at_20(self):
        queue = _make_review_queue(high=20)
        alerts = compute_run_alerts(review_queue=queue)
        rq = [a for a in alerts if a.code == "REVIEW_QUEUE_HIGH_GROWTH"]
        assert len(rq) == 1
        assert rq[0].severity == "CRITICAL"


# ---------------------------------------------------------------------------
# Tests: D_FRAGILE_SHIFT
# ---------------------------------------------------------------------------

class TestDFragileShift:
    def test_no_alert_below_threshold(self):
        drift = _make_drift(bucket_change_details=[
            _make_issuer_drift(issuer_id="iss-1", new_bucket="D_FRAGILE"),
        ], bucket_changes=1)
        alerts = compute_run_alerts(drift=drift)
        assert not any(a.code == "D_FRAGILE_SHIFT" for a in alerts)

    def test_warning_at_2(self):
        drift = _make_drift(bucket_change_details=[
            _make_issuer_drift(issuer_id="iss-1", ticker="TICK3", new_bucket="D_FRAGILE"),
            _make_issuer_drift(issuer_id="iss-2", ticker="ABCD3", new_bucket="D_FRAGILE"),
        ], bucket_changes=2)
        alerts = compute_run_alerts(drift=drift)
        fragile = [a for a in alerts if a.code == "D_FRAGILE_SHIFT"]
        assert len(fragile) == 1
        assert fragile[0].severity == "WARNING"
        assert fragile[0].metric_value == 2.0

    def test_critical_at_5(self):
        details = [
            _make_issuer_drift(issuer_id=f"iss-{i}", ticker=f"T{i}K3", new_bucket="D_FRAGILE")
            for i in range(5)
        ]
        drift = _make_drift(bucket_change_details=details, bucket_changes=5)
        alerts = compute_run_alerts(drift=drift)
        fragile = [a for a in alerts if a.code == "D_FRAGILE_SHIFT"]
        assert len(fragile) == 1
        assert fragile[0].severity == "CRITICAL"

    def test_ignores_already_fragile(self):
        """Issuers already in D_FRAGILE don't count."""
        drift = _make_drift(bucket_change_details=[
            _make_issuer_drift(issuer_id="iss-1", old_bucket="D_FRAGILE", new_bucket="D_FRAGILE", bucket_changed=False),
            _make_issuer_drift(issuer_id="iss-2", old_bucket="D_FRAGILE", new_bucket="D_FRAGILE", bucket_changed=False),
        ], bucket_changes=0)
        alerts = compute_run_alerts(drift=drift)
        assert not any(a.code == "D_FRAGILE_SHIFT" for a in alerts)


# ---------------------------------------------------------------------------
# Tests: Sorting and combined alerts
# ---------------------------------------------------------------------------

class TestAlertSorting:
    def test_critical_before_warning(self):
        drift = _make_drift(
            top10_entered=["A", "B", "C"],
            top10_exited=["D", "E", "F"],
        )
        aging = _make_aging(stale_count=25, total_active=100)  # WARNING

        alerts = compute_run_alerts(drift=drift, aging=aging)
        assert len(alerts) >= 2
        severities = [a.severity for a in alerts]
        assert severities.index("CRITICAL") < severities.index("WARNING")

    def test_no_alerts_when_all_healthy(self):
        monitoring = _make_monitoring(confidence_distribution={"high": 90, "medium": 9, "low": 1})
        drift = _make_drift()
        aging = _make_aging(stale_count=5, total_active=100)
        queue = _make_review_queue(high=2)

        alerts = compute_run_alerts(
            monitoring=monitoring,
            drift=drift,
            aging=aging,
            review_queue=queue,
        )
        assert len(alerts) == 0

    def test_all_none_returns_empty(self):
        alerts = compute_run_alerts()
        assert alerts == []
