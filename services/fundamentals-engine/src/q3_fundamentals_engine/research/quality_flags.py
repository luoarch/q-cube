"""Quality flag assignment for NPY research panel rows.

Quality levels:
    A = All components tier A/B, no NULL, no C
    B = All components tier B, no C, no NULL (same as A for current data)
    C = Any component has tier C
    D = NPY is NULL or any critical component missing
"""

from __future__ import annotations

from enum import Enum

from q3_fundamentals_engine.research.source_tiers import SourceTier


class QualityFlag(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


def assign_quality_flag(
    npy_value: float | None,
    dy_tier: SourceTier,
    nby_tier: SourceTier,
    npy_tier: SourceTier,
) -> QualityFlag:
    """Assign a quality flag to a research panel row.

    Rules (evaluated in order):
        D: NPY is NULL, or any tier is D
        C: any tier is C
        A: all tiers are A
        B: otherwise (mix of A/B)
    """
    if npy_value is None:
        return QualityFlag.D

    if any(t == SourceTier.D for t in (dy_tier, nby_tier, npy_tier)):
        return QualityFlag.D

    if any(t == SourceTier.C for t in (dy_tier, nby_tier, npy_tier)):
        return QualityFlag.C

    if all(t == SourceTier.A for t in (dy_tier, nby_tier, npy_tier)):
        return QualityFlag.A

    return QualityFlag.B
