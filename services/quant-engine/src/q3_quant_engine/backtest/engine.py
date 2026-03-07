"""Backtest engine — simulates strategy execution over historical periods."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC, CostModel
from q3_quant_engine.backtest.metrics import compute_metrics
from q3_quant_engine.data.pit_data import (
    fetch_eligible_universe_pit,
    fetch_fundamentals_pit,
    fetch_market_pit,
)
from q3_quant_engine.strategies.ranking import (
    RankedAsset,
    _compute_ey_roc,
    _rank_descending,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    strategy_type: str  # "magic_formula_original" | "magic_formula_brazil" | "magic_formula_hybrid"
    start_date: date
    end_date: date
    rebalance_freq: str = "monthly"  # "monthly" | "quarterly"
    execution_lag_days: int = 1
    top_n: int = 20
    equal_weight: bool = True
    cost_model: CostModel = field(default_factory=lambda: BRAZIL_REALISTIC)
    initial_capital: float = 1_000_000.0
    benchmark: str | None = None


@dataclass
class BacktestResult:
    config: BacktestConfig
    equity_curve: list[dict]  # [{date, value}]
    trades: list[dict]  # [{date, ticker, shares, price, cost, side}]
    holdings_history: list[dict]  # [{date, holdings: [{ticker, weight, value}]}]
    metrics: dict
    rebalance_dates: list[date]


def _generate_rebalance_dates(start: date, end: date, freq: str) -> list[date]:
    """Generate rebalance dates between start and end.

    Monthly: first business day of each month.
    Quarterly: first business day of Jan/Apr/Jul/Oct.
    """
    quarterly_months = {1, 4, 7, 10}
    dates: list[date] = []

    current = start.replace(day=1)
    if current < start:
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    while current <= end:
        if freq == "quarterly" and current.month not in quarterly_months:
            # Advance to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
            continue

        # Adjust to first business day (skip weekends)
        rebal = current
        while rebal.weekday() >= 5:  # 5=Sat, 6=Sun
            rebal += timedelta(days=1)

        if start <= rebal <= end:
            dates.append(rebal)

        # Next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return dates


def _rank_pit_data(
    fundamentals: list[tuple],
    strategy_type: str,
) -> list[RankedAsset]:
    """Rank PIT data using the same logic as the live ranking strategies."""
    from q3_quant_engine.strategies.ranking import (
        EXCLUDED_SECTORS,
        MIN_AVG_DAILY_VOLUME,
        MIN_MARKET_CAP,
        _rank_percentile,
        WEIGHT_CORE,
        WEIGHT_QUALITY,
        _rank_ascending,
        _safe_div,
    )

    if not fundamentals:
        return []

    # Apply filters based on strategy type
    filtered: list[tuple[int, object, object, float | None, float | None]] = []
    idx = 0
    for asset, fs in fundamentals:
        if strategy_type in ("magic_formula_brazil", "magic_formula_hybrid"):
            if asset.sector and asset.sector.lower() in EXCLUDED_SECTORS:
                continue
            if fs.avg_daily_volume is not None and fs.avg_daily_volume < MIN_AVG_DAILY_VOLUME:
                continue
            if fs.market_cap is not None and fs.market_cap < MIN_MARKET_CAP:
                continue
            if fs.ebit is None or fs.ebit <= 0:
                continue

        ey, roc = _compute_ey_roc(fs)
        filtered.append((idx, asset, fs, ey, roc))
        idx += 1

    if not filtered:
        return []

    n = len(filtered)
    ey_ranks = _rank_descending([(i, ey) for i, _, _, ey, _ in filtered])
    roc_ranks = _rank_descending([(i, roc) for i, _, _, _, roc in filtered])

    if strategy_type == "magic_formula_hybrid":
        ey_pct = _rank_percentile(ey_ranks, n)
        roc_pct = _rank_percentile(roc_ranks, n)

        debt_ebitda_values = []
        cash_conv_values = []
        for i, _, fs, _, _ in filtered:
            if hasattr(fs, "debt_to_ebitda") and fs.debt_to_ebitda is not None:
                debt_ebitda_values.append((i, float(fs.debt_to_ebitda)))
            else:
                debt_ebitda_values.append((i, _safe_div(fs.net_debt, fs.ebitda)))
            val = getattr(fs, "cash_conversion", None)
            cash_conv_values.append((i, float(val) if val is not None else None))

        debt_ebitda_ranks = _rank_ascending(debt_ebitda_values)
        cash_conv_ranks = _rank_descending(cash_conv_values)
        debt_ebitda_pct = _rank_percentile(debt_ebitda_ranks, n)
        cash_conv_pct = _rank_percentile(cash_conv_ranks, n)

        results = []
        for i, asset, fs, ey, roc in filtered:
            core_score = 0.5 * ey_pct[i] + 0.5 * roc_pct[i]
            quality_signals = []
            has_dte = (
                (hasattr(fs, "debt_to_ebitda") and fs.debt_to_ebitda is not None)
                or (fs.net_debt is not None and fs.ebitda is not None and fs.ebitda != 0)
            )
            if has_dte:
                quality_signals.append(debt_ebitda_pct[i])
            if getattr(fs, "cash_conversion", None) is not None:
                quality_signals.append(cash_conv_pct[i])

            if quality_signals:
                quality_score = sum(quality_signals) / len(quality_signals)
                final_score = WEIGHT_CORE * core_score + WEIGHT_QUALITY * quality_score
            else:
                final_score = core_score

            results.append(RankedAsset(
                ticker=asset.ticker, name=asset.name, sector=asset.sector,
                earnings_yield=ey, return_on_capital=roc, combined_rank=0,
                score_details={"final_score": round(final_score, 6)},
            ))
        results.sort(key=lambda r: r.score_details["final_score"])
    else:
        results = []
        for i, asset, _, ey, roc in filtered:
            combined = ey_ranks[i] + roc_ranks[i]
            results.append(RankedAsset(
                ticker=asset.ticker, name=asset.name, sector=asset.sector,
                earnings_yield=ey, return_on_capital=roc, combined_rank=combined,
                score_details={"ey_rank": ey_ranks[i], "roc_rank": roc_ranks[i]},
            ))
        results.sort(key=lambda r: r.combined_rank)

    for rank, r in enumerate(results, 1):
        r.combined_rank = rank

    return results


def run_backtest(session: Session, config: BacktestConfig) -> BacktestResult:
    """Execute a full backtest simulation.

    Core loop:
    1. Generate rebalance dates
    2. For each rebalance: rank PIT, select top_n, compute trades with costs
    3. Track equity curve and holdings
    """
    rebalance_dates = _generate_rebalance_dates(config.start_date, config.end_date, config.rebalance_freq)

    if not rebalance_dates:
        return BacktestResult(
            config=config, equity_curve=[], trades=[], holdings_history=[],
            metrics={}, rebalance_dates=[],
        )

    cash = config.initial_capital
    holdings: dict[str, dict] = {}  # {ticker: {shares, last_price}}
    equity_curve: list[dict] = [{"date": config.start_date, "value": config.initial_capital}]
    all_trades: list[dict] = []
    holdings_history: list[dict] = []

    for rebal_date in rebalance_dates:
        # 1. Run PIT ranking at rebalance date
        fundamentals = fetch_fundamentals_pit(session, rebal_date)
        universe = fetch_eligible_universe_pit(session, rebal_date)
        fundamentals = [(a, fs) for a, fs in fundamentals if a.ticker in universe]

        ranked = _rank_pit_data(fundamentals, config.strategy_type)
        top_picks = ranked[: config.top_n]

        if not top_picks:
            equity_curve.append({"date": rebal_date, "value": _portfolio_value(holdings, cash)})
            continue

        # 2. Get execution prices at rebalance_date + lag
        exec_date = rebal_date + timedelta(days=config.execution_lag_days)
        prices = fetch_market_pit(session, exec_date)

        # 3. Compute target portfolio
        portfolio_value = _portfolio_value(holdings, cash)
        target_tickers = {r.ticker for r in top_picks if r.ticker in prices}

        if not target_tickers:
            equity_curve.append({"date": rebal_date, "value": portfolio_value})
            continue

        target_weight = 1.0 / len(target_tickers) if config.equal_weight else 1.0 / len(target_tickers)
        target_value_per = portfolio_value * target_weight

        # 4. Sell positions not in target
        for ticker in list(holdings.keys()):
            if ticker not in target_tickers:
                h = holdings[ticker]
                price_data = prices.get(ticker)
                sell_price = price_data.price if price_data and price_data.price else h["last_price"]
                if sell_price and h["shares"] > 0:
                    trade_value = h["shares"] * sell_price
                    cost = config.cost_model.total_cost(trade_value)
                    cash += trade_value - cost
                    all_trades.append({
                        "date": exec_date, "ticker": ticker, "shares": -h["shares"],
                        "price": sell_price, "cost": cost, "side": "sell",
                    })
                del holdings[ticker]

        # 5. Rebalance existing + buy new
        for ticker in target_tickers:
            price_data = prices.get(ticker)
            if not price_data or not price_data.price:
                continue

            current_shares = holdings.get(ticker, {}).get("shares", 0)
            current_value = current_shares * price_data.price
            diff_value = target_value_per - current_value

            if abs(diff_value) < 1.0:
                # No meaningful trade needed
                holdings[ticker] = {"shares": current_shares, "last_price": price_data.price}
                continue

            if diff_value > 0:
                # Buy
                shares_to_buy = int(diff_value / price_data.price)
                if shares_to_buy <= 0:
                    holdings[ticker] = {"shares": current_shares, "last_price": price_data.price}
                    continue
                trade_value = shares_to_buy * price_data.price
                cost = config.cost_model.total_cost(trade_value)
                if trade_value + cost > cash:
                    shares_to_buy = int(cash / (price_data.price * (1 + config.cost_model.proportional_cost + config.cost_model.slippage_bps / 10_000)))
                    if shares_to_buy <= 0:
                        holdings[ticker] = {"shares": current_shares, "last_price": price_data.price}
                        continue
                    trade_value = shares_to_buy * price_data.price
                    cost = config.cost_model.total_cost(trade_value)
                cash -= trade_value + cost
                new_shares = current_shares + shares_to_buy
                holdings[ticker] = {"shares": new_shares, "last_price": price_data.price}
                all_trades.append({
                    "date": exec_date, "ticker": ticker, "shares": shares_to_buy,
                    "price": price_data.price, "cost": cost, "side": "buy",
                })
            else:
                # Sell excess
                shares_to_sell = int(abs(diff_value) / price_data.price)
                if shares_to_sell <= 0:
                    holdings[ticker] = {"shares": current_shares, "last_price": price_data.price}
                    continue
                shares_to_sell = min(shares_to_sell, current_shares)
                trade_value = shares_to_sell * price_data.price
                cost = config.cost_model.total_cost(trade_value)
                cash += trade_value - cost
                new_shares = current_shares - shares_to_sell
                holdings[ticker] = {"shares": new_shares, "last_price": price_data.price}
                all_trades.append({
                    "date": exec_date, "ticker": ticker, "shares": -shares_to_sell,
                    "price": price_data.price, "cost": cost, "side": "sell",
                })

        # 6. Update prices for holdings and record
        for ticker in holdings:
            if ticker in prices and prices[ticker].price:
                holdings[ticker]["last_price"] = prices[ticker].price

        pv = _portfolio_value(holdings, cash)
        equity_curve.append({"date": rebal_date, "value": pv})

        snapshot = []
        for ticker, h in holdings.items():
            val = h["shares"] * h["last_price"] if h["last_price"] else 0
            snapshot.append({"ticker": ticker, "weight": val / pv if pv > 0 else 0, "value": val})
        holdings_history.append({"date": rebal_date, "holdings": snapshot})

    # Compute metrics
    metrics = compute_metrics(equity_curve, all_trades)

    return BacktestResult(
        config=config,
        equity_curve=equity_curve,
        trades=all_trades,
        holdings_history=holdings_history,
        metrics=metrics,
        rebalance_dates=rebalance_dates,
    )


def _portfolio_value(holdings: dict[str, dict], cash: float) -> float:
    total = cash
    for h in holdings.values():
        if h.get("last_price"):
            total += h["shares"] * h["last_price"]
    return total
