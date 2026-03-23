"""Tests for Net Buyback Yield computation."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from q3_fundamentals_engine.metrics.net_buyback_yield import (
    compute_net_buyback_yield,
    _quarter_4_ago,
)


_ISSUER = uuid.uuid4()
_AS_OF = date(2025, 12, 31)


def _make_snapshot(shares: float | None, fetched_at: date | None = None) -> SimpleNamespace:
    """Create a mock snapshot with shares_outstanding."""
    return SimpleNamespace(
        shares_outstanding=shares,
        fetched_at=datetime(
            (fetched_at or _AS_OF).year,
            (fetched_at or _AS_OF).month,
            (fetched_at or _AS_OF).day,
            tzinfo=timezone.utc,
        ),
    )


# ---------------------------------------------------------------------------
# _quarter_4_ago
# ---------------------------------------------------------------------------


class TestQuarter4Ago:
    def test_dec_to_prev_dec(self) -> None:
        assert _quarter_4_ago(date(2025, 12, 31)) == date(2024, 12, 31)

    def test_sep_to_prev_sep(self) -> None:
        assert _quarter_4_ago(date(2025, 9, 30)) == date(2024, 9, 30)

    def test_jun_to_prev_jun(self) -> None:
        assert _quarter_4_ago(date(2025, 6, 30)) == date(2024, 6, 30)

    def test_mar_to_prev_mar(self) -> None:
        assert _quarter_4_ago(date(2025, 3, 31)) == date(2024, 3, 31)


# ---------------------------------------------------------------------------
# compute_net_buyback_yield
# ---------------------------------------------------------------------------


class TestComputeNetBuybackYield:
    def test_basic_buyback(self) -> None:
        """Shares decreased → positive NBY (buyback)."""
        snap_t = _make_snapshot(shares=900_000_000)
        snap_t4 = _make_snapshot(shares=1_000_000_000, fetched_at=date(2024, 12, 31))

        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            side_effect=[snap_t, snap_t4],
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.metric_code == "net_buyback_yield"
        # (1B - 900M) / 1B = 0.1
        assert result.value == pytest.approx(0.1)
        assert result.formula_version == 1
        assert result.inputs_snapshot["shares_t"] == 900_000_000
        assert result.inputs_snapshot["shares_t4"] == 1_000_000_000

    def test_dilution(self) -> None:
        """Shares increased → negative NBY (dilution)."""
        snap_t = _make_snapshot(shares=1_200_000_000)
        snap_t4 = _make_snapshot(shares=1_000_000_000, fetched_at=date(2024, 12, 31))

        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            side_effect=[snap_t, snap_t4],
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        # (1B - 1.2B) / 1B = -0.2
        assert result.value == pytest.approx(-0.2)

    def test_no_change(self) -> None:
        """Shares unchanged → NBY = 0."""
        snap_t = _make_snapshot(shares=1_000_000_000)
        snap_t4 = _make_snapshot(shares=1_000_000_000, fetched_at=date(2024, 12, 31))

        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            side_effect=[snap_t, snap_t4],
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.value == 0.0

    def test_no_snapshot_at_t_returns_none(self) -> None:
        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            return_value=None,
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None

    def test_no_shares_at_t_returns_none(self) -> None:
        snap_t = _make_snapshot(shares=None)
        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            return_value=snap_t,
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None

    def test_no_snapshot_at_t4_returns_none(self) -> None:
        snap_t = _make_snapshot(shares=1_000_000_000)
        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            side_effect=[snap_t, None],
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None

    def test_no_shares_at_t4_returns_none(self) -> None:
        snap_t = _make_snapshot(shares=1_000_000_000)
        snap_t4 = _make_snapshot(shares=None, fetched_at=date(2024, 12, 31))
        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            side_effect=[snap_t, snap_t4],
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None

    def test_zero_shares_at_t_returns_none(self) -> None:
        snap_t = _make_snapshot(shares=0)
        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            return_value=snap_t,
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None

    def test_zero_shares_at_t4_returns_none(self) -> None:
        snap_t = _make_snapshot(shares=1_000_000_000)
        snap_t4 = _make_snapshot(shares=0, fetched_at=date(2024, 12, 31))
        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            side_effect=[snap_t, snap_t4],
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None

    def test_provenance_dates_in_snapshot(self) -> None:
        """inputs_snapshot should include temporal anchoring info."""
        snap_t = _make_snapshot(shares=900_000_000, fetched_at=date(2025, 12, 28))
        snap_t4 = _make_snapshot(shares=1_000_000_000, fetched_at=date(2024, 12, 29))
        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            side_effect=[snap_t, snap_t4],
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.inputs_snapshot["t_date"] == "2025-12-31"
        assert result.inputs_snapshot["t4_date"] == "2024-12-31"
        assert "2025-12-28" in result.inputs_snapshot["t_snapshot_fetched_at"]
        assert "2024-12-29" in result.inputs_snapshot["t4_snapshot_fetched_at"]

    def test_source_filing_ids_empty(self) -> None:
        """NBY uses market data, not CVM filings."""
        snap_t = _make_snapshot(shares=900_000_000)
        snap_t4 = _make_snapshot(shares=1_000_000_000, fetched_at=date(2024, 12, 31))
        with patch(
            "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot",
            side_effect=[snap_t, snap_t4],
        ):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is not None
        assert result.source_filing_ids == []
