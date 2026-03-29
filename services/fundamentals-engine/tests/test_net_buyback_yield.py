"""Tests for Net Buyback Yield v2 computation (Plan 5 S3).

v2: CVM primary source via find_cvm_shares(), Yahoo fallback via find_anchored_snapshot().
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from q3_fundamentals_engine.metrics.net_buyback_yield import (
    compute_net_buyback_yield,
    _quarter_4_ago,
    _resolve_shares,
    SPLIT_RATIO_THRESHOLD,
)


_ISSUER = uuid.uuid4()
_AS_OF = date(2025, 12, 31)
_T4 = date(2024, 12, 31)

_CVM_PATCH = "q3_fundamentals_engine.metrics.net_buyback_yield.find_cvm_shares"
_YAHOO_PATCH = "q3_fundamentals_engine.metrics.net_buyback_yield.find_anchored_snapshot"


def _make_cvm(net: float = 1_000_000, doc_type: str = "DFP") -> MagicMock:
    m = MagicMock()
    m.net_shares = net
    m.total_shares = net + 50_000
    m.treasury_shares = 50_000
    m.document_type = doc_type
    m.reference_date = _AS_OF
    m.publication_date_estimated = date(2026, 3, 31)
    return m


def _make_snapshot(shares: float | None, fetched_at: date | None = None) -> SimpleNamespace:
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
# _quarter_4_ago (unchanged from v1)
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
# CVM/CVM path — both endpoints from CVM
# ---------------------------------------------------------------------------


class TestCvmCvmPath:
    def test_both_cvm_buyback(self) -> None:
        """Both t and t-4 from CVM. Shares decreased → positive NBY."""
        cvm_t = _make_cvm(net=900_000)
        cvm_t4 = _make_cvm(net=1_000_000)

        with patch(_CVM_PATCH, side_effect=[cvm_t, cvm_t4]), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.value == pytest.approx(0.1)
        assert result.formula_version == 2
        assert result.inputs_snapshot["source_t"] == "cvm"
        assert result.inputs_snapshot["source_t4"] == "cvm"
        assert result.inputs_snapshot["t_provenance"]["document_type"] == "DFP"

    def test_both_cvm_dilution(self) -> None:
        cvm_t = _make_cvm(net=1_200_000)
        cvm_t4 = _make_cvm(net=1_000_000)

        with patch(_CVM_PATCH, side_effect=[cvm_t, cvm_t4]), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.value == pytest.approx(-0.2)
        assert result.inputs_snapshot["source_t"] == "cvm"
        assert result.inputs_snapshot["source_t4"] == "cvm"

    def test_both_cvm_no_change(self) -> None:
        cvm_t = _make_cvm(net=1_000_000)
        cvm_t4 = _make_cvm(net=1_000_000)

        with patch(_CVM_PATCH, side_effect=[cvm_t, cvm_t4]), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.value == 0.0


# ---------------------------------------------------------------------------
# Yahoo/Yahoo fallback path — backward compat
# ---------------------------------------------------------------------------


class TestYahooFallbackPath:
    def test_both_yahoo_fallback(self) -> None:
        """When CVM unavailable, falls back to Yahoo."""
        snap_t = _make_snapshot(shares=900_000_000)
        snap_t4 = _make_snapshot(shares=1_000_000_000, fetched_at=_T4)

        with patch(_CVM_PATCH, return_value=None), \
             patch(_YAHOO_PATCH, side_effect=[snap_t, snap_t4]):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.value == pytest.approx(0.1)
        assert result.formula_version == 2
        assert result.inputs_snapshot["source_t"] == "yahoo"
        assert result.inputs_snapshot["source_t4"] == "yahoo"

    def test_yahoo_no_snapshot_at_t_returns_none(self) -> None:
        with patch(_CVM_PATCH, return_value=None), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None

    def test_yahoo_no_shares_at_t_returns_none(self) -> None:
        snap_t = _make_snapshot(shares=None)
        with patch(_CVM_PATCH, return_value=None), \
             patch(_YAHOO_PATCH, return_value=snap_t):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None

    def test_yahoo_zero_shares_at_t4_returns_none(self) -> None:
        snap_t = _make_snapshot(shares=1_000_000)
        snap_t4 = _make_snapshot(shares=0, fetched_at=_T4)
        with patch(_CVM_PATCH, return_value=None), \
             patch(_YAHOO_PATCH, side_effect=[snap_t, snap_t4]):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None


# ---------------------------------------------------------------------------
# Mixed source path — CVM for one endpoint, Yahoo for the other
# ---------------------------------------------------------------------------


class TestMixedSourcePath:
    def test_cvm_t_yahoo_t4(self) -> None:
        """t from CVM, t-4 from Yahoo (CVM not available for old date)."""
        cvm_t = _make_cvm(net=900_000)
        snap_t4 = _make_snapshot(shares=1_000_000, fetched_at=_T4)

        # CVM: t→hit, t4→miss. Yahoo only called for t4 (CVM hit skips Yahoo for t).
        with patch(_CVM_PATCH, side_effect=[cvm_t, None]), \
             patch(_YAHOO_PATCH, side_effect=[snap_t4]):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.inputs_snapshot["source_t"] == "cvm"
        assert result.inputs_snapshot["source_t4"] == "yahoo"

    def test_yahoo_t_cvm_t4(self) -> None:
        """t from Yahoo, t-4 from CVM."""
        cvm_t4 = _make_cvm(net=1_000_000)
        snap_t = _make_snapshot(shares=900_000)

        # CVM: t→miss, t4→hit. Yahoo only called for t (CVM miss triggers Yahoo).
        with patch(_CVM_PATCH, side_effect=[None, cvm_t4]), \
             patch(_YAHOO_PATCH, side_effect=[snap_t]):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        assert result.inputs_snapshot["source_t"] == "yahoo"
        assert result.inputs_snapshot["source_t4"] == "cvm"


# ---------------------------------------------------------------------------
# Split detection
# ---------------------------------------------------------------------------


class TestSplitDetection:
    def test_cvm_split_detected_returns_none(self) -> None:
        """ratio > 5x → possible split → None."""
        cvm_t = _make_cvm(net=10_000_000)  # 10x more
        cvm_t4 = _make_cvm(net=1_000_000)

        with patch(_CVM_PATCH, side_effect=[cvm_t, cvm_t4]), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is None

    def test_cvm_reverse_split_detected_returns_none(self) -> None:
        """ratio < 0.2x → possible reverse split → None."""
        cvm_t = _make_cvm(net=100_000)  # 10x less
        cvm_t4 = _make_cvm(net=1_000_000)

        with patch(_CVM_PATCH, side_effect=[cvm_t, cvm_t4]), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is None

    def test_borderline_ratio_passes(self) -> None:
        """ratio = 4.9 (just under threshold) → should compute."""
        cvm_t = _make_cvm(net=4_900_000)
        cvm_t4 = _make_cvm(net=1_000_000)

        with patch(_CVM_PATCH, side_effect=[cvm_t, cvm_t4]), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None

    def test_cvm_net_shares_zero_returns_none(self) -> None:
        cvm_t = _make_cvm(net=0)
        with patch(_CVM_PATCH, side_effect=[cvm_t, None]), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)
        assert result is None


# ---------------------------------------------------------------------------
# inputs_snapshot completeness
# ---------------------------------------------------------------------------


class TestInputsSnapshot:
    def test_cvm_provenance_complete(self) -> None:
        cvm_t = _make_cvm(net=900_000, doc_type="DFP")
        cvm_t4 = _make_cvm(net=1_000_000, doc_type="ITR")

        with patch(_CVM_PATCH, side_effect=[cvm_t, cvm_t4]), \
             patch(_YAHOO_PATCH, return_value=None):
            result = compute_net_buyback_yield(None, _ISSUER, _AS_OF)

        assert result is not None
        inp = result.inputs_snapshot
        # Mandatory fields
        assert "source_t" in inp
        assert "source_t4" in inp
        assert "shares_t" in inp
        assert "shares_t4" in inp
        assert "t_date" in inp
        assert "t4_date" in inp
        assert "share_ratio_t_over_t4" in inp
        assert "net_buyback_yield" in inp
        # CVM provenance
        assert inp["t_provenance"]["document_type"] == "DFP"
        assert inp["t4_provenance"]["document_type"] == "ITR"
        assert "total_shares" in inp["t_provenance"]
        assert "treasury_shares" in inp["t_provenance"]
        assert "publication_date_estimated" in inp["t_provenance"]


# ---------------------------------------------------------------------------
# Ownership enforcement
# ---------------------------------------------------------------------------


class TestOwnershipEnforcement:
    def test_metric_does_not_import_parser_or_loader(self) -> None:
        """The metric module must NOT import parser or loader (Plan 5 §6.3)."""
        import q3_fundamentals_engine.metrics.net_buyback_yield as mod
        source = open(mod.__file__).read()
        assert "shares.parser" not in source
        assert "shares.loader" not in source
        assert "parse_composicao_capital" not in source
        assert "persist_share_counts" not in source
