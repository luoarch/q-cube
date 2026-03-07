"""Promotion pipeline — automated checklist for strategy promotion.

A strategy can only be promoted to "candidate" status if it passes
ALL 6 mandatory checks from the research validation protocol:

1. Point-in-time correct
2. OOS real
3. Real costs
4. Multiple testing correction
5. Selection-adjusted metrics
6. Full reproducibility

Reference: docs/research-validation-protocol.md, Section 13 & 16.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class PromotionCheck:
    """Result of a single promotion criterion."""

    name: str
    passed: bool
    detail: str
    value: float | str | None = None
    threshold: float | str | None = None


@dataclass
class PromotionResult:
    """Full promotion evaluation for a strategy."""

    strategy: str
    variant: str
    checks: list[PromotionCheck]
    promoted: bool  # True only if ALL checks pass
    blocking_checks: list[str]  # names of failed checks
    summary: dict  # key metrics at a glance


# Configurable thresholds
PROMOTION_THRESHOLDS = {
    "min_oos_sharpe": 0.3,
    "max_degradation_sharpe": -0.50,  # 50% drop max
    "min_dsr": 0.50,  # DSR must indicate >50% probability
    "max_sensitivity_swing": 0.50,  # Sharpe swing < 50%
    "max_subperiod_dependency": False,  # fragile flag must be False
    "min_oos_months": 12,  # minimum OOS period
}


def run_promotion_check(
    strategy: str,
    variant: str,
    oos_metrics: dict,
    oos_statistical: dict,
    degradation: dict,
    sensitivity_robust: bool,
    subperiod_fragile: bool,
    manifest_valid: bool,
    pit_validated: bool,
    costs_applied: bool,
    oos_months: int,
) -> PromotionResult:
    """Evaluate all promotion criteria for a strategy.

    Each argument comes from the corresponding R1/R2 reports.
    """
    checks: list[PromotionCheck] = []

    # 1. Point-in-time correct
    checks.append(PromotionCheck(
        name="point_in_time",
        passed=pit_validated,
        detail="PIT data layer used with available_at filtering" if pit_validated else "PIT validation not confirmed",
    ))

    # 2. OOS real — minimum OOS period and acceptable Sharpe
    oos_sharpe = oos_metrics.get("sharpe", 0)
    oos_period_ok = oos_months >= PROMOTION_THRESHOLDS["min_oos_months"]
    oos_sharpe_ok = oos_sharpe >= PROMOTION_THRESHOLDS["min_oos_sharpe"]
    checks.append(PromotionCheck(
        name="oos_acceptable",
        passed=oos_period_ok and oos_sharpe_ok,
        detail=f"OOS Sharpe={oos_sharpe:.4f}, months={oos_months}",
        value=oos_sharpe,
        threshold=PROMOTION_THRESHOLDS["min_oos_sharpe"],
    ))

    # 3. Real costs applied
    checks.append(PromotionCheck(
        name="costs_applied",
        passed=costs_applied,
        detail="Backtest includes proportional costs + slippage" if costs_applied else "No cost model applied",
    ))

    # 4. Multiple testing correction (DSR)
    dsr = oos_statistical.get("dsr", 0)
    dsr_ok = dsr >= PROMOTION_THRESHOLDS["min_dsr"]
    checks.append(PromotionCheck(
        name="multiple_testing_corrected",
        passed=dsr_ok,
        detail=f"DSR={dsr:.4f} (min={PROMOTION_THRESHOLDS['min_dsr']})",
        value=dsr,
        threshold=PROMOTION_THRESHOLDS["min_dsr"],
    ))

    # 5. Selection-adjusted metrics — no severe degradation + stable across params
    sharpe_deg = degradation.get("sharpe", 0)
    deg_ok = sharpe_deg >= PROMOTION_THRESHOLDS["max_degradation_sharpe"]
    sensitivity_ok = sensitivity_robust
    not_fragile = not subperiod_fragile
    adjusted_ok = deg_ok and sensitivity_ok and not_fragile

    details = []
    if not deg_ok:
        details.append(f"Sharpe degradation={sharpe_deg:.4f}")
    if not sensitivity_ok:
        details.append("sensitivity: not robust")
    if not not_fragile:
        details.append("subperiod: fragile")

    checks.append(PromotionCheck(
        name="selection_adjusted",
        passed=adjusted_ok,
        detail="; ".join(details) if details else "Degradation, sensitivity, and subperiods all OK",
        value=sharpe_deg,
        threshold=PROMOTION_THRESHOLDS["max_degradation_sharpe"],
    ))

    # 6. Full reproducibility
    checks.append(PromotionCheck(
        name="reproducibility",
        passed=manifest_valid,
        detail="Research manifest with experiment_id and commit_hash" if manifest_valid else "Missing or invalid manifest",
    ))

    # Final verdict
    blocking = [c.name for c in checks if not c.passed]
    promoted = len(blocking) == 0

    summary = {
        "oos_sharpe": round(oos_sharpe, 4),
        "oos_cagr": round(oos_metrics.get("cagr", 0), 6),
        "dsr": round(dsr, 4),
        "psr": round(oos_statistical.get("psr", 0), 4),
        "degradation_sharpe": round(sharpe_deg, 4),
        "robust": sensitivity_robust,
        "fragile": subperiod_fragile,
        "n_checks_passed": sum(1 for c in checks if c.passed),
        "n_checks_total": len(checks),
    }

    return PromotionResult(
        strategy=strategy,
        variant=variant,
        checks=checks,
        promoted=promoted,
        blocking_checks=blocking,
        summary=summary,
    )
