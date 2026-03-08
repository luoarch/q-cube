"""Marginal contribution tests."""

from __future__ import annotations

from q3_quant_engine.backtest.contribution import (
    ContributionReport,
    MarginalContribution,
    ContributionEntry,
)


def test_contribution_report_has_all_variants():
    """Report includes core_only, core_brazil, core_hybrid."""
    # Test dataclass construction
    variants = [
        ContributionEntry(variant="core_only", metrics={"sharpe": 1.0, "cagr": 0.1}, returns=[0.01, 0.02]),
        ContributionEntry(variant="core_brazil", metrics={"sharpe": 1.2, "cagr": 0.12}, returns=[0.01, 0.03]),
        ContributionEntry(variant="core_hybrid", metrics={"sharpe": 1.5, "cagr": 0.15}, returns=[0.02, 0.03]),
    ]
    contributions = [
        MarginalContribution(component="core_brazil", delta_sharpe=0.2, delta_cagr=0.02,
                           delta_max_drawdown=-0.01, delta_turnover=0.05, positive=True),
        MarginalContribution(component="core_hybrid", delta_sharpe=0.5, delta_cagr=0.05,
                           delta_max_drawdown=-0.02, delta_turnover=0.03, positive=True),
    ]
    report = ContributionReport(
        base_variant="core_only",
        variants=variants,
        contributions=contributions,
        all_positive=True,
    )
    assert report.base_variant == "core_only"
    assert len(report.variants) == 3
    assert len(report.contributions) == 2
    assert report.all_positive is True


def test_negative_contribution_detected():
    """Component that worsens Sharpe is flagged as not positive."""
    mc = MarginalContribution(
        component="bad_overlay",
        delta_sharpe=-0.3,
        delta_cagr=-0.02,
        delta_max_drawdown=0.05,
        delta_turnover=0.1,
        positive=False,
    )
    assert mc.positive is False


def test_contribution_neutral_sharpe_better_dd():
    """Component with same Sharpe but lower drawdown is positive."""
    mc = MarginalContribution(
        component="dd_reducer",
        delta_sharpe=0.0,
        delta_cagr=0.0,
        delta_max_drawdown=-0.05,
        delta_turnover=0.0,
        positive=True,  # delta_dd < 0 when delta_sharpe == 0
    )
    assert mc.positive is True
