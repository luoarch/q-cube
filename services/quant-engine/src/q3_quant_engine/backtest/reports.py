"""OOS, subperiod, and sensitivity reports for research validation."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from q3_quant_engine.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from q3_quant_engine.backtest.metrics import compute_metrics, compute_returns
from q3_quant_engine.backtest.statistical import compute_statistical_metrics
from q3_quant_engine.backtest.walk_forward import WalkForwardConfig, run_walk_forward

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OOS Report
# ---------------------------------------------------------------------------


@dataclass
class OOSReport:
    """Structured comparison of IS vs OOS performance."""

    is_metrics: dict
    oos_metrics: dict
    is_statistical: dict  # PSR, DSR, skew, kurtosis
    oos_statistical: dict
    degradation: dict  # {metric_name: (oos - is) / |is|}
    is_period: dict  # {start, end}
    oos_period: dict
    fragile: bool  # True if OOS Sharpe < 0 or degradation > threshold


# Degradation thresholds — beyond these the strategy is flagged fragile
DEGRADATION_THRESHOLDS = {
    "sharpe": -0.50,  # 50% drop
    "cagr": -0.60,
    "sortino": -0.50,
}


def generate_oos_report(
    session: Session,
    config: BacktestConfig,
    is_end: date,
    oos_start: date,
    n_trials: int = 1,
) -> OOSReport:
    """Generate a side-by-side IS vs OOS report.

    Args:
        config: Full-period backtest config (start_date to end_date)
        is_end: End of in-sample period
        oos_start: Start of out-of-sample period (gap = embargo)
        n_trials: Number of strategy variants tested (for DSR correction)
    """
    is_config = copy.copy(config)
    is_config.start_date = config.start_date
    is_config.end_date = is_end
    is_result = run_backtest(session, is_config)

    oos_config = copy.copy(config)
    oos_config.start_date = oos_start
    oos_config.end_date = config.end_date
    oos_result = run_backtest(session, oos_config)

    is_returns = compute_returns(is_result.equity_curve)
    oos_returns = compute_returns(oos_result.equity_curve)

    is_statistical = compute_statistical_metrics(
        is_returns, is_result.metrics.get("sharpe", 0), n_trials=n_trials,
    )
    oos_statistical = compute_statistical_metrics(
        oos_returns, oos_result.metrics.get("sharpe", 0), n_trials=n_trials,
    )

    degradation = _compute_degradation(is_result.metrics, oos_result.metrics)
    fragile = _is_fragile(oos_result.metrics, degradation)

    return OOSReport(
        is_metrics=is_result.metrics,
        oos_metrics=oos_result.metrics,
        is_statistical=is_statistical,
        oos_statistical=oos_statistical,
        degradation=degradation,
        is_period={"start": str(config.start_date), "end": str(is_end)},
        oos_period={"start": str(oos_start), "end": str(config.end_date)},
        fragile=fragile,
    )


def _compute_degradation(is_metrics: dict, oos_metrics: dict) -> dict:
    result = {}
    for key in ("sharpe", "cagr", "sortino", "max_drawdown", "volatility"):
        is_val = is_metrics.get(key, 0)
        oos_val = oos_metrics.get(key, 0)
        if is_val and is_val != 0:
            result[key] = round((oos_val - is_val) / abs(is_val), 4)
        else:
            result[key] = 0.0
    return result


def _is_fragile(oos_metrics: dict, degradation: dict) -> bool:
    if oos_metrics.get("sharpe", 0) < 0:
        return True
    for key, threshold in DEGRADATION_THRESHOLDS.items():
        if degradation.get(key, 0) < threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Subperiod Report
# ---------------------------------------------------------------------------


@dataclass
class SubperiodReport:
    """Performance breakdown by time subperiods."""

    subperiods: list[dict]  # [{label, start, end, metrics, returns_stats}]
    rolling_sharpe: list[dict]  # [{end_date, sharpe}] — rolling window
    regime_summary: dict  # {bull: metrics, bear: metrics, ...}
    fragile: bool


def generate_subperiod_report(
    session: Session,
    config: BacktestConfig,
    subperiod_months: int = 12,
    rolling_window_months: int = 12,
) -> SubperiodReport:
    """Break full backtest into subperiods and analyze each."""
    from q3_quant_engine.backtest.walk_forward import _add_months

    full_result = run_backtest(session, config)

    # 1. Split into subperiods
    subperiods: list[dict] = []
    current = config.start_date
    while current < config.end_date:
        sub_end = _add_months(current, subperiod_months)
        if sub_end > config.end_date:
            sub_end = config.end_date

        sub_config = copy.copy(config)
        sub_config.start_date = current
        sub_config.end_date = sub_end
        sub_result = run_backtest(session, sub_config)

        sub_returns = compute_returns(sub_result.equity_curve)

        subperiods.append({
            "label": f"{current.isoformat()} to {sub_end.isoformat()}",
            "start": str(current),
            "end": str(sub_end),
            "metrics": sub_result.metrics,
            "returns_stats": {
                "mean": round(sum(sub_returns) / len(sub_returns), 6) if sub_returns else 0.0,
                "count": len(sub_returns),
            },
        })
        current = sub_end

    # 2. Rolling Sharpe
    rolling_sharpe: list[dict] = []
    roll_start = config.start_date
    while True:
        roll_end = _add_months(roll_start, rolling_window_months)
        if roll_end > config.end_date:
            break
        roll_config = copy.copy(config)
        roll_config.start_date = roll_start
        roll_config.end_date = roll_end
        roll_result = run_backtest(session, roll_config)
        rolling_sharpe.append({
            "end_date": str(roll_end),
            "sharpe": roll_result.metrics.get("sharpe", 0),
        })
        roll_start = _add_months(roll_start, 3)  # step by quarter

    # 3. Regime classification (simple: positive CAGR = bull, negative = bear)
    regime_summary = _classify_regimes(subperiods)

    # 4. Fragile if any subperiod has Sharpe < -0.5 or one dominates
    fragile = _subperiod_fragile(subperiods)

    return SubperiodReport(
        subperiods=subperiods,
        rolling_sharpe=rolling_sharpe,
        regime_summary=regime_summary,
        fragile=fragile,
    )


def _classify_regimes(subperiods: list[dict]) -> dict:
    """Classify subperiods into bull/bear/stress/recovery regimes."""
    regimes: dict[str, list[dict]] = {"bull": [], "bear": [], "stress": [], "recovery": []}

    for i, sp in enumerate(subperiods):
        cagr = sp["metrics"].get("cagr", 0)
        dd = sp["metrics"].get("max_drawdown", 0)

        if dd > 0.20:
            regimes["stress"].append(sp["metrics"])
        elif cagr < 0:
            regimes["bear"].append(sp["metrics"])
        elif i > 0 and subperiods[i - 1]["metrics"].get("cagr", 0) < 0 and cagr > 0:
            regimes["recovery"].append(sp["metrics"])
        else:
            regimes["bull"].append(sp["metrics"])

    result = {}
    for regime, metrics_list in regimes.items():
        if metrics_list:
            result[regime] = {
                "count": len(metrics_list),
                "avg_sharpe": round(sum(m.get("sharpe", 0) for m in metrics_list) / len(metrics_list), 4),
                "avg_cagr": round(sum(m.get("cagr", 0) for m in metrics_list) / len(metrics_list), 6),
                "avg_max_dd": round(sum(m.get("max_drawdown", 0) for m in metrics_list) / len(metrics_list), 6),
            }
    return result


def _subperiod_fragile(subperiods: list[dict]) -> bool:
    """Strategy is fragile if dependent on a single exceptional subperiod."""
    if len(subperiods) < 2:
        return False

    sharpes = [sp["metrics"].get("sharpe", 0) for sp in subperiods]
    if any(s < -0.5 for s in sharpes):
        return True

    # Check if one subperiod dominates: best > 2x average of rest
    if len(sharpes) >= 3:
        best = max(sharpes)
        rest = [s for s in sharpes if s != best]
        avg_rest = sum(rest) / len(rest) if rest else 0
        if avg_rest > 0 and best > 3 * avg_rest:
            return True

    return False


# ---------------------------------------------------------------------------
# Sensitivity Report
# ---------------------------------------------------------------------------


@dataclass
class SensitivityReport:
    """Parameter sensitivity analysis results."""

    base_metrics: dict
    variations: list[dict]  # [{param, value, metrics, delta_sharpe, delta_cagr}]
    robust: bool  # True if strategy is stable across variations


def generate_sensitivity_report(
    session: Session,
    config: BacktestConfig,
) -> SensitivityReport:
    """Sweep key parameters and measure impact on metrics."""
    base_result = run_backtest(session, config)
    base_metrics = base_result.metrics
    base_sharpe = base_metrics.get("sharpe", 0)
    base_cagr = base_metrics.get("cagr", 0)

    variations: list[dict] = []

    # 1. Rebalance frequency
    for freq in ("monthly", "quarterly"):
        if freq == config.rebalance_freq:
            continue
        v_config = copy.copy(config)
        v_config.rebalance_freq = freq
        v_result = run_backtest(session, v_config)
        variations.append(_variation_entry("rebalance_freq", freq, v_result.metrics, base_sharpe, base_cagr))

    # 2. Top N
    for top_n in (10, 15, 20, 30):
        if top_n == config.top_n:
            continue
        v_config = copy.copy(config)
        v_config.top_n = top_n
        v_result = run_backtest(session, v_config)
        variations.append(_variation_entry("top_n", top_n, v_result.metrics, base_sharpe, base_cagr))

    # 3. Execution lag
    for lag in (0, 1, 2, 3):
        if lag == config.execution_lag_days:
            continue
        v_config = copy.copy(config)
        v_config.execution_lag_days = lag
        v_result = run_backtest(session, v_config)
        variations.append(_variation_entry("execution_lag_days", lag, v_result.metrics, base_sharpe, base_cagr))

    # 4. Cost model variations
    from q3_quant_engine.backtest.costs import CostModel, CONSERVATIVE
    cost_variations = [
        ("zero_cost", CostModel(0, 0, 0)),
        ("conservative", CONSERVATIVE),
        ("high_slippage", CostModel(0, 0.0005, 30.0)),
    ]
    for label, cm in cost_variations:
        v_config = copy.copy(config)
        v_config.cost_model = cm
        v_result = run_backtest(session, v_config)
        variations.append(_variation_entry("cost_model", label, v_result.metrics, base_sharpe, base_cagr))

    # 5. Min market cap variations
    for mcap in (100_000_000, 250_000_000, 500_000_000, 1_000_000_000):
        if mcap == (config.min_market_cap or 500_000_000):
            continue
        v_config = copy.copy(config)
        v_config.min_market_cap = float(mcap)
        v_result = run_backtest(session, v_config)
        label = f"{mcap/1e6:.0f}M"
        variations.append(_variation_entry("min_market_cap", label, v_result.metrics, base_sharpe, base_cagr))

    # 6. Min avg daily volume variations
    for vol in (500_000, 1_000_000, 2_000_000, 5_000_000):
        if vol == (config.min_avg_daily_volume or 1_000_000):
            continue
        v_config = copy.copy(config)
        v_config.min_avg_daily_volume = float(vol)
        v_result = run_backtest(session, v_config)
        label = f"{vol/1e6:.1f}M"
        variations.append(_variation_entry("min_avg_daily_volume", label, v_result.metrics, base_sharpe, base_cagr))

    # Robustness check: Sharpe doesn't swing more than 50% across variations
    robust = _check_robustness(variations, base_sharpe)

    return SensitivityReport(
        base_metrics=base_metrics,
        variations=variations,
        robust=robust,
    )


def _variation_entry(param: str, value: object, metrics: dict, base_sharpe: float, base_cagr: float) -> dict:
    sharpe = metrics.get("sharpe", 0)
    cagr = metrics.get("cagr", 0)
    return {
        "param": param,
        "value": value,
        "metrics": metrics,
        "delta_sharpe": round(sharpe - base_sharpe, 4),
        "delta_cagr": round(cagr - base_cagr, 6),
    }


def _check_robustness(variations: list[dict], base_sharpe: float) -> bool:
    if not variations or base_sharpe == 0:
        return True
    for v in variations:
        sharpe = v["metrics"].get("sharpe", 0)
        if abs(sharpe - base_sharpe) / max(abs(base_sharpe), 0.01) > 0.50:
            return False
    return True
