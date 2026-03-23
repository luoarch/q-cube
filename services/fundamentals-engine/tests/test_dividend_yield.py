"""Tests for Dividend Yield TTM computation.

These tests mock the TTM module to test the dividend yield logic in isolation.
Integration tests with real DB are deferred to validation.
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import patch

from q3_fundamentals_engine.metrics.dividend_yield import compute_dividend_yield


_ISSUER = uuid.uuid4()
_AS_OF = date(2025, 12, 31)


class TestComputeDividendYield:
    def test_basic_computation(self) -> None:
        """DY = abs(TTM distributions) / market_cap."""
        ttm_sum = -520_000_000.0  # negative (cash outflow)
        filing_ids = [str(uuid.uuid4())]
        inputs = {
            "q1_shareholder_distributions": -100_000_000.0,
            "q2_shareholder_distributions": -120_000_000.0,
            "q3_shareholder_distributions": -150_000_000.0,
            "q4_shareholder_distributions": -150_000_000.0,
            "shareholder_distributions_ttm": -520_000_000.0,
        }
        with patch(
            "q3_fundamentals_engine.metrics.dividend_yield.compute_ttm_sum",
            return_value=(ttm_sum, filing_ids, inputs),
        ):
            result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=10_000_000_000.0)

        assert result is not None
        assert result.metric_code == "dividend_yield"
        assert result.value == abs(ttm_sum) / 10_000_000_000.0
        assert result.value == 0.052  # 5.2%
        assert result.formula_version == 2
        assert result.inputs_snapshot["market_cap"] == 10_000_000_000.0
        assert result.inputs_snapshot["shareholder_distributions_ttm"] == -520_000_000.0

    def test_none_market_cap(self) -> None:
        """Returns None when market_cap is None."""
        result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=None)
        assert result is None

    def test_zero_market_cap(self) -> None:
        """Returns None when market_cap is zero."""
        result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=0.0)
        assert result is None

    def test_negative_market_cap(self) -> None:
        """Returns None when market_cap is negative."""
        result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=-1.0)
        assert result is None

    def test_incomplete_ttm_no_dfc_returns_none(self) -> None:
        """Returns None when TTM data is incomplete and no DFC coverage."""
        with patch(
            "q3_fundamentals_engine.metrics.dividend_yield.compute_ttm_sum",
            return_value=None,
        ), patch(
            "q3_fundamentals_engine.metrics.dividend_yield._has_dfc_coverage",
            return_value=False,
        ):
            result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=10_000_000_000.0)
        assert result is None

    def test_no_distributions_with_dfc_coverage_returns_zero(self) -> None:
        """DY=0 when issuer has DFC filings but no shareholder_distributions."""
        with patch(
            "q3_fundamentals_engine.metrics.dividend_yield.compute_ttm_sum",
            return_value=None,
        ), patch(
            "q3_fundamentals_engine.metrics.dividend_yield._has_dfc_coverage",
            return_value=True,
        ):
            result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=10_000_000_000.0)
        assert result is not None
        assert result.value == 0.0
        assert result.inputs_snapshot["zero_reason"] == "no_distribution_lines_in_dfc"

    def test_positive_distributions_treated_correctly(self) -> None:
        """Edge case: if distributions sum positive (anomaly), abs() still works."""
        ttm_sum = 18_000_000.0  # positive anomaly
        with patch(
            "q3_fundamentals_engine.metrics.dividend_yield.compute_ttm_sum",
            return_value=(ttm_sum, ["fid"], {"shareholder_distributions_ttm": ttm_sum}),
        ):
            result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=1_000_000_000.0)
        assert result is not None
        assert result.value == 0.018

    def test_zero_distributions(self) -> None:
        """Company with zero distributions in all 4 quarters → DY = 0."""
        with patch(
            "q3_fundamentals_engine.metrics.dividend_yield.compute_ttm_sum",
            return_value=(0.0, ["fid"], {"shareholder_distributions_ttm": 0.0}),
        ):
            result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=1_000_000_000.0)
        assert result is not None
        assert result.value == 0.0

    def test_filing_ids_propagated(self) -> None:
        """Source filing IDs from TTM computation are preserved."""
        fids = [str(uuid.uuid4()), str(uuid.uuid4())]
        with patch(
            "q3_fundamentals_engine.metrics.dividend_yield.compute_ttm_sum",
            return_value=(-100.0, fids, {"shareholder_distributions_ttm": -100.0}),
        ):
            result = compute_dividend_yield(None, _ISSUER, _AS_OF, market_cap=1000.0)
        assert result is not None
        assert result.source_filing_ids == fids
