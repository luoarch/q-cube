"""Marginal contribution analysis — proves each factor adds value.

Compares strategy variants to measure the incremental value of
quality overlay components (leverage, cash conversion).

Reference: docs/research-validation-protocol.md, Section 11.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from sqlalchemy.orm import Session

from q3_quant_engine.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from q3_quant_engine.backtest.metrics import compute_returns


@dataclass
class ContributionEntry:
    """Results for one strategy variant."""
    variant: str
    metrics: dict
    returns: list[float]


@dataclass
class MarginalContribution:
    """Marginal improvement of adding a component."""
    component: str
    delta_sharpe: float
    delta_cagr: float
    delta_max_drawdown: float
    delta_turnover: float
    positive: bool  # True if the component adds value


@dataclass
class ContributionReport:
    """Full marginal contribution analysis."""
    base_variant: str  # "core_only"
    variants: list[ContributionEntry]
    contributions: list[MarginalContribution]
    all_positive: bool  # True if every overlay adds value


def generate_contribution_report(
    session: Session,
    config: BacktestConfig,
) -> ContributionReport:
    """Run backtests for each variant and compute marginal contributions.

    Variants:
    1. core_only: magic_formula_original (EY + ROC only)
    2. core_brazil: magic_formula_brazil (core + sector/liquidity gates)
    3. core_hybrid: magic_formula_hybrid (core + quality overlay)
    """
    variants: list[ContributionEntry] = []

    variant_configs = [
        ("core_only", "magic_formula_original"),
        ("core_brazil", "magic_formula_brazil"),
        ("core_hybrid", "magic_formula_hybrid"),
    ]

    for variant_name, strategy_type in variant_configs:
        v_config = copy.copy(config)
        v_config.strategy_type = strategy_type
        result = run_backtest(session, v_config)
        returns = compute_returns(result.equity_curve)
        variants.append(ContributionEntry(
            variant=variant_name,
            metrics=result.metrics,
            returns=returns,
        ))

    # Compute marginal contributions relative to core_only
    base = variants[0]  # core_only
    contributions: list[MarginalContribution] = []

    for v in variants[1:]:
        delta_sharpe = v.metrics.get("sharpe", 0) - base.metrics.get("sharpe", 0)
        delta_cagr = v.metrics.get("cagr", 0) - base.metrics.get("cagr", 0)
        delta_dd = v.metrics.get("max_drawdown", 0) - base.metrics.get("max_drawdown", 0)
        delta_turnover = v.metrics.get("turnover_avg", 0) - base.metrics.get("turnover_avg", 0)

        # Positive if Sharpe improves or drawdown decreases
        positive = delta_sharpe > 0 or (delta_sharpe == 0 and delta_dd < 0)

        contributions.append(MarginalContribution(
            component=v.variant,
            delta_sharpe=round(delta_sharpe, 4),
            delta_cagr=round(delta_cagr, 6),
            delta_max_drawdown=round(delta_dd, 6),
            delta_turnover=round(delta_turnover, 4),
            positive=positive,
        ))

    all_positive = all(c.positive for c in contributions)

    return ContributionReport(
        base_variant="core_only",
        variants=variants,
        contributions=contributions,
        all_positive=all_positive,
    )
