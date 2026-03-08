"""Backtest metrics computation tests."""

from __future__ import annotations

import math
from datetime import date

from q3_quant_engine.backtest.metrics import (
    compute_cagr,
    compute_max_drawdown,
    compute_metrics,
    compute_returns,
)


def test_compute_returns():
    """Returns are correctly computed as fractional changes."""
    curve = [
        {"date": "2024-01-01", "value": 100},
        {"date": "2024-02-01", "value": 110},
        {"date": "2024-03-01", "value": 99},
    ]
    returns = compute_returns(curve)
    assert len(returns) == 2
    assert abs(returns[0] - 0.1) < 1e-10  # 110/100 - 1
    assert abs(returns[1] - (-0.1)) < 1e-10  # 99/110 - 1


def test_sharpe_ratio_computation():
    """Sharpe = (mean_excess_return) / std * sqrt(periods_per_year)."""
    # Constant positive returns → high sharpe
    curve = [{"date": f"2024-{m:02d}-01", "value": 100 + i * 10} for i, m in enumerate(range(1, 13))]
    metrics = compute_metrics(curve, [], risk_free=0.0, periods_per_year=12.0)
    assert metrics["sharpe"] > 0
    # Zero volatility edge case is handled gracefully
    constant = [{"date": f"2024-{m:02d}-01", "value": 100} for m in range(1, 7)]
    m2 = compute_metrics(constant, [], risk_free=0.0, periods_per_year=12.0)
    assert m2["sharpe"] == 0.0


def test_max_drawdown_computation():
    """Correctly finds peak-to-trough."""
    curve = [
        {"date": "2024-01-01", "value": 100},
        {"date": "2024-02-01", "value": 120},  # peak
        {"date": "2024-03-01", "value": 90},   # trough (25% from peak)
        {"date": "2024-04-01", "value": 110},
    ]
    max_dd, duration = compute_max_drawdown(curve)
    assert abs(max_dd - 0.25) < 1e-10  # (120-90)/120
    assert duration > 0


def test_cagr_computation():
    """CAGR correctly computed over the time period."""
    curve = [
        {"date": date(2024, 1, 1), "value": 100},
        {"date": date(2025, 1, 1), "value": 110},
    ]
    cagr = compute_cagr(curve)
    assert abs(cagr - 0.1) < 0.01  # ~10% CAGR


def test_information_ratio_with_benchmark():
    """IR = mean(excess) / tracking_error."""
    strategy_curve = [
        {"date": f"2024-{m:02d}-01", "value": 100 + i * 12}
        for i, m in enumerate(range(1, 7))
    ]
    bench_curve = [
        {"date": f"2024-{m:02d}-01", "value": 100 + i * 8}
        for i, m in enumerate(range(1, 7))
    ]
    metrics = compute_metrics(
        strategy_curve, [],
        benchmark_curve=bench_curve,
        periods_per_year=12.0,
    )
    assert "information_ratio" in metrics
    assert "excess_return" in metrics
    assert "tracking_error" in metrics
    # Strategy outperforms benchmark → positive excess return
    assert metrics["excess_return"] > 0


def test_benchmark_excess_return():
    """Excess return computed when benchmark provided."""
    equity = [
        {"date": "2024-01-01", "value": 100},
        {"date": "2024-02-01", "value": 110},
        {"date": "2024-03-01", "value": 115},
    ]
    bench = [
        {"date": "2024-01-01", "value": 1000},
        {"date": "2024-02-01", "value": 1050},
        {"date": "2024-03-01", "value": 1080},
    ]
    metrics = compute_metrics(equity, [], benchmark_curve=bench)
    assert "excess_return" in metrics
    assert "tracking_error" in metrics
    assert "information_ratio" in metrics
    # Portfolio returned more than benchmark
    assert metrics["excess_return"] > 0


def test_no_benchmark_no_relative_metrics():
    """Without benchmark, relative metrics absent."""
    equity = [
        {"date": "2024-01-01", "value": 100},
        {"date": "2024-02-01", "value": 110},
    ]
    metrics = compute_metrics(equity, [])
    assert "excess_return" not in metrics
    assert "tracking_error" not in metrics
