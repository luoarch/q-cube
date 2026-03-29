"""Spec tests for forward return pure functions (MF-RUNTIME-01A S1)."""

from __future__ import annotations

from datetime import date

import pytest

from q3_quant_engine.pilot.returns import calculate_forward_return, resolve_horizon_date


class TestCalculateForwardReturn:
    def test_positive_return(self) -> None:
        # (price_tn - price_t0) / price_t0 = (110 - 100) / 100 = 0.10
        assert calculate_forward_return(100.0, 110.0) == pytest.approx(0.10)

    def test_negative_return(self) -> None:
        # (100 - 110) / 110 = -0.0909...
        assert calculate_forward_return(110.0, 100.0) == pytest.approx(-0.090909, rel=1e-4)

    def test_zero_return(self) -> None:
        assert calculate_forward_return(100.0, 100.0) == 0.0

    def test_price_t0_zero_returns_none(self) -> None:
        assert calculate_forward_return(0.0, 100.0) is None

    def test_price_t0_none_returns_none(self) -> None:
        assert calculate_forward_return(None, 100.0) is None  # type: ignore[arg-type]

    def test_price_tn_none_returns_none(self) -> None:
        assert calculate_forward_return(100.0, None) is None  # type: ignore[arg-type]

    def test_both_none_returns_none(self) -> None:
        assert calculate_forward_return(None, None) is None  # type: ignore[arg-type]

    def test_negative_prices_still_compute(self) -> None:
        # Edge case: shouldn't happen but function is pure math
        result = calculate_forward_return(100.0, 50.0)
        assert result == pytest.approx(-0.50)

    def test_large_return(self) -> None:
        # 10x increase
        assert calculate_forward_return(10.0, 100.0) == pytest.approx(9.0)


class TestResolveHorizonDate:
    """Weekday-only (Mon-Fri), no B3 holiday calendar."""

    def test_1d_from_monday(self) -> None:
        # Monday 2026-03-23 + 1 weekday = Tuesday 2026-03-24
        assert resolve_horizon_date(date(2026, 3, 23), "1d") == date(2026, 3, 24)

    def test_1d_from_friday(self) -> None:
        # Friday 2026-03-27 + 1 weekday = Monday 2026-03-30
        assert resolve_horizon_date(date(2026, 3, 27), "1d") == date(2026, 3, 30)

    def test_5d_from_monday(self) -> None:
        # Monday + 5 weekdays = next Monday
        assert resolve_horizon_date(date(2026, 3, 23), "5d") == date(2026, 3, 30)

    def test_5d_from_wednesday(self) -> None:
        # Wednesday 2026-03-25 + 5 weekdays = Wednesday 2026-04-01
        assert resolve_horizon_date(date(2026, 3, 25), "5d") == date(2026, 4, 1)

    def test_21d_from_monday(self) -> None:
        # Monday + 21 weekdays = 4 weeks + 1 day later
        # 2026-03-23 + 21 weekdays = 2026-04-21 (Tuesday)
        result = resolve_horizon_date(date(2026, 3, 23), "21d")
        assert result == date(2026, 4, 21)

    def test_1d_from_saturday_edge_case(self) -> None:
        """Defensive edge case — snapshot_date should never be weekend in domain,
        but the pure function handles it by counting weekdays forward."""
        # Saturday 2026-03-28 + 1 weekday = Monday 2026-03-30
        assert resolve_horizon_date(date(2026, 3, 28), "1d") == date(2026, 3, 30)

    def test_1d_from_sunday_edge_case(self) -> None:
        """Defensive edge case — Sunday + 1 weekday = Monday."""
        # Sunday 2026-03-29 + 1 weekday = Monday 2026-03-30
        assert resolve_horizon_date(date(2026, 3, 29), "1d") == date(2026, 3, 30)

    def test_invalid_horizon_raises(self) -> None:
        with pytest.raises(ValueError, match="horizon"):
            resolve_horizon_date(date(2026, 3, 23), "10d")
