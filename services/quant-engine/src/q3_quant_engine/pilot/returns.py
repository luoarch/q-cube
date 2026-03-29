"""Pure forward return functions — no DB, no HTTP, no side effects.

Formula: return = (price_tn - price_t0) / price_t0
Business days: weekday-only (Mon-Fri), no B3 holiday calendar.
"""

from __future__ import annotations

from datetime import date, timedelta

VALID_HORIZONS = {"1d": 1, "5d": 5, "21d": 21}


def calculate_forward_return(
    price_t0: float | None,
    price_tn: float | None,
) -> float | None:
    """Calculate forward return: (price_tn - price_t0) / price_t0.

    Returns None if either price is None or price_t0 is zero.
    Pure arithmetic — no domain validation of negative prices.
    B3 prices are always positive, but this function is math-only.
    """
    if price_t0 is None or price_tn is None:
        return None
    if price_t0 == 0:
        return None
    return (price_tn - price_t0) / price_t0


def resolve_horizon_date(snapshot_date: date, horizon: str) -> date:
    """Advance snapshot_date by N weekdays (Mon-Fri).

    No B3 holiday calendar — weekday-only simplification for test harness.

    Args:
        snapshot_date: Starting date.
        horizon: '1d', '5d', or '21d'.

    Raises:
        ValueError: If horizon is not in VALID_HORIZONS.
    """
    if horizon not in VALID_HORIZONS:
        msg = f"Invalid horizon '{horizon}'. Valid: {sorted(VALID_HORIZONS)}"
        raise ValueError(msg)

    days_remaining = VALID_HORIZONS[horizon]
    current = snapshot_date

    while days_remaining > 0:
        current += timedelta(days=1)
        # Monday=0 ... Friday=4, Saturday=5, Sunday=6
        if current.weekday() < 5:
            days_remaining -= 1

    return current
