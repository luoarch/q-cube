"""Tests for TTM quarter extraction and standalone deaccumulation."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from q3_shared_models.entities import FilingType, ScopeType
from q3_fundamentals_engine.metrics.ttm import (
    QuarterValue,
    quarter_end_dates,
    snap_to_quarter_end,
    _previous_quarter_end,
    _subtract_quarter,
    extract_standalone_quarters,
)


# ---------------------------------------------------------------------------
# quarter_end_dates
# ---------------------------------------------------------------------------


class TestQuarterEndDates:
    def test_from_dec(self) -> None:
        result = quarter_end_dates(date(2025, 12, 31))
        assert result == [
            date(2025, 3, 31),
            date(2025, 6, 30),
            date(2025, 9, 30),
            date(2025, 12, 31),
        ]

    def test_from_sep(self) -> None:
        result = quarter_end_dates(date(2025, 9, 30))
        assert result == [
            date(2024, 12, 31),
            date(2025, 3, 31),
            date(2025, 6, 30),
            date(2025, 9, 30),
        ]

    def test_from_jun(self) -> None:
        result = quarter_end_dates(date(2025, 6, 30))
        assert result == [
            date(2024, 9, 30),
            date(2024, 12, 31),
            date(2025, 3, 31),
            date(2025, 6, 30),
        ]

    def test_from_mar(self) -> None:
        result = quarter_end_dates(date(2025, 3, 31))
        assert result == [
            date(2024, 6, 30),
            date(2024, 9, 30),
            date(2024, 12, 31),
            date(2025, 3, 31),
        ]

    def test_crosses_year_boundary(self) -> None:
        result = quarter_end_dates(date(2025, 3, 31))
        assert result[0].year == 2024
        assert result[-1].year == 2025


# ---------------------------------------------------------------------------
# _subtract_quarter
# ---------------------------------------------------------------------------


class TestSubtractQuarter:
    def test_dec_to_sep(self) -> None:
        assert _subtract_quarter(date(2025, 12, 31)) == date(2025, 9, 30)

    def test_sep_to_jun(self) -> None:
        assert _subtract_quarter(date(2025, 9, 30)) == date(2025, 6, 30)

    def test_jun_to_mar(self) -> None:
        assert _subtract_quarter(date(2025, 6, 30)) == date(2025, 3, 31)

    def test_mar_to_dec_prev_year(self) -> None:
        assert _subtract_quarter(date(2025, 3, 31)) == date(2024, 12, 31)

    def test_non_quarter_end_snaps_first(self) -> None:
        """Non-quarter-end dates (e.g., November FYE) should snap before subtracting."""
        # 2024-11-30 snaps to 2024-12-31, then subtract → 2024-09-30
        assert _subtract_quarter(date(2024, 11, 30)) == date(2024, 9, 30)

    def test_august_snaps_to_sep(self) -> None:
        # 2024-08-31 snaps to 2024-09-30, then subtract → 2024-06-30
        assert _subtract_quarter(date(2024, 8, 31)) == date(2024, 6, 30)


# ---------------------------------------------------------------------------
# snap_to_quarter_end
# ---------------------------------------------------------------------------


class TestSnapToQuarterEnd:
    def test_already_quarter_end(self) -> None:
        assert snap_to_quarter_end(date(2024, 12, 31)) == date(2024, 12, 31)

    def test_november_to_december(self) -> None:
        assert snap_to_quarter_end(date(2024, 11, 30)) == date(2024, 12, 31)

    def test_august_to_september(self) -> None:
        assert snap_to_quarter_end(date(2024, 8, 31)) == date(2024, 9, 30)

    def test_may_to_june(self) -> None:
        assert snap_to_quarter_end(date(2024, 5, 31)) == date(2024, 6, 30)

    def test_february_to_march(self) -> None:
        assert snap_to_quarter_end(date(2024, 2, 28)) == date(2024, 3, 31)

    def test_january(self) -> None:
        assert snap_to_quarter_end(date(2024, 1, 15)) == date(2024, 3, 31)

    def test_quarter_end_dates_with_non_standard_fye(self) -> None:
        """quarter_end_dates should snap non-quarter-end input."""
        result = quarter_end_dates(date(2024, 11, 30))
        assert result == [
            date(2024, 3, 31),
            date(2024, 6, 30),
            date(2024, 9, 30),
            date(2024, 12, 31),
        ]


# ---------------------------------------------------------------------------
# _previous_quarter_end
# ---------------------------------------------------------------------------


class TestPreviousQuarterEnd:
    def test_q1_returns_none(self) -> None:
        assert _previous_quarter_end(date(2025, 3, 31)) is None

    def test_q2_returns_q1(self) -> None:
        assert _previous_quarter_end(date(2025, 6, 30)) == date(2025, 3, 31)

    def test_q3_returns_q2(self) -> None:
        assert _previous_quarter_end(date(2025, 9, 30)) == date(2025, 6, 30)

    def test_q4_returns_q3(self) -> None:
        assert _previous_quarter_end(date(2025, 12, 31)) == date(2025, 9, 30)


# ---------------------------------------------------------------------------
# extract_standalone_quarters
# ---------------------------------------------------------------------------

_FID = uuid.uuid4()
_FID2 = uuid.uuid4()
_FID3 = uuid.uuid4()
_FID4 = uuid.uuid4()


def _qv(ref: date, scope: ScopeType, ytd: float, fid: uuid.UUID = _FID) -> QuarterValue:
    return QuarterValue(
        reference_date=ref,
        scope=scope,
        ytd_value=ytd,
        filing_id=fid,
        filing_type=FilingType.ITR,
    )


class TestExtractStandaloneQuarters:
    """Test YTD → standalone deaccumulation logic."""

    def test_full_year_q1_to_q4(self) -> None:
        """Q1 standalone, Q2-Q4 deaccumulated from YTD."""
        dates = quarter_end_dates(date(2025, 12, 31))
        # YTD values: Q1=100, Q2=250, Q3=400, Q4_annual=600
        ytd_data = {
            date(2025, 3, 31): [_qv(date(2025, 3, 31), ScopeType.con, -100.0, _FID)],
            date(2025, 6, 30): [_qv(date(2025, 6, 30), ScopeType.con, -250.0, _FID2)],
            date(2025, 9, 30): [_qv(date(2025, 9, 30), ScopeType.con, -400.0, _FID3)],
            date(2025, 12, 31): [_qv(date(2025, 12, 31), ScopeType.con, -600.0, _FID4)],
        }
        result = extract_standalone_quarters(ytd_data, dates)
        assert result is not None
        assert len(result) == 4
        # Expected standalones: Q1=-100, Q2=-150, Q3=-150, Q4=-200
        assert result[0] == (date(2025, 3, 31), -100.0, _FID)
        assert result[1] == (date(2025, 6, 30), -150.0, _FID2)
        assert result[2] == (date(2025, 9, 30), -150.0, _FID3)
        assert result[3] == (date(2025, 12, 31), -200.0, _FID4)

    def test_cross_year_ttm(self) -> None:
        """TTM ending at Q3 2025 spans Q4 2024 through Q3 2025."""
        dates = quarter_end_dates(date(2025, 9, 30))
        # dates = [2024-12-31, 2025-03-31, 2025-06-30, 2025-09-30]
        # For Q4 2024: need YTD_annual(2024-12-31) and YTD_Q3(2024-09-30)
        ytd_data = {
            date(2024, 9, 30): [_qv(date(2024, 9, 30), ScopeType.con, -300.0)],
            date(2024, 12, 31): [_qv(date(2024, 12, 31), ScopeType.con, -500.0)],
            date(2025, 3, 31): [_qv(date(2025, 3, 31), ScopeType.con, -80.0)],
            date(2025, 6, 30): [_qv(date(2025, 6, 30), ScopeType.con, -180.0)],
            date(2025, 9, 30): [_qv(date(2025, 9, 30), ScopeType.con, -320.0)],
        }
        result = extract_standalone_quarters(ytd_data, dates)
        assert result is not None
        # Q4_2024 = -500 - (-300) = -200
        # Q1_2025 = -80 (standalone)
        # Q2_2025 = -180 - (-80) = -100
        # Q3_2025 = -320 - (-180) = -140
        assert result[0][1] == pytest.approx(-200.0)
        assert result[1][1] == pytest.approx(-80.0)
        assert result[2][1] == pytest.approx(-100.0)
        assert result[3][1] == pytest.approx(-140.0)

    def test_missing_quarter_returns_none(self) -> None:
        """If any quarter is missing, return None."""
        dates = quarter_end_dates(date(2025, 12, 31))
        ytd_data = {
            date(2025, 3, 31): [_qv(date(2025, 3, 31), ScopeType.con, -100.0)],
            # Q2 missing
            date(2025, 9, 30): [_qv(date(2025, 9, 30), ScopeType.con, -400.0)],
            date(2025, 12, 31): [_qv(date(2025, 12, 31), ScopeType.con, -600.0)],
        }
        assert extract_standalone_quarters(ytd_data, dates) is None

    def test_missing_prev_quarter_for_deaccum_returns_none(self) -> None:
        """If the prior quarter needed for deaccumulation is missing, return None."""
        dates = quarter_end_dates(date(2025, 9, 30))
        # Need 2024-09-30 for Q4 deaccum, but it's missing
        ytd_data = {
            date(2024, 12, 31): [_qv(date(2024, 12, 31), ScopeType.con, -500.0)],
            date(2025, 3, 31): [_qv(date(2025, 3, 31), ScopeType.con, -80.0)],
            date(2025, 6, 30): [_qv(date(2025, 6, 30), ScopeType.con, -180.0)],
            date(2025, 9, 30): [_qv(date(2025, 9, 30), ScopeType.con, -320.0)],
        }
        assert extract_standalone_quarters(ytd_data, dates) is None

    def test_scope_fallback_ind(self) -> None:
        """Falls back to ind scope when con is not available."""
        dates = quarter_end_dates(date(2025, 12, 31))
        ytd_data = {
            date(2025, 3, 31): [_qv(date(2025, 3, 31), ScopeType.ind, -100.0)],
            date(2025, 6, 30): [_qv(date(2025, 6, 30), ScopeType.ind, -250.0)],
            date(2025, 9, 30): [_qv(date(2025, 9, 30), ScopeType.ind, -400.0)],
            date(2025, 12, 31): [_qv(date(2025, 12, 31), ScopeType.ind, -600.0)],
        }
        result = extract_standalone_quarters(ytd_data, dates, preferred_scope=ScopeType.con)
        assert result is not None
        # Should use ind scope since con is not available
        assert result[0][1] == -100.0

    def test_no_scope_mixing(self) -> None:
        """All 4 quarters must use the same scope. Mixed con+ind returns None."""
        dates = quarter_end_dates(date(2025, 12, 31))
        ytd_data = {
            date(2025, 3, 31): [_qv(date(2025, 3, 31), ScopeType.con, -100.0)],
            date(2025, 6, 30): [_qv(date(2025, 6, 30), ScopeType.ind, -250.0)],  # only ind
            date(2025, 9, 30): [_qv(date(2025, 9, 30), ScopeType.con, -400.0)],
            date(2025, 12, 31): [_qv(date(2025, 12, 31), ScopeType.con, -600.0)],
        }
        # con fails at Q2 (only ind), ind fails at Q1 (only con)
        assert extract_standalone_quarters(ytd_data, dates) is None

    def test_both_scopes_available_prefers_con(self) -> None:
        """When both scopes exist, prefer con."""
        dates = quarter_end_dates(date(2025, 12, 31))
        ytd_data = {
            date(2025, 3, 31): [
                _qv(date(2025, 3, 31), ScopeType.con, -100.0),
                _qv(date(2025, 3, 31), ScopeType.ind, -90.0),
            ],
            date(2025, 6, 30): [
                _qv(date(2025, 6, 30), ScopeType.con, -250.0),
                _qv(date(2025, 6, 30), ScopeType.ind, -220.0),
            ],
            date(2025, 9, 30): [
                _qv(date(2025, 9, 30), ScopeType.con, -400.0),
                _qv(date(2025, 9, 30), ScopeType.ind, -350.0),
            ],
            date(2025, 12, 31): [
                _qv(date(2025, 12, 31), ScopeType.con, -600.0),
                _qv(date(2025, 12, 31), ScopeType.ind, -500.0),
            ],
        }
        result = extract_standalone_quarters(ytd_data, dates)
        assert result is not None
        # Should use con: Q1=-100
        assert result[0][1] == -100.0

    def test_empty_ytd_data_returns_none(self) -> None:
        dates = quarter_end_dates(date(2025, 12, 31))
        assert extract_standalone_quarters({}, dates) is None

    def test_zero_value_quarter(self) -> None:
        """Zero is a valid value (company paid no dividends in that quarter)."""
        dates = quarter_end_dates(date(2025, 12, 31))
        ytd_data = {
            date(2025, 3, 31): [_qv(date(2025, 3, 31), ScopeType.con, 0.0)],
            date(2025, 6, 30): [_qv(date(2025, 6, 30), ScopeType.con, -100.0)],
            date(2025, 9, 30): [_qv(date(2025, 9, 30), ScopeType.con, -100.0)],
            date(2025, 12, 31): [_qv(date(2025, 12, 31), ScopeType.con, -200.0)],
        }
        result = extract_standalone_quarters(ytd_data, dates)
        assert result is not None
        assert result[0][1] == 0.0      # Q1 = 0
        assert result[1][1] == -100.0   # Q2 = -100 - 0
        assert result[2][1] == 0.0      # Q3 = -100 - (-100)
        assert result[3][1] == -100.0   # Q4 = -200 - (-100)
