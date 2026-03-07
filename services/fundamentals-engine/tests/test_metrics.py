"""Tests for metric computation strategies."""

from __future__ import annotations

from q3_fundamentals_engine.metrics.cash_conversion import CashConversionStrategy
from q3_fundamentals_engine.metrics.roic import RoicStrategy
from q3_fundamentals_engine.metrics.roe import RoeStrategy
from q3_fundamentals_engine.metrics.net_debt import NetDebtStrategy
from q3_fundamentals_engine.metrics.margins import GrossMarginStrategy, EbitMarginStrategy, NetMarginStrategy
from q3_fundamentals_engine.metrics.earnings_yield import EarningsYieldStrategy


def test_roic_computation() -> None:
    strategy = RoicStrategy()
    values = {
        "ebit": 1_000_000.0,
        "current_assets": 5_000_000.0,
        "current_liabilities": 3_000_000.0,
        "fixed_assets": 2_000_000.0,
    }
    assert strategy.supports(set(values.keys()))
    result = strategy.compute(values, ["filing-1"])
    assert result is not None
    # ROIC = 1M / (5M-3M + 2M) = 1M/4M = 0.25
    assert abs(result.value - 0.25) < 0.001


def test_net_debt_computation() -> None:
    strategy = NetDebtStrategy()
    values = {
        "short_term_debt": 100_000.0,
        "long_term_debt": 200_000.0,
        "cash_and_equivalents": 50_000.0,
    }
    assert strategy.supports(set(values.keys()))
    result = strategy.compute(values, ["filing-1"])
    assert result is not None
    # Net debt = 100K + 200K - 50K = 250K
    assert abs(result.value - 250_000.0) < 0.01


def test_gross_margin() -> None:
    strategy = GrossMarginStrategy()
    values = {"gross_profit": 300.0, "revenue": 1000.0}
    result = strategy.compute(values, ["f1"])
    assert result is not None
    assert abs(result.value - 0.3) < 0.001


def test_ebit_margin() -> None:
    strategy = EbitMarginStrategy()
    values = {"ebit": 150.0, "revenue": 1000.0}
    result = strategy.compute(values, ["f1"])
    assert result is not None
    assert abs(result.value - 0.15) < 0.001


def test_net_margin() -> None:
    strategy = NetMarginStrategy()
    values = {"net_income": 100.0, "revenue": 1000.0}
    result = strategy.compute(values, ["f1"])
    assert result is not None
    assert abs(result.value - 0.1) < 0.001


def test_earnings_yield_with_market_cap() -> None:
    strategy = EarningsYieldStrategy()
    values = {
        "ebit": 500_000.0,
        "short_term_debt": 100_000.0,
        "long_term_debt": 200_000.0,
        "cash_and_equivalents": 50_000.0,
    }
    # EV = market_cap + net_debt = 1M + 250K = 1.25M
    # EY = 500K / 1.25M = 0.4
    result = strategy.compute(values, ["f1"], market_cap=1_000_000.0)
    assert result is not None
    assert abs(result.value - 0.4) < 0.001


def test_roic_missing_inputs() -> None:
    strategy = RoicStrategy()
    values = {"ebit": 1_000_000.0}  # missing other inputs
    assert not strategy.supports(set(values.keys()))


# --- ROE ---

def test_roe_positive_equity() -> None:
    strategy = RoeStrategy()
    values = {"net_income": 200_000.0, "equity": 1_000_000.0}
    assert strategy.supports(set(values.keys()))
    result = strategy.compute(values, ["f1"])
    assert result is not None
    assert result.metric_code == "roe"
    # ROE = 200K / 1M = 0.2
    assert abs(result.value - 0.2) < 0.001


def test_roe_zero_equity() -> None:
    strategy = RoeStrategy()
    values = {"net_income": 200_000.0, "equity": 0.0}
    result = strategy.compute(values, ["f1"])
    assert result is None


def test_roe_negative_equity() -> None:
    strategy = RoeStrategy()
    values = {"net_income": 200_000.0, "equity": -500_000.0}
    result = strategy.compute(values, ["f1"])
    assert result is not None
    # ROE = 200K / -500K = -0.4
    assert abs(result.value - (-0.4)) < 0.001


def test_roe_missing_inputs() -> None:
    strategy = RoeStrategy()
    values = {"net_income": 200_000.0}
    assert not strategy.supports(set(values.keys()))


# --- Cash Conversion ---

def test_cash_conversion_positive_ni() -> None:
    strategy = CashConversionStrategy()
    values = {"cash_from_operations": 300_000.0, "net_income": 200_000.0}
    assert strategy.supports(set(values.keys()))
    result = strategy.compute(values, ["f1"])
    assert result is not None
    assert result.metric_code == "cash_conversion"
    # CC = 300K / 200K = 1.5
    assert abs(result.value - 1.5) < 0.001


def test_cash_conversion_zero_ni() -> None:
    strategy = CashConversionStrategy()
    values = {"cash_from_operations": 300_000.0, "net_income": 0.0}
    result = strategy.compute(values, ["f1"])
    assert result is None


def test_cash_conversion_negative_ni() -> None:
    strategy = CashConversionStrategy()
    values = {"cash_from_operations": 300_000.0, "net_income": -100_000.0}
    result = strategy.compute(values, ["f1"])
    assert result is None


def test_cash_conversion_missing_inputs() -> None:
    strategy = CashConversionStrategy()
    values = {"cash_from_operations": 300_000.0}
    assert not strategy.supports(set(values.keys()))
