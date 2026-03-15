"""B2 Input Assembly — completes Plan2FeatureDraft into Plan2FeatureInput.

Applies defaults and derivations for dimensions F1 left as None.
Each default/derivation gets its own provenance entry so the system
never silently masks uncertainty as a "normal" score.

Default rules (from spec-02):
  - exportFxLeverage: directCommodityExposure * 0.6 (DERIVED)
  - usdDebtExposure: 30 (DEFAULT)
  - usdImportDependence: 20 (DEFAULT)
  - usdRevenueOffset: if directCommodity >= 70 → directCommodity * 0.7 (DERIVED), else 10 (DEFAULT)
"""

from __future__ import annotations

from q3_quant_engine.thesis.types import (
    Plan2FeatureDraft,
    Plan2FeatureInput,
    ScoreConfidence,
    ScoreProvenance,
    ScoreSourceType,
)

INPUT_ASSEMBLY_VERSION = "b2-assembly-v1"

# Default values per spec-02
_DEFAULT_USD_DEBT_EXPOSURE = 30.0
_DEFAULT_USD_IMPORT_DEPENDENCE = 20.0
_DEFAULT_USD_REVENUE_OFFSET = 10.0
_EXPORT_FX_DERIVATION_FACTOR = 0.6
_USD_REVENUE_DERIVATION_FACTOR = 0.7
_USD_REVENUE_DERIVATION_THRESHOLD = 70.0


def _default_provenance(as_of_date: str) -> ScoreProvenance:
    return ScoreProvenance(
        source_type=ScoreSourceType.DEFAULT,
        source_version=INPUT_ASSEMBLY_VERSION,
        assessed_at=as_of_date,
        assessed_by=None,
        confidence=ScoreConfidence.LOW,
        evidence_ref=None,
    )


def _derived_provenance(as_of_date: str, derivation: str) -> ScoreProvenance:
    return ScoreProvenance(
        source_type=ScoreSourceType.DERIVED,
        source_version=INPUT_ASSEMBLY_VERSION,
        assessed_at=as_of_date,
        assessed_by=None,
        confidence=ScoreConfidence.LOW,
        evidence_ref=derivation,
    )


def complete_feature_input(
    draft: Plan2FeatureDraft,
    as_of_date: str,
) -> Plan2FeatureInput:
    """Complete a partial Plan2FeatureDraft into a full Plan2FeatureInput.

    Fills missing dimension scores with defaults or derivations per spec-02.
    Preserves provenance from F1 for dimensions already computed, adds
    provenance for each default/derivation applied by B2.
    """
    provenance = dict(draft.provenance)

    # --- Opportunity dimensions ---

    direct = draft.direct_commodity_exposure_score
    if direct is None:
        direct = 0.0
        provenance["direct_commodity_exposure"] = _default_provenance(as_of_date)

    indirect = draft.indirect_commodity_exposure_score
    if indirect is None:
        indirect = 0.0
        provenance["indirect_commodity_exposure"] = _default_provenance(as_of_date)

    # exportFxLeverage: derive from directCommodity if missing
    export_fx = draft.export_fx_leverage_score
    if export_fx is None:
        export_fx = direct * _EXPORT_FX_DERIVATION_FACTOR
        provenance["export_fx_leverage"] = _derived_provenance(
            as_of_date,
            f"derived: direct_commodity_exposure({direct}) * {_EXPORT_FX_DERIVATION_FACTOR}",
        )

    # --- Fragility dimensions ---

    refinancing = draft.refinancing_stress_score
    if refinancing is None:
        refinancing = 50.0  # neutral fallback
        provenance["refinancing_stress"] = _default_provenance(as_of_date)

    # usdDebtExposure: default 30 (moderado)
    usd_debt = draft.usd_debt_exposure_score
    if usd_debt is None:
        usd_debt = _DEFAULT_USD_DEBT_EXPOSURE
        provenance["usd_debt_exposure"] = _default_provenance(as_of_date)

    # usdImportDependence: default 20 (conservador)
    usd_import = draft.usd_import_dependence_score
    if usd_import is None:
        usd_import = _DEFAULT_USD_IMPORT_DEPENDENCE
        provenance["usd_import_dependence"] = _default_provenance(as_of_date)

    # usdRevenueOffset: derive from directCommodity if high, else default 10
    usd_revenue = draft.usd_revenue_offset_score
    if usd_revenue is None:
        if direct >= _USD_REVENUE_DERIVATION_THRESHOLD:
            usd_revenue = direct * _USD_REVENUE_DERIVATION_FACTOR
            provenance["usd_revenue_offset"] = _derived_provenance(
                as_of_date,
                f"derived: direct_commodity_exposure({direct}) * {_USD_REVENUE_DERIVATION_FACTOR}",
            )
        else:
            usd_revenue = _DEFAULT_USD_REVENUE_OFFSET
            provenance["usd_revenue_offset"] = _default_provenance(as_of_date)

    return Plan2FeatureInput(
        issuer_id=draft.issuer_id,
        ticker=draft.ticker,
        passed_core_screening=draft.passed_core_screening,
        has_valid_financials=draft.has_valid_financials,
        interest_coverage=draft.interest_coverage,
        debt_to_ebitda=draft.debt_to_ebitda,
        core_rank_percentile=draft.core_rank_percentile,
        direct_commodity_exposure_score=direct,
        indirect_commodity_exposure_score=indirect,
        export_fx_leverage_score=export_fx,
        refinancing_stress_score=refinancing,
        usd_debt_exposure_score=usd_debt,
        usd_import_dependence_score=usd_import,
        usd_revenue_offset_score=usd_revenue,
        provenance=provenance,
    )
