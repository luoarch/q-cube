"""Plan 2 Feature Engineering — automatic feature extraction (MF-F1)."""

from q3_quant_engine.thesis.features.draft_builder import build_feature_draft
from q3_quant_engine.thesis.features.refinancing_stress import (
    compute_refinancing_stress_score,
)
from q3_quant_engine.thesis.features.sector_proxy import (
    lookup_direct_commodity_proxy,
    lookup_indirect_commodity_proxy,
)

__all__ = [
    "build_feature_draft",
    "compute_refinancing_stress_score",
    "lookup_direct_commodity_proxy",
    "lookup_indirect_commodity_proxy",
]
