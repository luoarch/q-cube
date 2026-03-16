"""Plan 2 automated alerts — compute governance alerts from monitoring data.

Pure computation function. No DB access — caller provides monitoring results.

6 alert types with WARNING/CRITICAL thresholds:
1. BUCKET_DRIFT_HIGH — too many bucket changes between runs
2. TOP10_CHANGED — top-10 ranking instability
3. LOW_CONFIDENCE_SURGE — spike in low-confidence scores
4. STALE_RUBRICS_HIGH — too many stale rubrics
5. REVIEW_QUEUE_HIGH_GROWTH — review queue growing fast
6. D_FRAGILE_SHIFT — too many issuers moving into D_FRAGILE bucket
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from q3_quant_engine.thesis.monitoring import (
    ReviewQueue,
    RubricAgingReport,
    RunDrift,
    RunMonitoringSummary,
)


@dataclass
class Alert:
    """A single governance alert."""
    code: str
    severity: str  # "INFO" | "WARNING" | "CRITICAL"
    title: str
    message: str
    metric_value: float
    threshold: float
    context: dict[str, Any]


def compute_run_alerts(
    monitoring: RunMonitoringSummary | None = None,
    drift: RunDrift | None = None,
    aging: RubricAgingReport | None = None,
    review_queue: ReviewQueue | None = None,
) -> list[Alert]:
    """Compute all governance alerts from monitoring data.

    Returns list of alerts sorted by severity (CRITICAL first).
    """
    alerts: list[Alert] = []

    total_eligible = monitoring.total_eligible if monitoring else 0

    if drift is not None:
        alerts.extend(_check_bucket_drift(drift, total_eligible))
        alerts.extend(_check_top10_changed(drift))
        alerts.extend(_check_d_fragile_shift(drift))

    if monitoring is not None:
        alerts.extend(_check_low_confidence_surge(monitoring))

    if aging is not None:
        alerts.extend(_check_stale_rubrics(aging))

    if review_queue is not None:
        alerts.extend(_check_review_queue_growth(review_queue))

    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 3))

    return alerts


def _check_bucket_drift(drift: RunDrift, total_eligible: int) -> list[Alert]:
    """BUCKET_DRIFT_HIGH: >=10% WARNING, >=20% CRITICAL."""
    if total_eligible == 0:
        return []

    changes = drift.bucket_changes
    pct = changes / total_eligible * 100

    if pct < 10:
        return []

    severity = "CRITICAL" if pct >= 20 else "WARNING"

    return [Alert(
        code="BUCKET_DRIFT_HIGH",
        severity=severity,
        title="High bucket drift between runs",
        message=f"{pct:.1f}% of issuers changed buckets ({changes}/{total_eligible})",
        metric_value=round(pct, 1),
        threshold=20.0 if severity == "CRITICAL" else 10.0,
        context={
            "bucket_changes": changes,
            "total_eligible": total_eligible,
            "current_run_id": drift.current_run_id,
            "previous_run_id": drift.previous_run_id,
        },
    )]


def _check_top10_changed(drift: RunDrift) -> list[Alert]:
    """TOP10_CHANGED: any change WARNING, >=3 CRITICAL."""
    entered = len(drift.top10_entered)
    exited = len(drift.top10_exited)
    changes = max(entered, exited)

    if changes == 0:
        return []

    severity = "CRITICAL" if changes >= 3 else "WARNING"
    entered_str = ", ".join(drift.top10_entered) if drift.top10_entered else "none"
    exited_str = ", ".join(drift.top10_exited) if drift.top10_exited else "none"

    return [Alert(
        code="TOP10_CHANGED",
        severity=severity,
        title="Top-10 ranking changed",
        message=f"{changes} top-10 changes: entered [{entered_str}], exited [{exited_str}]",
        metric_value=float(changes),
        threshold=3.0 if severity == "CRITICAL" else 1.0,
        context={
            "entered": drift.top10_entered,
            "exited": drift.top10_exited,
        },
    )]


def _check_low_confidence_surge(monitoring: RunMonitoringSummary) -> list[Alert]:
    """LOW_CONFIDENCE_SURGE: >=10pp low confidence WARNING, >=20pp CRITICAL."""
    low_count = monitoring.confidence_distribution.get("low", 0)
    total = sum(monitoring.confidence_distribution.values())
    if total == 0:
        return []

    low_pct = low_count / total * 100

    if low_pct < 10:
        return []

    severity = "CRITICAL" if low_pct >= 20 else "WARNING"

    return [Alert(
        code="LOW_CONFIDENCE_SURGE",
        severity=severity,
        title="High proportion of low-confidence scores",
        message=f"{low_pct:.1f}% of scores have low confidence ({low_count}/{total})",
        metric_value=round(low_pct, 1),
        threshold=20.0 if severity == "CRITICAL" else 10.0,
        context={
            "low_count": low_count,
            "total": total,
            "distribution": monitoring.confidence_distribution,
        },
    )]


def _check_stale_rubrics(aging: RubricAgingReport) -> list[Alert]:
    """STALE_RUBRICS_HIGH: >=20% WARNING, >=35% CRITICAL."""
    if aging.total_active_rubrics == 0:
        return []

    pct = aging.stale_pct

    if pct < 20:
        return []

    severity = "CRITICAL" if pct >= 35 else "WARNING"

    return [Alert(
        code="STALE_RUBRICS_HIGH",
        severity=severity,
        title="Too many stale rubrics",
        message=f"{pct:.1f}% of rubrics are stale ({aging.stale_count}/{aging.total_active_rubrics})",
        metric_value=round(pct, 1),
        threshold=35.0 if severity == "CRITICAL" else 20.0,
        context={
            "stale_count": aging.stale_count,
            "total": aging.total_active_rubrics,
            "stale_by_dimension": aging.stale_by_dimension,
        },
    )]


def _check_review_queue_growth(current: ReviewQueue) -> list[Alert]:
    """REVIEW_QUEUE_HIGH_GROWTH: >=10 high-priority items WARNING, >=20 CRITICAL."""
    high = current.high_priority

    if high < 10:
        return []

    severity = "CRITICAL" if high >= 20 else "WARNING"

    return [Alert(
        code="REVIEW_QUEUE_HIGH_GROWTH",
        severity=severity,
        title="Review queue has many high-priority items",
        message=f"{high} high-priority items in review queue",
        metric_value=float(high),
        threshold=20.0 if severity == "CRITICAL" else 10.0,
        context={
            "high_priority": current.high_priority,
            "medium_priority": current.medium_priority,
            "low_priority": current.low_priority,
            "total": current.total_items,
        },
    )]


def _check_d_fragile_shift(drift: RunDrift) -> list[Alert]:
    """D_FRAGILE_SHIFT: >=2 issuers entering D_FRAGILE WARNING, >=5 CRITICAL."""
    entered_fragile = sum(
        1 for d in drift.bucket_change_details
        if d.new_bucket == "D_FRAGILE" and d.old_bucket != "D_FRAGILE" and d.bucket_changed
    )

    if entered_fragile < 2:
        return []

    severity = "CRITICAL" if entered_fragile >= 5 else "WARNING"

    fragile_tickers = [
        d.ticker for d in drift.bucket_change_details
        if d.new_bucket == "D_FRAGILE" and d.old_bucket != "D_FRAGILE" and d.bucket_changed
    ]

    return [Alert(
        code="D_FRAGILE_SHIFT",
        severity=severity,
        title="Issuers entering D_FRAGILE bucket",
        message=f"{entered_fragile} issuers entered D_FRAGILE: {', '.join(fragile_tickers)}",
        metric_value=float(entered_fragile),
        threshold=5.0 if severity == "CRITICAL" else 2.0,
        context={
            "entered_fragile": entered_fragile,
            "tickers": fragile_tickers,
        },
    )]
