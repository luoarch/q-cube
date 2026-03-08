"""Backtest engine tests."""

from __future__ import annotations

from datetime import date

from q3_quant_engine.backtest.costs import CostModel
from q3_quant_engine.backtest.engine import (
    BacktestConfig,
    _generate_rebalance_dates,
)


def test_backtest_monthly_rebalance_dates():
    """Monthly config produces first-business-day dates."""
    dates = _generate_rebalance_dates(date(2024, 1, 1), date(2024, 6, 30), "monthly")
    assert len(dates) == 6
    for d in dates:
        assert d.weekday() < 5  # Not weekend
        assert d.day <= 3  # First few days of month


def test_backtest_quarterly_rebalance_dates():
    """Quarterly config: Jan/Apr/Jul/Oct."""
    dates = _generate_rebalance_dates(date(2024, 1, 1), date(2024, 12, 31), "quarterly")
    months = {d.month for d in dates}
    assert months.issubset({1, 4, 7, 10})
    assert len(dates) == 4


def test_cost_model_total_cost():
    """CostModel correctly combines fixed + proportional + slippage."""
    model = CostModel(fixed_cost_per_trade=10.0, proportional_cost=0.001, slippage_bps=20.0)
    trade_value = 100_000.0
    cost = model.total_cost(trade_value)
    expected = 10.0 + 100_000 * 0.001 + 100_000 * (20 / 10_000)
    assert abs(cost - expected) < 0.01


def test_cost_model_default_brazil():
    """Brazil realistic model: 5 bps proportional + 10 bps slippage."""
    from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC
    cost = BRAZIL_REALISTIC.total_cost(100_000)
    # 0 fixed + 100k * 0.0005 + 100k * 0.001 = 50 + 100 = 150
    assert abs(cost - 150.0) < 0.01


def test_backtest_execution_lag_concept():
    """Execution lag means trades happen after ranking date.

    Verify the rebalance dates are correctly generated and the lag
    would shift execution forward.
    """
    config = BacktestConfig(
        strategy_type="magic_formula_original",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        execution_lag_days=2,
    )
    dates = _generate_rebalance_dates(config.start_date, config.end_date, config.rebalance_freq)
    assert len(dates) == 3
    # Execution would be at date + 2 days
    for d in dates:
        exec_date = date(d.year, d.month, d.day + config.execution_lag_days)
        assert exec_date > d


def test_lot_rounding():
    """Shares rounded to lot size."""
    from q3_quant_engine.backtest.engine import _round_to_lot
    assert _round_to_lot(150, 100) == 100
    assert _round_to_lot(99, 100) == 0
    assert _round_to_lot(200, 100) == 200
    assert _round_to_lot(350, 100) == 300
    assert _round_to_lot(50, 1) == 50  # lot_size=1 means no rounding


def test_lot_rounding_zero():
    """Zero shares stays zero."""
    from q3_quant_engine.backtest.engine import _round_to_lot
    assert _round_to_lot(0, 100) == 0
