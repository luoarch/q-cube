"""Walk-forward analysis with expanding IS + rolling OOS windows."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from q3_quant_engine.backtest.engine import BacktestConfig, run_backtest


@dataclass
class WalkForwardConfig:
    backtest_config: BacktestConfig
    n_splits: int = 3
    oos_months: int = 12  # fixed OOS window size
    embargo_days: int = 21  # gap between IS and OOS (~1 month)


@dataclass
class WalkForwardResult:
    splits: list[dict]  # [{is_metrics, oos_metrics, is_period, oos_period}]
    is_avg: dict
    oos_avg: dict
    degradation: dict  # {sharpe: X%, cagr: Y%, ...}


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping day to valid range."""
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, max_day))


def generate_splits(
    start_date: date,
    end_date: date,
    n_splits: int,
    oos_months: int,
    embargo_days: int,
) -> list[dict]:
    """Generate expanding IS + rolling OOS splits.

    IS always starts from start_date (expanding window).
    OOS windows are fixed-size and roll forward.
    """
    splits = []

    for i in range(n_splits):
        # OOS windows work backwards from end_date
        oos_end = _add_months(end_date, -(n_splits - 1 - i) * oos_months)
        oos_start = _add_months(oos_end, -oos_months)

        # IS ends before embargo gap
        is_end = oos_start - timedelta(days=embargo_days)
        is_start = start_date  # expanding: always starts from beginning

        if is_end <= is_start:
            continue

        splits.append({
            "is_start": is_start,
            "is_end": is_end,
            "oos_start": oos_start,
            "oos_end": oos_end,
        })

    return splits


def run_walk_forward(session: Session, config: WalkForwardConfig) -> WalkForwardResult:
    """Run walk-forward analysis with expanding IS and rolling OOS windows."""
    splits = generate_splits(
        config.backtest_config.start_date,
        config.backtest_config.end_date,
        config.n_splits,
        config.oos_months,
        config.embargo_days,
    )

    results: list[dict] = []

    for split in splits:
        # In-sample backtest
        is_config = copy.copy(config.backtest_config)
        is_config.start_date = split["is_start"]
        is_config.end_date = split["is_end"]
        is_result = run_backtest(session, is_config)

        # Out-of-sample backtest
        oos_config = copy.copy(config.backtest_config)
        oos_config.start_date = split["oos_start"]
        oos_config.end_date = split["oos_end"]
        oos_result = run_backtest(session, oos_config)

        results.append({
            "is_metrics": is_result.metrics,
            "oos_metrics": oos_result.metrics,
            "is_period": {"start": split["is_start"], "end": split["is_end"]},
            "oos_period": {"start": split["oos_start"], "end": split["oos_end"]},
        })

    # Compute averages
    is_avg = _avg_metrics([r["is_metrics"] for r in results])
    oos_avg = _avg_metrics([r["oos_metrics"] for r in results])

    # Compute degradation
    degradation = {}
    for key in ("sharpe", "cagr", "sortino"):
        is_val = is_avg.get(key, 0)
        oos_val = oos_avg.get(key, 0)
        if is_val and is_val != 0:
            degradation[key] = round((oos_val - is_val) / abs(is_val), 4)
        else:
            degradation[key] = 0.0

    return WalkForwardResult(
        splits=results,
        is_avg=is_avg,
        oos_avg=oos_avg,
        degradation=degradation,
    )


def _avg_metrics(metrics_list: list[dict]) -> dict:
    """Average numeric metrics across splits."""
    if not metrics_list:
        return {}

    result: dict = {}
    numeric_keys = set()
    for m in metrics_list:
        for k, v in m.items():
            if isinstance(v, (int, float)):
                numeric_keys.add(k)

    for key in numeric_keys:
        vals = [m.get(key, 0) for m in metrics_list if isinstance(m.get(key), (int, float))]
        result[key] = round(sum(vals) / len(vals), 6) if vals else 0.0

    return result
