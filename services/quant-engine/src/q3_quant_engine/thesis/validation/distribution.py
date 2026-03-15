"""Distribution sanity — structural alerts for a pipeline run.

Detects anomalous bucket distributions that suggest model misconfiguration
or data quality issues.
"""

from __future__ import annotations

from dataclasses import dataclass

from q3_quant_engine.thesis.types import Plan2RankingSnapshot, ThesisBucket


@dataclass(frozen=True)
class DistributionAlert:
    """A single distribution sanity alert."""

    severity: str  # "WARNING" | "CRITICAL"
    code: str
    message: str


# Configurable thresholds
_MAX_FRAGILE_PCT = 0.40  # alert if >40% of eligible are D_FRAGILE
_MIN_ELIGIBLE = 3  # alert if fewer than 3 eligible
_MIN_SCORE_SPREAD = 5.0  # alert if thesis_rank_score spread < 5 points
_MAX_SCORE_SPREAD = 95.0  # alert if spread > 95 (basically 0-100)
_MAX_SINGLE_BUCKET_PCT = 0.80  # alert if >80% in one bucket


def check_distribution_sanity(
    snapshots: list[Plan2RankingSnapshot],
) -> list[DistributionAlert]:
    """Check distribution sanity of a pipeline run.

    Returns a list of alerts (empty = all clear).
    """
    alerts: list[DistributionAlert] = []

    eligible = [s for s in snapshots if s.eligible and s.bucket is not None]
    total_eligible = len(eligible)

    # --- Alert: too few eligible ---
    if total_eligible == 0:
        alerts.append(DistributionAlert(
            severity="CRITICAL",
            code="NO_ELIGIBLE",
            message="Zero eligible issuers in run",
        ))
        return alerts  # can't check further

    if total_eligible < _MIN_ELIGIBLE:
        alerts.append(DistributionAlert(
            severity="WARNING",
            code="FEW_ELIGIBLE",
            message=f"Only {total_eligible} eligible issuers (threshold: {_MIN_ELIGIBLE})",
        ))

    # --- Bucket distribution ---
    bucket_counts: dict[ThesisBucket, int] = {}
    for s in eligible:
        assert s.bucket is not None
        bucket_counts[s.bucket] = bucket_counts.get(s.bucket, 0) + 1

    # Alert: A_DIRECT == 0
    if bucket_counts.get(ThesisBucket.A_DIRECT, 0) == 0:
        alerts.append(DistributionAlert(
            severity="WARNING",
            code="NO_A_DIRECT",
            message="Zero issuers in A_DIRECT bucket — check direct commodity proxy thresholds",
        ))

    # Alert: D_FRAGILE concentration
    fragile_count = bucket_counts.get(ThesisBucket.D_FRAGILE, 0)
    fragile_pct = fragile_count / total_eligible
    if fragile_pct > _MAX_FRAGILE_PCT:
        alerts.append(DistributionAlert(
            severity="WARNING",
            code="HIGH_FRAGILE_PCT",
            message=f"{fragile_pct:.0%} of eligible in D_FRAGILE ({fragile_count}/{total_eligible}) — "
                    f"threshold: {_MAX_FRAGILE_PCT:.0%}",
        ))

    # Alert: excessive concentration in any single bucket
    for bucket, count in bucket_counts.items():
        pct = count / total_eligible
        if pct > _MAX_SINGLE_BUCKET_PCT:
            alerts.append(DistributionAlert(
                severity="WARNING",
                code="BUCKET_CONCENTRATION",
                message=f"{pct:.0%} of eligible in {bucket.value} ({count}/{total_eligible}) — "
                        f"threshold: {_MAX_SINGLE_BUCKET_PCT:.0%}",
            ))

    # --- Score spread ---
    scores = [s.thesis_rank_score for s in eligible if s.thesis_rank_score is not None]
    if len(scores) >= 2:
        spread = max(scores) - min(scores)
        if spread < _MIN_SCORE_SPREAD:
            alerts.append(DistributionAlert(
                severity="WARNING",
                code="NARROW_SCORE_SPREAD",
                message=f"Thesis rank score spread is {spread:.1f} (threshold: {_MIN_SCORE_SPREAD}) — "
                        "scores may lack discrimination",
            ))
        if spread > _MAX_SCORE_SPREAD:
            alerts.append(DistributionAlert(
                severity="WARNING",
                code="WIDE_SCORE_SPREAD",
                message=f"Thesis rank score spread is {spread:.1f} (threshold: {_MAX_SCORE_SPREAD}) — "
                        "extreme range may indicate data issue",
            ))

    return alerts
