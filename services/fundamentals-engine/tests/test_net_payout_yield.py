"""Tests for Net Payout Yield composition.

NPY = DY + NBY. Pure composition — no DB, no recomputation.
Tests focus on: identity, NULL propagation, negative NPY, inputs_snapshot completeness.
"""

from __future__ import annotations

import uuid

from q3_fundamentals_engine.metrics.base import MetricResult
from q3_fundamentals_engine.metrics.net_payout_yield import compute_net_payout_yield


def _dy_result(value: float, filing_ids: list[str] | None = None) -> MetricResult:
    return MetricResult(
        metric_code="dividend_yield",
        value=value,
        formula_version=1,
        inputs_snapshot={"dividend_yield": value, "market_cap": 10_000_000_000.0},
        source_filing_ids=filing_ids or [str(uuid.uuid4())],
    )


def _nby_result(value: float) -> MetricResult:
    return MetricResult(
        metric_code="net_buyback_yield",
        value=value,
        formula_version=1,
        inputs_snapshot={"net_buyback_yield": value, "shares_t": 1e9, "shares_t4": 1.05e9},
        source_filing_ids=[],
    )


class TestComputeNetPayoutYield:
    def test_basic_composition(self) -> None:
        """NPY = DY + NBY for normal case."""
        dy = _dy_result(0.052)  # 5.2% dividend yield
        nby = _nby_result(0.03)  # 3% net buyback
        result = compute_net_payout_yield(dy, nby)

        assert result is not None
        assert result.metric_code == "net_payout_yield"
        assert abs(result.value - 0.082) < 1e-9
        assert result.formula_version == 1

    def test_identity_dy_plus_nby(self) -> None:
        """Identity: NPY == DY + NBY exactly (within floating point)."""
        for dy_val, nby_val in [
            (0.10, 0.05),
            (0.001, 0.0001),
            (0.25, -0.10),
            (0.0, 0.0),
            (0.052, 0.0),
            (0.0, 0.03),
        ]:
            dy = _dy_result(dy_val)
            nby = _nby_result(nby_val)
            result = compute_net_payout_yield(dy, nby)
            assert result is not None
            assert abs(result.value - (dy_val + nby_val)) < 1e-12, (
                f"Identity failed: DY={dy_val} + NBY={nby_val} != NPY={result.value}"
            )

    def test_npy_negative_dilution_exceeds_payout(self) -> None:
        """NPY can be negative when dilution exceeds dividend payout."""
        dy = _dy_result(0.03)  # 3% DY
        nby = _nby_result(-0.10)  # -10% dilution
        result = compute_net_payout_yield(dy, nby)

        assert result is not None
        assert result.value < 0, "NPY should be negative when dilution > payout"
        assert abs(result.value - (-0.07)) < 1e-9

    def test_null_when_dy_is_none(self) -> None:
        """Returns None when DY result is None."""
        nby = _nby_result(0.03)
        result = compute_net_payout_yield(None, nby)
        assert result is None

    def test_null_when_nby_is_none(self) -> None:
        """Returns None when NBY result is None."""
        dy = _dy_result(0.052)
        result = compute_net_payout_yield(dy, None)
        assert result is None

    def test_null_when_both_none(self) -> None:
        """Returns None when both components are None."""
        result = compute_net_payout_yield(None, None)
        assert result is None

    def test_null_when_dy_value_is_none(self) -> None:
        """Returns None when DY result exists but value is None."""
        dy = MetricResult(
            metric_code="dividend_yield",
            value=None,
            formula_version=1,
            inputs_snapshot={},
            source_filing_ids=[],
        )
        nby = _nby_result(0.03)
        result = compute_net_payout_yield(dy, nby)
        assert result is None

    def test_null_when_nby_value_is_none(self) -> None:
        """Returns None when NBY result exists but value is None."""
        dy = _dy_result(0.052)
        nby = MetricResult(
            metric_code="net_buyback_yield",
            value=None,
            formula_version=1,
            inputs_snapshot={},
            source_filing_ids=[],
        )
        result = compute_net_payout_yield(dy, nby)
        assert result is None

    def test_inputs_snapshot_complete(self) -> None:
        """inputs_snapshot contains both component values and the result."""
        dy = _dy_result(0.052)
        nby = _nby_result(0.03)
        result = compute_net_payout_yield(dy, nby)

        assert result is not None
        snap = result.inputs_snapshot
        assert "dividend_yield" in snap
        assert "net_buyback_yield" in snap
        assert "net_payout_yield" in snap
        assert snap["dividend_yield"] == 0.052
        assert snap["net_buyback_yield"] == 0.03
        assert abs(snap["net_payout_yield"] - 0.082) < 1e-9

    def test_filing_ids_from_dy(self) -> None:
        """Source filing IDs come from DY (NBY has none — market data only)."""
        fids = [str(uuid.uuid4()), str(uuid.uuid4())]
        dy = _dy_result(0.05, filing_ids=fids)
        nby = _nby_result(0.02)
        result = compute_net_payout_yield(dy, nby)

        assert result is not None
        assert result.source_filing_ids == fids

    def test_zero_dy_zero_nby(self) -> None:
        """NPY = 0 when both DY and NBY are zero."""
        dy = _dy_result(0.0)
        nby = _nby_result(0.0)
        result = compute_net_payout_yield(dy, nby)

        assert result is not None
        assert result.value == 0.0
