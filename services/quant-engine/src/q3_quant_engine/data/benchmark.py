"""Benchmark data layer — fetch index price series for relative metrics."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_shared_models.entities import MarketSnapshot, Security


IBOV_TICKER = "^BVSP"


def fetch_benchmark_curve(
    session: Session,
    ticker: str,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch benchmark equity curve from market_snapshots.

    Returns [{date, value}, ...] sorted by date, matching the format
    expected by compute_metrics(benchmark_curve=...).

    For index data, we look for a security with the given ticker.
    Falls back to empty list if no data found.
    """
    # Find the security for this ticker
    security = session.execute(
        select(Security).where(Security.ticker == ticker)
    ).scalar_one_or_none()

    if security is None:
        return []

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    snapshots = session.execute(
        select(MarketSnapshot)
        .where(
            MarketSnapshot.security_id == security.id,
            MarketSnapshot.fetched_at >= start_dt,
            MarketSnapshot.fetched_at <= end_dt,
        )
        .order_by(MarketSnapshot.fetched_at)
    ).scalars().all()

    if not snapshots:
        return []

    curve = []
    for snap in snapshots:
        if snap.price is not None:
            d = snap.fetched_at.date() if hasattr(snap.fetched_at, 'date') else snap.fetched_at
            curve.append({"date": d, "value": float(snap.price)})

    return curve


def build_benchmark_curve_for_rebalances(
    session: Session,
    ticker: str,
    rebalance_dates: list[date],
    max_staleness_days: int = 7,
) -> list[dict]:
    """Build benchmark curve aligned with backtest rebalance dates.

    For each rebalance date, find the closest benchmark price within
    the staleness window. This ensures the benchmark curve has the
    same number of points as the equity curve.
    """
    security = session.execute(
        select(Security).where(Security.ticker == ticker)
    ).scalar_one_or_none()

    if security is None:
        return []

    curve = []
    for rebal_date in rebalance_dates:
        end_dt = datetime.combine(rebal_date, datetime.max.time(), tzinfo=timezone.utc)
        start_dt = end_dt - timedelta(days=max_staleness_days)

        snap = session.execute(
            select(MarketSnapshot)
            .where(
                MarketSnapshot.security_id == security.id,
                MarketSnapshot.fetched_at >= start_dt,
                MarketSnapshot.fetched_at <= end_dt,
            )
            .order_by(MarketSnapshot.fetched_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if snap and snap.price is not None:
            curve.append({"date": rebal_date, "value": float(snap.price)})

    return curve
