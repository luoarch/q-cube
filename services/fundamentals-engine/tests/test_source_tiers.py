"""Tests for source tier derivation rules."""

from q3_fundamentals_engine.research.source_tiers import (
    SourceTier,
    derive_dy_tiers,
    derive_nby_tiers,
    derive_npy_tier,
    worst_tier,
)


class TestWorstTier:
    def test_same_tier(self) -> None:
        assert worst_tier(SourceTier.A, SourceTier.A) == SourceTier.A

    def test_a_and_b(self) -> None:
        assert worst_tier(SourceTier.A, SourceTier.B) == SourceTier.B

    def test_b_and_c(self) -> None:
        assert worst_tier(SourceTier.B, SourceTier.C) == SourceTier.C

    def test_any_d(self) -> None:
        assert worst_tier(SourceTier.A, SourceTier.D) == SourceTier.D
        assert worst_tier(SourceTier.D, SourceTier.B) == SourceTier.D

    def test_three_tiers(self) -> None:
        assert worst_tier(SourceTier.A, SourceTier.B, SourceTier.C) == SourceTier.C


class TestDeriveDyTiers:
    def test_normal_dy(self) -> None:
        inputs = {"market_cap": 1_000_000.0, "dividend_yield": 0.05}
        filings = ["filing-1", "filing-2"]
        dy_tier, mcap_tier = derive_dy_tiers(inputs, filings)
        assert dy_tier == SourceTier.B  # worst(A, B)
        assert mcap_tier == SourceTier.B

    def test_no_filings(self) -> None:
        inputs = {"market_cap": 1_000_000.0, "dividend_yield": 0.05}
        dy_tier, mcap_tier = derive_dy_tiers(inputs, [])
        assert dy_tier == SourceTier.D  # no filing backing
        assert mcap_tier == SourceTier.B

    def test_no_market_cap(self) -> None:
        inputs = {"dividend_yield": 0.05}
        dy_tier, mcap_tier = derive_dy_tiers(inputs, ["f1"])
        assert dy_tier == SourceTier.D  # no market_cap
        assert mcap_tier == SourceTier.D

    def test_none_inputs(self) -> None:
        dy_tier, mcap_tier = derive_dy_tiers(None, None)
        assert dy_tier == SourceTier.D
        assert mcap_tier == SourceTier.D

    def test_zero_market_cap(self) -> None:
        inputs = {"market_cap": 0.0}
        dy_tier, mcap_tier = derive_dy_tiers(inputs, ["f1"])
        assert mcap_tier == SourceTier.D


class TestDeriveNbyTiers:
    def test_normal_nby(self) -> None:
        inputs = {"shares_t": 100_000.0, "shares_t4": 95_000.0}
        nby_tier, shares_tier = derive_nby_tiers(inputs)
        assert nby_tier == SourceTier.B
        assert shares_tier == SourceTier.B

    def test_missing_shares_t(self) -> None:
        inputs = {"shares_t4": 95_000.0}
        nby_tier, shares_tier = derive_nby_tiers(inputs)
        assert nby_tier == SourceTier.D

    def test_missing_shares_t4(self) -> None:
        inputs = {"shares_t": 100_000.0}
        nby_tier, shares_tier = derive_nby_tiers(inputs)
        assert nby_tier == SourceTier.D

    def test_none_inputs(self) -> None:
        nby_tier, shares_tier = derive_nby_tiers(None)
        assert nby_tier == SourceTier.D
        assert shares_tier == SourceTier.D


class TestDeriveNpyTier:
    def test_both_b(self) -> None:
        assert derive_npy_tier(SourceTier.B, SourceTier.B) == SourceTier.B

    def test_one_c(self) -> None:
        assert derive_npy_tier(SourceTier.B, SourceTier.C) == SourceTier.C

    def test_one_d(self) -> None:
        assert derive_npy_tier(SourceTier.B, SourceTier.D) == SourceTier.D
