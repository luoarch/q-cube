"""Benchmark curve generation for backtest comparison.

Fetches historical prices for a benchmark index (default: Ibovespa ^BVSP)
and builds an equity curve normalized to the backtest's initial capital.

Methodology:
- Source: yfinance adjusted close prices (price index, NOT total return)
- Returns: daily log returns from adjusted close
- Equity curve: cumulative product normalized to initial_capital
- Calendar: trading days only, non-trading days skipped
- Limitation: price-only index — does not include dividend reinvestment,
  creating a conservative bias against dividend-paying strategies
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def fetch_benchmark_curve(
    start_date: date,
    end_date: date,
    *,
    ticker: str = "^BVSP",
    initial_capital: float = 1_000_000.0,
) -> list[dict]:
    """Fetch benchmark equity curve from yfinance.

    Returns list of {date: str, value: float} matching the backtest equity curve format.
    Returns empty list if data unavailable.
    """
    import yfinance as yf

    logger.info("Fetching benchmark %s from %s to %s", ticker, start_date, end_date)

    try:
        # Fetch with buffer to ensure start_date is covered
        fetch_start = start_date - timedelta(days=7)
        df = yf.Ticker(ticker).history(
            start=fetch_start.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            interval="1d",
        )
    except Exception:
        logger.warning("Failed to fetch benchmark %s", ticker, exc_info=True)
        return []

    if df is None or df.empty:
        logger.warning("No benchmark data for %s", ticker)
        return []

    # Use Close prices
    if "Close" not in df.columns:
        logger.warning("No Close column in benchmark data")
        return []

    # Filter to actual date range
    df = df[df.index >= str(start_date)]
    df = df[df.index <= str(end_date + timedelta(days=1))]

    if len(df) < 2:
        logger.warning("Insufficient benchmark data points: %d", len(df))
        return []

    # Build equity curve: normalize to initial_capital
    close = df["Close"]
    base_price = close.iloc[0]
    if base_price <= 0:
        return []

    curve: list[dict] = []
    for idx, price in close.items():
        d = idx.date() if hasattr(idx, "date") else idx
        value = initial_capital * (price / base_price)
        curve.append({"date": d, "value": round(value, 2)})

    logger.info("Benchmark curve: %d points, start=%.0f, end=%.0f",
                len(curve), curve[0]["value"], curve[-1]["value"])
    return curve
