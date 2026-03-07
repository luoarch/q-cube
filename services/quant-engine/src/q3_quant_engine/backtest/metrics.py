"""Backtest performance metrics computation."""

from __future__ import annotations

import math
from datetime import date


def compute_returns(equity_curve: list[dict]) -> list[float]:
    """Compute period-over-period returns from an equity curve.

    Each element is {date, value}. Returns list of fractional returns
    (len = len(equity_curve) - 1).
    """
    if len(equity_curve) < 2:
        return []
    returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]["value"]
        curr = equity_curve[i]["value"]
        if prev and prev != 0:
            returns.append(curr / prev - 1.0)
        else:
            returns.append(0.0)
    return returns


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float], ddof: int = 1) -> float:
    if len(xs) <= ddof:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - ddof))


def _downside_std(xs: list[float], threshold: float = 0.0, ddof: int = 1) -> float:
    downs = [min(x - threshold, 0.0) for x in xs]
    if len(downs) <= ddof:
        return 0.0
    return math.sqrt(sum(d**2 for d in downs) / (len(downs) - ddof))


def compute_cagr(equity_curve: list[dict]) -> float:
    if len(equity_curve) < 2:
        return 0.0
    start_val = equity_curve[0]["value"]
    end_val = equity_curve[-1]["value"]
    if start_val <= 0:
        return 0.0

    start_date = equity_curve[0]["date"]
    end_date = equity_curve[-1]["date"]
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    years = (end_date - start_date).days / 365.25
    if years <= 0:
        return 0.0
    return (end_val / start_val) ** (1.0 / years) - 1.0


def compute_max_drawdown(equity_curve: list[dict]) -> tuple[float, int]:
    """Returns (max_drawdown_fraction, max_drawdown_duration_days)."""
    if len(equity_curve) < 2:
        return 0.0, 0

    peak = equity_curve[0]["value"]
    max_dd = 0.0
    max_dd_duration = 0
    peak_date = equity_curve[0]["date"]
    if isinstance(peak_date, str):
        peak_date = date.fromisoformat(peak_date)

    for point in equity_curve[1:]:
        val = point["value"]
        d = point["date"]
        if isinstance(d, str):
            d = date.fromisoformat(d)

        if val >= peak:
            peak = val
            peak_date = d
        else:
            dd = (peak - val) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                max_dd_duration = (d - peak_date).days

    return max_dd, max_dd_duration


def compute_metrics(
    equity_curve: list[dict],
    trades: list[dict],
    benchmark_curve: list[dict] | None = None,
    risk_free: float = 0.0,
    periods_per_year: float = 12.0,
) -> dict:
    """Compute comprehensive backtest metrics.

    Args:
        equity_curve: [{date, value}, ...]
        trades: [{date, ticker, shares, price, cost, side}, ...]
        benchmark_curve: optional [{date, value}, ...] for relative metrics
        risk_free: annualized risk-free rate
        periods_per_year: annualization factor (12 for monthly, 252 for daily)
    """
    returns = compute_returns(equity_curve)

    if not returns:
        return {
            "cagr": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_duration_days": 0,
            "turnover_avg": 0.0,
            "hit_rate": 0.0,
            "total_costs": 0.0,
        }

    cagr = compute_cagr(equity_curve)
    vol = _std(returns) * math.sqrt(periods_per_year)
    rf_per_period = risk_free / periods_per_year
    excess_returns = [r - rf_per_period for r in returns]
    sharpe = (_mean(excess_returns) / _std(returns) * math.sqrt(periods_per_year)) if _std(returns) > 0 else 0.0
    ds = _downside_std(excess_returns)
    sortino = (_mean(excess_returns) / ds * math.sqrt(periods_per_year)) if ds > 0 else 0.0
    max_dd, max_dd_duration = compute_max_drawdown(equity_curve)

    total_costs = sum(t.get("cost", 0.0) for t in trades)

    # Hit rate: fraction of trades with positive P&L (approximate from buy/sell pairs)
    winning = sum(1 for t in trades if t.get("side") == "sell" and t.get("pnl", 0.0) > 0)
    sell_count = sum(1 for t in trades if t.get("side") == "sell")
    hit_rate = winning / sell_count if sell_count > 0 else 0.0

    # Average turnover per rebalance
    buy_value = sum(abs(t.get("price", 0.0) * t.get("shares", 0)) for t in trades if t.get("side") == "buy")
    rebalance_dates = {t.get("date") for t in trades}
    n_rebalances = len(rebalance_dates) if rebalance_dates else 1
    avg_portfolio_val = _mean([p["value"] for p in equity_curve]) if equity_curve else 1.0
    turnover_avg = (buy_value / n_rebalances / avg_portfolio_val) if avg_portfolio_val > 0 else 0.0

    result: dict = {
        "cagr": round(cagr, 6),
        "volatility": round(vol, 6),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "max_drawdown": round(max_dd, 6),
        "max_drawdown_duration_days": max_dd_duration,
        "turnover_avg": round(turnover_avg, 4),
        "hit_rate": round(hit_rate, 4),
        "total_costs": round(total_costs, 2),
    }

    # Benchmark-relative metrics
    if benchmark_curve:
        bench_returns = compute_returns(benchmark_curve)
        min_len = min(len(returns), len(bench_returns))
        if min_len > 0:
            excess = [returns[i] - bench_returns[i] for i in range(min_len)]
            tracking_error = _std(excess) * math.sqrt(periods_per_year) if len(excess) > 1 else 0.0
            mean_excess = _mean(excess) * periods_per_year
            ir = mean_excess / tracking_error if tracking_error > 0 else 0.0
            result["excess_return"] = round(mean_excess, 6)
            result["tracking_error"] = round(tracking_error, 6)
            result["information_ratio"] = round(ir, 4)

    return result
