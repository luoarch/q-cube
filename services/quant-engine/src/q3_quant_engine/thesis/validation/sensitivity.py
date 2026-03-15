"""Sensitivity analysis — weight/threshold perturbation.

Perturbs scoring weights and bucket thresholds to measure ranking stability.
A stable model should not see massive bucket flips from small changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from q3_quant_engine.thesis.scoring import (
    compute_final_commodity_affinity_score,
    compute_final_dollar_fragility_score,
    compute_thesis_rank_score,
)
from q3_quant_engine.thesis.types import (
    Plan2FeatureInput,
    Plan2RankingSnapshot,
    ThesisBucket,
)


@dataclass
class SensitivityResult:
    """Result of a sensitivity analysis run."""

    perturbation_label: str
    perturbation_detail: dict[str, float]
    bucket_changes: int
    top10_changes: int
    top20_changes: int
    total_eligible: int
    bucket_change_pct: float
    details: list[dict[str, str]] = field(default_factory=list)


def _recompute_with_perturbed_thresholds(
    inputs: list[Plan2FeatureInput],
    threshold_overrides: dict[str, float],
) -> list[tuple[str, ThesisBucket, float]]:
    """Recompute buckets and rank scores with perturbed thresholds.

    Returns list of (ticker, bucket, thesis_rank_score).
    """
    from q3_quant_engine.thesis.config import BUCKET_THRESHOLDS

    perturbed = dict(BUCKET_THRESHOLDS)
    perturbed.update(threshold_overrides)

    results: list[tuple[str, ThesisBucket, float]] = []
    for inp in inputs:
        commodity_affinity = compute_final_commodity_affinity_score(
            inp.direct_commodity_exposure_score,
            inp.indirect_commodity_exposure_score,
            inp.export_fx_leverage_score,
        )
        fragility = compute_final_dollar_fragility_score(
            inp.refinancing_stress_score,
            inp.usd_debt_exposure_score,
            inp.usd_import_dependence_score,
            inp.usd_revenue_offset_score,
        )

        # Bucket with perturbed thresholds
        t = perturbed
        if (
            inp.direct_commodity_exposure_score >= t["a_direct_min_direct_commodity"]
            and fragility <= t["a_direct_max_fragility"]
        ):
            bucket = ThesisBucket.A_DIRECT
        elif (
            inp.indirect_commodity_exposure_score >= t["b_indirect_min_indirect_commodity"]
            and fragility <= t["b_indirect_max_fragility"]
        ):
            bucket = ThesisBucket.B_INDIRECT
        elif fragility >= t["d_fragile_min_fragility"]:
            bucket = ThesisBucket.D_FRAGILE
        else:
            bucket = ThesisBucket.C_NEUTRAL

        rank_score = compute_thesis_rank_score(
            commodity_affinity, fragility, inp.core_rank_percentile,
        )
        results.append((inp.ticker, bucket, rank_score))

    return results


def run_sensitivity_analysis(
    inputs: list[Plan2FeatureInput],
    baseline_snapshots: list[Plan2RankingSnapshot],
    perturbations: list[tuple[str, dict[str, float]]] | None = None,
) -> list[SensitivityResult]:
    """Run sensitivity analysis with multiple perturbation scenarios.

    Args:
        inputs: The Plan2FeatureInput for each eligible issuer.
        baseline_snapshots: The original ranked snapshots (eligible only).
        perturbations: List of (label, threshold_overrides). If None, uses defaults.

    Returns:
        List of SensitivityResult, one per perturbation scenario.
    """
    if perturbations is None:
        perturbations = _default_perturbations()

    baseline_buckets = {s.ticker: s.bucket for s in baseline_snapshots if s.eligible}
    baseline_ranked = [
        s.ticker for s in baseline_snapshots
        if s.eligible and s.thesis_rank is not None
    ]
    baseline_top10 = set(baseline_ranked[:10])
    baseline_top20 = set(baseline_ranked[:20])

    results: list[SensitivityResult] = []

    for label, overrides in perturbations:
        perturbed = _recompute_with_perturbed_thresholds(inputs, overrides)

        bucket_changes = 0
        details: list[dict[str, str]] = []

        perturbed_sorted = sorted(perturbed, key=lambda x: -x[2])
        perturbed_tickers = [t for t, _, _ in perturbed_sorted]
        perturbed_top10 = set(perturbed_tickers[:10])
        perturbed_top20 = set(perturbed_tickers[:20])

        for ticker, new_bucket, _ in perturbed:
            old_bucket = baseline_buckets.get(ticker)
            if old_bucket is not None and old_bucket != new_bucket:
                bucket_changes += 1
                details.append({
                    "ticker": ticker,
                    "old_bucket": old_bucket.value if old_bucket else "None",
                    "new_bucket": new_bucket.value,
                })

        top10_changes = len(baseline_top10.symmetric_difference(perturbed_top10))
        top20_changes = len(baseline_top20.symmetric_difference(perturbed_top20))
        total = len(inputs)

        results.append(SensitivityResult(
            perturbation_label=label,
            perturbation_detail=overrides,
            bucket_changes=bucket_changes,
            top10_changes=top10_changes,
            top20_changes=top20_changes,
            total_eligible=total,
            bucket_change_pct=round(bucket_changes / total * 100, 1) if total > 0 else 0.0,
            details=details,
        ))

    return results


def _default_perturbations() -> list[tuple[str, dict[str, float]]]:
    """Default perturbation scenarios: +/- 5 points on key thresholds."""
    return [
        ("A_DIRECT threshold +5", {
            "a_direct_min_direct_commodity": 75.0,
            "a_direct_max_fragility": 55.0,
        }),
        ("A_DIRECT threshold -5", {
            "a_direct_min_direct_commodity": 65.0,
            "a_direct_max_fragility": 65.0,
        }),
        ("B_INDIRECT threshold +5", {
            "b_indirect_min_indirect_commodity": 65.0,
            "b_indirect_max_fragility": 60.0,
        }),
        ("B_INDIRECT threshold -5", {
            "b_indirect_min_indirect_commodity": 55.0,
            "b_indirect_max_fragility": 70.0,
        }),
        ("D_FRAGILE threshold +5 (stricter)", {
            "d_fragile_min_fragility": 80.0,
        }),
        ("D_FRAGILE threshold -5 (looser)", {
            "d_fragile_min_fragility": 70.0,
        }),
    ]
