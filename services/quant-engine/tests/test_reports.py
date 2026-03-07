"""OOS, subperiod, and sensitivity report tests."""

from __future__ import annotations

from q3_quant_engine.backtest.reports import (
    DEGRADATION_THRESHOLDS,
    _classify_regimes,
    _compute_degradation,
    _is_fragile,
    _check_robustness,
    _subperiod_fragile,
)


def test_degradation_computation():
    """Degradation is (oos - is) / |is| for each metric."""
    is_m = {"sharpe": 2.0, "cagr": 0.15, "sortino": 2.5}
    oos_m = {"sharpe": 1.0, "cagr": 0.05, "sortino": 1.0}
    deg = _compute_degradation(is_m, oos_m)
    assert abs(deg["sharpe"] - (-0.5)) < 0.01  # (1-2)/2 = -0.5
    assert abs(deg["cagr"] - (-0.6667)) < 0.01  # (0.05-0.15)/0.15


def test_fragile_negative_oos_sharpe():
    """Strategy is fragile when OOS Sharpe < 0."""
    assert _is_fragile({"sharpe": -0.3}, {"sharpe": 0, "cagr": 0, "sortino": 0})


def test_fragile_severe_degradation():
    """Strategy is fragile when degradation exceeds threshold."""
    deg = {"sharpe": -0.55, "cagr": -0.3, "sortino": -0.2}
    assert _is_fragile({"sharpe": 0.5}, deg)


def test_not_fragile_mild_degradation():
    """Strategy is NOT fragile with mild degradation."""
    deg = {"sharpe": -0.2, "cagr": -0.1, "sortino": -0.1}
    assert not _is_fragile({"sharpe": 0.8}, deg)


def test_regime_classification():
    """Subperiods are classified into bull/bear/stress/recovery."""
    subperiods = [
        {"metrics": {"cagr": 0.15, "max_drawdown": 0.05, "sharpe": 1.5}},  # bull
        {"metrics": {"cagr": -0.10, "max_drawdown": 0.15, "sharpe": -0.5}},  # bear
        {"metrics": {"cagr": -0.25, "max_drawdown": 0.35, "sharpe": -1.0}},  # stress
        {"metrics": {"cagr": 0.20, "max_drawdown": 0.08, "sharpe": 2.0}},  # recovery (follows bear)
    ]
    regimes = _classify_regimes(subperiods)
    assert "bull" in regimes
    assert "stress" in regimes
    assert regimes["stress"]["count"] == 1


def test_subperiod_fragile_extreme_sharpe():
    """Strategy is fragile if any subperiod has Sharpe < -0.5."""
    subperiods = [
        {"metrics": {"sharpe": 1.0}},
        {"metrics": {"sharpe": -0.8}},
    ]
    assert _subperiod_fragile(subperiods)


def test_subperiod_not_fragile_stable():
    """Strategy is NOT fragile when subperiods are stable."""
    subperiods = [
        {"metrics": {"sharpe": 0.8}},
        {"metrics": {"sharpe": 1.2}},
        {"metrics": {"sharpe": 0.9}},
    ]
    assert not _subperiod_fragile(subperiods)


def test_robustness_stable_sharpe():
    """Strategy is robust when variations don't swing Sharpe >50%."""
    variations = [
        {"metrics": {"sharpe": 1.1}},
        {"metrics": {"sharpe": 0.9}},
        {"metrics": {"sharpe": 1.0}},
    ]
    assert _check_robustness(variations, base_sharpe=1.0)


def test_robustness_unstable_sharpe():
    """Strategy is NOT robust when one variation swings Sharpe heavily."""
    variations = [
        {"metrics": {"sharpe": 1.0}},
        {"metrics": {"sharpe": 0.1}},  # 90% drop from base
    ]
    assert not _check_robustness(variations, base_sharpe=1.0)
