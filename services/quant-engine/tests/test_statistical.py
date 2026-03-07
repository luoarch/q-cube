"""PSR, DSR, skewness, and kurtosis tests."""

from __future__ import annotations

import math

from q3_quant_engine.backtest.statistical import (
    _kurtosis_excess,
    _skewness,
    compute_statistical_metrics,
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
)


def test_psr_high_sharpe_is_confident():
    """High observed Sharpe with enough data → PSR close to 1."""
    psr = probabilistic_sharpe_ratio(
        observed_sharpe=2.0,
        benchmark_sharpe=0.0,
        n_returns=60,
    )
    assert psr > 0.95


def test_psr_zero_sharpe_equals_half():
    """Observed Sharpe = benchmark Sharpe → PSR = 0.5."""
    psr = probabilistic_sharpe_ratio(
        observed_sharpe=0.5,
        benchmark_sharpe=0.5,
        n_returns=60,
    )
    assert abs(psr - 0.5) < 0.01


def test_psr_accounts_for_skewness():
    """Negative skewness should reduce PSR for the same Sharpe."""
    psr_normal = probabilistic_sharpe_ratio(
        observed_sharpe=1.0, benchmark_sharpe=0.0,
        n_returns=60, skew=0.0, excess_kurtosis=0.0,
    )
    psr_negskew = probabilistic_sharpe_ratio(
        observed_sharpe=1.0, benchmark_sharpe=0.0,
        n_returns=60, skew=-1.5, excess_kurtosis=0.0,
    )
    # Negative skew inflates SR standard error → lower confidence
    assert psr_negskew < psr_normal


def test_dsr_penalizes_multiple_trials():
    """More trials tested → higher expected max SR → lower DSR."""
    # Use moderate Sharpe so DSR doesn't saturate at 1.0
    dsr_1 = deflated_sharpe_ratio(observed_sharpe=0.6, n_returns=60, n_trials=1)
    dsr_10 = deflated_sharpe_ratio(observed_sharpe=0.6, n_returns=60, n_trials=10)
    dsr_100 = deflated_sharpe_ratio(observed_sharpe=0.6, n_returns=60, n_trials=100)
    assert dsr_1 > dsr_10 > dsr_100


def test_dsr_single_trial_equals_psr():
    """With 1 trial, DSR should equal PSR(SR, 0)."""
    dsr = deflated_sharpe_ratio(observed_sharpe=1.0, n_returns=60, n_trials=1)
    psr = probabilistic_sharpe_ratio(
        observed_sharpe=1.0, benchmark_sharpe=0.0, n_returns=60,
    )
    assert abs(dsr - psr) < 0.01


def test_skewness_symmetric_returns():
    """Symmetric returns should have ~0 skewness."""
    returns = [0.01, -0.01, 0.02, -0.02, 0.01, -0.01, 0.02, -0.02]
    skew = _skewness(returns)
    assert abs(skew) < 0.1


def test_kurtosis_normal_like():
    """Uniform-ish returns should have slightly negative excess kurtosis."""
    # Near-uniform distribution has excess kurtosis ~ -1.2
    returns = [float(i) / 100 for i in range(-10, 11)]
    kurt = _kurtosis_excess(returns)
    assert kurt < 0  # platykurtic


def test_compute_statistical_metrics_integration():
    """Integration test: all fields present and reasonable."""
    returns = [0.02, -0.01, 0.03, -0.005, 0.015, 0.01, -0.02, 0.025, 0.01, -0.01, 0.02, 0.005]
    result = compute_statistical_metrics(returns, sharpe=1.5, n_trials=3)
    assert "psr" in result
    assert "dsr" in result
    assert "skewness" in result
    assert "excess_kurtosis" in result
    assert 0 <= result["psr"] <= 1
    assert 0 <= result["dsr"] <= 1
    assert result["n_trials"] == 3
