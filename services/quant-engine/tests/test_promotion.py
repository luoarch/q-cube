"""Promotion pipeline tests."""

from __future__ import annotations

from q3_quant_engine.backtest.promotion import (
    PROMOTION_THRESHOLDS,
    PromotionResult,
    run_promotion_check,
)


def _run_check(**overrides) -> PromotionResult:
    """Helper to run promotion check with sensible defaults."""
    defaults = {
        "strategy": "magic_formula_brazil",
        "variant": "base",
        "oos_metrics": {"sharpe": 0.8, "cagr": 0.12, "sortino": 1.0, "max_drawdown": 0.15},
        "oos_statistical": {"psr": 0.85, "dsr": 0.70},
        "degradation": {"sharpe": -0.20, "cagr": -0.15, "sortino": -0.10},
        "sensitivity_robust": True,
        "subperiod_fragile": False,
        "manifest_valid": True,
        "pit_validated": True,
        "costs_applied": True,
        "oos_months": 24,
    }
    defaults.update(overrides)
    return run_promotion_check(**defaults)


def test_all_checks_pass_promotes():
    """Strategy passes all checks → promoted = True."""
    result = _run_check()
    assert result.promoted is True
    assert len(result.blocking_checks) == 0
    assert result.summary["n_checks_passed"] == 6


def test_low_oos_sharpe_blocks():
    """OOS Sharpe below threshold blocks promotion."""
    result = _run_check(oos_metrics={"sharpe": 0.1, "cagr": 0.02})
    assert result.promoted is False
    assert "oos_acceptable" in result.blocking_checks


def test_negative_oos_sharpe_blocks():
    """Negative OOS Sharpe definitely blocks."""
    result = _run_check(oos_metrics={"sharpe": -0.3, "cagr": -0.05})
    assert result.promoted is False


def test_low_dsr_blocks():
    """DSR below threshold blocks promotion."""
    result = _run_check(oos_statistical={"psr": 0.30, "dsr": 0.20})
    assert result.promoted is False
    assert "multiple_testing_corrected" in result.blocking_checks


def test_severe_degradation_blocks():
    """Severe IS→OOS degradation blocks promotion."""
    result = _run_check(degradation={"sharpe": -0.65, "cagr": -0.50, "sortino": -0.60})
    assert result.promoted is False
    assert "selection_adjusted" in result.blocking_checks


def test_sensitivity_not_robust_blocks():
    """Non-robust sensitivity analysis blocks promotion."""
    result = _run_check(sensitivity_robust=False)
    assert result.promoted is False
    assert "selection_adjusted" in result.blocking_checks


def test_fragile_subperiod_blocks():
    """Fragile subperiod analysis blocks promotion."""
    result = _run_check(subperiod_fragile=True)
    assert result.promoted is False
    assert "selection_adjusted" in result.blocking_checks


def test_no_manifest_blocks():
    """Missing manifest blocks promotion."""
    result = _run_check(manifest_valid=False)
    assert result.promoted is False
    assert "reproducibility" in result.blocking_checks


def test_no_pit_blocks():
    """Missing PIT validation blocks promotion."""
    result = _run_check(pit_validated=False)
    assert result.promoted is False
    assert "point_in_time" in result.blocking_checks


def test_no_costs_blocks():
    """Missing cost model blocks promotion."""
    result = _run_check(costs_applied=False)
    assert result.promoted is False
    assert "costs_applied" in result.blocking_checks


def test_short_oos_blocks():
    """OOS period shorter than minimum blocks promotion."""
    result = _run_check(oos_months=6)
    assert result.promoted is False
    assert "oos_acceptable" in result.blocking_checks


def test_multiple_failures_all_reported():
    """Multiple blocking checks are all reported."""
    result = _run_check(
        pit_validated=False,
        costs_applied=False,
        manifest_valid=False,
    )
    assert result.promoted is False
    assert len(result.blocking_checks) == 3
    assert "point_in_time" in result.blocking_checks
    assert "costs_applied" in result.blocking_checks
    assert "reproducibility" in result.blocking_checks


def test_summary_has_key_metrics():
    """Summary dict contains all key metrics for quick review."""
    result = _run_check()
    s = result.summary
    assert "oos_sharpe" in s
    assert "oos_cagr" in s
    assert "dsr" in s
    assert "psr" in s
    assert "degradation_sharpe" in s
    assert "robust" in s
    assert "fragile" in s
    assert "n_checks_passed" in s
    assert "n_checks_total" in s
