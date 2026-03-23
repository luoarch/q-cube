"""Tests for quality flag assignment."""

from q3_fundamentals_engine.research.quality_flags import QualityFlag, assign_quality_flag
from q3_fundamentals_engine.research.source_tiers import SourceTier


class TestAssignQualityFlag:
    def test_all_b_with_value(self) -> None:
        assert assign_quality_flag(0.05, SourceTier.B, SourceTier.B, SourceTier.B) == QualityFlag.B

    def test_all_a_with_value(self) -> None:
        assert assign_quality_flag(0.05, SourceTier.A, SourceTier.A, SourceTier.A) == QualityFlag.A

    def test_npy_null(self) -> None:
        assert assign_quality_flag(None, SourceTier.B, SourceTier.B, SourceTier.D) == QualityFlag.D

    def test_any_tier_d(self) -> None:
        assert assign_quality_flag(0.05, SourceTier.D, SourceTier.B, SourceTier.D) == QualityFlag.D
        assert assign_quality_flag(0.05, SourceTier.B, SourceTier.D, SourceTier.D) == QualityFlag.D

    def test_any_tier_c(self) -> None:
        assert assign_quality_flag(0.05, SourceTier.C, SourceTier.B, SourceTier.C) == QualityFlag.C
        assert assign_quality_flag(0.05, SourceTier.B, SourceTier.C, SourceTier.C) == QualityFlag.C

    def test_mixed_a_b(self) -> None:
        assert assign_quality_flag(0.05, SourceTier.A, SourceTier.B, SourceTier.B) == QualityFlag.B

    def test_negative_npy(self) -> None:
        assert assign_quality_flag(-0.10, SourceTier.B, SourceTier.B, SourceTier.B) == QualityFlag.B

    def test_zero_npy(self) -> None:
        assert assign_quality_flag(0.0, SourceTier.B, SourceTier.B, SourceTier.B) == QualityFlag.B
