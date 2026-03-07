"""Reality Check for data snooping — White (2000).

Tests whether the best strategy's performance is statistically significant
after accounting for the number of strategies tested on the same data.

Uses a bootstrap-based approach: under the null hypothesis (all strategies
have zero expected return), we estimate the distribution of the maximum
Sharpe ratio across N strategies and compute a corrected p-value.

Reference: White, H. (2000). A Reality Check for Data Snooping.
Econometrica, 68(5), 1097–1126.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from q3_quant_engine.backtest.metrics import _mean, _std, compute_returns


@dataclass
class StrategyReturns:
    """Return series for one strategy variant."""

    name: str
    returns: list[float]
    sharpe: float = 0.0


@dataclass
class RealityCheckReport:
    """Results of the White Reality Check test."""

    best_strategy: str
    best_sharpe: float
    n_strategies: int
    n_bootstrap: int
    p_value: float  # corrected p-value (probability of seeing this under null)
    bootstrap_max_sharpes: list[float]  # distribution under null
    reject_null: bool  # True if p_value < significance_level
    significance_level: float
    hypothesis_registry: list[dict]  # all strategies tested


def _sharpe_from_returns(returns: list[float], periods_per_year: float = 12.0) -> float:
    """Compute annualized Sharpe from return series."""
    if len(returns) < 2:
        return 0.0
    s = _std(returns)
    if s == 0:
        return 0.0
    return _mean(returns) / s * math.sqrt(periods_per_year)


def _stationary_bootstrap(
    returns_matrix: list[list[float]],
    n_bootstrap: int,
    block_size: float = 6.0,
    seed: int | None = None,
) -> list[float]:
    """Stationary bootstrap (Politis & Romano 1994) for the max Sharpe.

    Generates bootstrap samples maintaining temporal dependence via
    geometric-distributed block lengths.

    Args:
        returns_matrix: list of return series (one per strategy), all same length
        n_bootstrap: number of bootstrap iterations
        block_size: expected block length (geometric distribution parameter)
        seed: random seed for reproducibility

    Returns:
        List of max Sharpe ratios under null (centered returns)
    """
    rng = random.Random(seed)
    n_strategies = len(returns_matrix)
    if n_strategies == 0:
        return []
    T = len(returns_matrix[0])
    if T < 2:
        return [0.0] * n_bootstrap

    # Center returns (impose null: mean = 0)
    centered = []
    for returns in returns_matrix:
        m = _mean(returns)
        centered.append([r - m for r in returns])

    p = 1.0 / block_size  # probability of starting a new block
    max_sharpes: list[float] = []

    for _ in range(n_bootstrap):
        # Generate bootstrap indices using stationary bootstrap
        indices: list[int] = []
        pos = rng.randint(0, T - 1)
        for _ in range(T):
            indices.append(pos)
            if rng.random() < p:
                pos = rng.randint(0, T - 1)  # new block
            else:
                pos = (pos + 1) % T  # continue block

        # Compute Sharpe for each strategy using bootstrapped returns
        boot_sharpes = []
        for s in range(n_strategies):
            boot_returns = [centered[s][i] for i in indices]
            boot_sharpes.append(_sharpe_from_returns(boot_returns))

        max_sharpes.append(max(boot_sharpes))

    return max_sharpes


def run_reality_check(
    strategies: list[StrategyReturns],
    n_bootstrap: int = 1000,
    significance_level: float = 0.05,
    block_size: float = 6.0,
    seed: int | None = 42,
) -> RealityCheckReport:
    """Run White's Reality Check on a set of strategy variants.

    Tests H0: The best strategy has no genuine edge (its Sharpe is
    explainable by data snooping across N strategies tested).

    Args:
        strategies: list of StrategyReturns (must have same-length return series)
        n_bootstrap: number of bootstrap samples
        significance_level: threshold for rejecting H0
        block_size: expected block length for stationary bootstrap
        seed: random seed for reproducibility
    """
    if not strategies:
        return RealityCheckReport(
            best_strategy="", best_sharpe=0.0, n_strategies=0,
            n_bootstrap=0, p_value=1.0, bootstrap_max_sharpes=[],
            reject_null=False, significance_level=significance_level,
            hypothesis_registry=[],
        )

    # Compute Sharpe for each strategy
    for s in strategies:
        if s.sharpe == 0.0 and s.returns:
            s.sharpe = _sharpe_from_returns(s.returns)

    # Find best
    best = max(strategies, key=lambda s: s.sharpe)

    # Build hypothesis registry
    registry = [
        {"name": s.name, "sharpe": round(s.sharpe, 4), "n_returns": len(s.returns)}
        for s in strategies
    ]

    # Bootstrap under null
    returns_matrix = [s.returns for s in strategies]

    # Ensure all series are same length (truncate to min)
    min_len = min(len(r) for r in returns_matrix)
    returns_matrix = [r[:min_len] for r in returns_matrix]

    bootstrap_max_sharpes = _stationary_bootstrap(
        returns_matrix, n_bootstrap, block_size, seed,
    )

    # p-value: fraction of bootstrap max Sharpes >= observed best Sharpe
    if bootstrap_max_sharpes:
        n_exceeding = sum(1 for bs in bootstrap_max_sharpes if bs >= best.sharpe)
        p_value = n_exceeding / len(bootstrap_max_sharpes)
    else:
        p_value = 1.0

    return RealityCheckReport(
        best_strategy=best.name,
        best_sharpe=round(best.sharpe, 4),
        n_strategies=len(strategies),
        n_bootstrap=n_bootstrap,
        p_value=round(p_value, 4),
        bootstrap_max_sharpes=bootstrap_max_sharpes,
        reject_null=p_value < significance_level,
        significance_level=significance_level,
        hypothesis_registry=registry,
    )
