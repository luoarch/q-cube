"""Build Plan2FeatureDraft from issuer data — automatic extraction only.

F1 produces a *partial* draft with only the dimensions it can compute:
  - directCommodityExposureScore (SECTOR_PROXY)
  - indirectCommodityExposureScore (SECTOR_PROXY)
  - refinancingStressScore (QUANTITATIVE)

Other dimensions (exportFx, usdDebt, usdImport, usdRevenue) remain None.
B2 later fills them with defaults/derivations/rubrics.
"""

from __future__ import annotations

from dataclasses import dataclass

from q3_quant_engine.thesis.features.refinancing_stress import (
    compute_refinancing_stress_score,
)
from q3_quant_engine.thesis.features.sector_proxy import (
    lookup_direct_commodity_proxy,
    lookup_indirect_commodity_proxy,
)
from q3_quant_engine.thesis.types import Plan2FeatureDraft, ScoreProvenance


@dataclass
class IssuerFeatureData:
    """Input data for feature extraction. Assembled by the caller from DB."""

    issuer_id: str
    ticker: str
    sector: str | None
    subsector: str | None
    # eligibility inputs
    passed_core_screening: bool
    has_valid_financials: bool
    interest_coverage: float | None
    debt_to_ebitda: float | None
    core_rank_percentile: float
    # refinancing stress inputs (from statement_lines)
    short_term_debt: float | None
    long_term_debt: float | None


def build_feature_draft(
    data: IssuerFeatureData,
    as_of_date: str,
) -> Plan2FeatureDraft:
    """Build a partial Plan2FeatureDraft from available data.

    Computes only automatic dimensions:
      - directCommodityExposureScore (sector proxy)
      - indirectCommodityExposureScore (sector proxy)
      - refinancingStressScore (quantitative)

    All other dimension scores are left as None.
    """
    provenance: dict[str, ScoreProvenance] = {}

    # Sector proxy dimensions
    direct_score, direct_prov = lookup_direct_commodity_proxy(
        data.sector, data.subsector, as_of_date,
    )
    provenance["direct_commodity_exposure"] = direct_prov

    indirect_score, indirect_prov = lookup_indirect_commodity_proxy(
        data.sector, data.subsector, as_of_date,
    )
    provenance["indirect_commodity_exposure"] = indirect_prov

    # Refinancing stress (quantitative)
    refin_score, refin_prov, _detail = compute_refinancing_stress_score(
        short_term_debt=data.short_term_debt,
        long_term_debt=data.long_term_debt,
        debt_to_ebitda=data.debt_to_ebitda,
        interest_coverage=data.interest_coverage,
        as_of_date=as_of_date,
    )
    provenance["refinancing_stress"] = refin_prov

    return Plan2FeatureDraft(
        issuer_id=data.issuer_id,
        ticker=data.ticker,
        passed_core_screening=data.passed_core_screening,
        has_valid_financials=data.has_valid_financials,
        interest_coverage=data.interest_coverage,
        debt_to_ebitda=data.debt_to_ebitda,
        core_rank_percentile=data.core_rank_percentile,
        # F1 automatic dimensions
        direct_commodity_exposure_score=direct_score,
        indirect_commodity_exposure_score=indirect_score,
        refinancing_stress_score=refin_score,
        # Dimensions left for B2
        export_fx_leverage_score=None,
        usd_debt_exposure_score=None,
        usd_import_dependence_score=None,
        usd_revenue_offset_score=None,
        provenance=provenance,
    )
