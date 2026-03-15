"""Plan 2 thesis configuration — weights, thresholds, versions."""

from __future__ import annotations

# -- Thesis config version (semver) --
THESIS_CONFIG_VERSION = "1.0.0"

# -- Eligibility thresholds --
ELIGIBILITY_MIN_INTEREST_COVERAGE = 1.5
ELIGIBILITY_MAX_DEBT_TO_EBITDA = 6.0

# -- Opportunity vector weights (MVP: 3 dimensions, must sum to 1.0) --
OPPORTUNITY_WEIGHTS = {
    "direct_commodity_exposure": 0.50,
    "indirect_commodity_exposure": 0.30,
    "export_fx_leverage": 0.20,
}

# -- Fragility vector weights (MVP: 4 dimensions, accounting for inversions) --
# usd_revenue_offset is protective (higher = less fragile), so weight is applied to (100 - score)
FRAGILITY_WEIGHTS = {
    "refinancing_stress": 0.30,
    "usd_debt_exposure": 0.30,
    "usd_import_dependence": 0.20,
    "usd_revenue_offset_inverted": 0.20,  # applied to (100 - usdRevenueOffsetScore)
}

# -- Thesis rank score weights --
THESIS_RANK_WEIGHTS = {
    "commodity_affinity": 0.60,
    "fragility_inverted": 0.25,  # applied to (100 - fragilityScore)
    "base_core": 0.15,
}

# -- Bucket thresholds --
BUCKET_THRESHOLDS = {
    "a_direct_min_direct_commodity": 70.0,
    "a_direct_max_fragility": 60.0,
    "b_indirect_min_indirect_commodity": 50.0,
    "b_indirect_max_fragility": 65.0,
    "d_fragile_min_fragility": 75.0,
}
