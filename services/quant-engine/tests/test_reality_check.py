"""Reality Check (White 2000) tests."""

from __future__ import annotations

import math

from q3_quant_engine.backtest.reality_check import (
    RealityCheckReport,
    StrategyReturns,
    _sharpe_from_returns,
    _stationary_bootstrap,
    run_reality_check,
)


def _make_returns(mean: float, std: float, n: int, seed: int = 0) -> list[float]:
    """Generate deterministic pseudo-returns."""
    import random
    rng = random.Random(seed)
    return [mean + std * (rng.gauss(0, 1)) for _ in range(n)]


def test_sharpe_from_returns_positive():
    """Positive mean returns → positive Sharpe."""
    returns = [0.02, 0.01, 0.03, 0.02, 0.015, 0.025, 0.01, 0.02, 0.03, 0.015, 0.02, 0.01]
    sharpe = _sharpe_from_returns(returns)
    assert sharpe > 0


def test_sharpe_from_returns_zero_std():
    """Constant returns → Sharpe = 0 (no std)."""
    returns = [0.01] * 12
    sharpe = _sharpe_from_returns(returns)
    assert sharpe == 0.0


def test_bootstrap_returns_correct_count():
    """Bootstrap produces n_bootstrap samples."""
    matrix = [[0.01, 0.02, -0.01, 0.015] for _ in range(3)]
    result = _stationary_bootstrap(matrix, n_bootstrap=100, seed=42)
    assert len(result) == 100


def test_bootstrap_centered_mean_near_zero():
    """Under null (centered returns), mean of max Sharpes should be moderate."""
    matrix = [_make_returns(0.02, 0.05, 60, seed=i) for i in range(5)]
    max_sharpes = _stationary_bootstrap(matrix, n_bootstrap=500, seed=42)
    # Mean of null distribution should be positive (max of centered)
    # but typically < 2 for 5 strategies and 60 returns
    mean_max = sum(max_sharpes) / len(max_sharpes)
    assert mean_max < 3.0


def test_reality_check_single_strategy_low_pvalue():
    """Single strong strategy with no snooping → low p-value."""
    strong = StrategyReturns(
        name="strong",
        returns=_make_returns(0.03, 0.02, 60, seed=1),
    )
    report = run_reality_check([strong], n_bootstrap=500, seed=42)
    assert report.n_strategies == 1
    assert report.best_strategy == "strong"
    # With very strong returns vs null, p-value should be low
    assert report.p_value < 0.20


def test_reality_check_many_weak_strategies_high_pvalue():
    """Many weak strategies → high p-value (data snooping)."""
    strategies = [
        StrategyReturns(name=f"weak_{i}", returns=_make_returns(0.001, 0.05, 60, seed=i))
        for i in range(50)
    ]
    report = run_reality_check(strategies, n_bootstrap=500, seed=42)
    assert report.n_strategies == 50
    # Best of 50 weak strategies should be explainable by chance
    assert report.p_value >= 0.05


def test_reality_check_hypothesis_registry():
    """All tested strategies are recorded in the registry."""
    strategies = [
        StrategyReturns(name="alpha", returns=_make_returns(0.02, 0.03, 24, seed=1)),
        StrategyReturns(name="beta", returns=_make_returns(0.01, 0.03, 24, seed=2)),
        StrategyReturns(name="gamma", returns=_make_returns(0.015, 0.03, 24, seed=3)),
    ]
    report = run_reality_check(strategies, n_bootstrap=100, seed=42)
    names = {h["name"] for h in report.hypothesis_registry}
    assert names == {"alpha", "beta", "gamma"}
    for h in report.hypothesis_registry:
        assert "sharpe" in h
        assert "n_returns" in h


def test_reality_check_reproducible_with_seed():
    """Same seed → same results."""
    strategies = [
        StrategyReturns(name="a", returns=_make_returns(0.02, 0.04, 36, seed=1)),
        StrategyReturns(name="b", returns=_make_returns(0.01, 0.04, 36, seed=2)),
    ]
    r1 = run_reality_check(strategies, n_bootstrap=200, seed=123)
    r2 = run_reality_check(strategies, n_bootstrap=200, seed=123)
    assert r1.p_value == r2.p_value
    assert r1.bootstrap_max_sharpes == r2.bootstrap_max_sharpes


def test_reality_check_empty_strategies():
    """Empty input → safe defaults."""
    report = run_reality_check([])
    assert report.n_strategies == 0
    assert report.p_value == 1.0
    assert not report.reject_null
