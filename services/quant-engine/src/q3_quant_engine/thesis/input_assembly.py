"""B2 Input Assembly — completes Plan2FeatureDraft into Plan2FeatureInput.

Applies rubrics, defaults, and derivations for dimensions F1 left as None.
Priority: F1 (automatic) > RUBRIC_MANUAL > AI_ASSISTED > DERIVED > DEFAULT.

Each source gets its own provenance entry so the system
never silently masks uncertainty as a "normal" score.

Default rules (from spec-02):
  - exportFxLeverage: directCommodityExposure * 0.6 (DERIVED)
  - usdDebtExposure: 30 (DEFAULT)
  - usdImportDependence: 20 (DEFAULT)
  - usdRevenueOffset: if directCommodity >= 70 → directCommodity * 0.7 (DERIVED), else 10 (DEFAULT)
"""

from __future__ import annotations

from dataclasses import dataclass

from q3_quant_engine.thesis.types import (
    Plan2FeatureDraft,
    Plan2FeatureInput,
    ScoreConfidence,
    ScoreProvenance,
    ScoreSourceType,
)

INPUT_ASSEMBLY_VERSION = "b2-assembly-v2"

# Default values per spec-02
_DEFAULT_USD_DEBT_EXPOSURE = 30.0
_DEFAULT_USD_IMPORT_DEPENDENCE = 20.0
_DEFAULT_USD_REVENUE_OFFSET = 10.0
_EXPORT_FX_DERIVATION_FACTOR = 0.6
_USD_REVENUE_DERIVATION_FACTOR = 0.7
_USD_REVENUE_DERIVATION_THRESHOLD = 70.0


@dataclass(frozen=True)
class RubricEntry:
    """A single rubric score for one dimension of one issuer."""

    score: float
    source_type: ScoreSourceType
    source_version: str
    confidence: ScoreConfidence
    evidence_ref: str | None = None
    assessed_at: str | None = None
    assessed_by: str | None = None


# Type alias: dimension_key → RubricEntry
RubricMap = dict[str, RubricEntry]


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


def _rubric_provenance(entry: RubricEntry, as_of_date: str) -> ScoreProvenance:
    return ScoreProvenance(
        source_type=entry.source_type,
        source_version=entry.source_version,
        assessed_at=entry.assessed_at or as_of_date,
        assessed_by=entry.assessed_by,
        confidence=entry.confidence,
        evidence_ref=entry.evidence_ref,
    )


def complete_feature_input(
    draft: Plan2FeatureDraft,
    as_of_date: str,
    rubrics: RubricMap | None = None,
) -> Plan2FeatureInput:
    """Complete a partial Plan2FeatureDraft into a full Plan2FeatureInput.

    Resolution priority per dimension:
      1. F1 automatic (already in draft, not None)
      2. Rubric (RUBRIC_MANUAL or AI_ASSISTED)
      3. Derived (calculated from other dimensions)
      4. Default (hardcoded neutral value)

    Preserves provenance from F1 for dimensions already computed, adds
    provenance for each rubric/default/derivation applied by B2.
    """
    if rubrics is None:
        rubrics = {}

    provenance = dict(draft.provenance)

    # --- Opportunity dimensions ---

    direct = draft.direct_commodity_exposure_score
    if direct is None:
        rubric = rubrics.get("direct_commodity_exposure")
        if rubric is not None:
            direct = rubric.score
            provenance["direct_commodity_exposure"] = _rubric_provenance(rubric, as_of_date)
        else:
            direct = 0.0
            provenance["direct_commodity_exposure"] = _default_provenance(as_of_date)

    indirect = draft.indirect_commodity_exposure_score
    if indirect is None:
        rubric = rubrics.get("indirect_commodity_exposure")
        if rubric is not None:
            indirect = rubric.score
            provenance["indirect_commodity_exposure"] = _rubric_provenance(rubric, as_of_date)
        else:
            indirect = 0.0
            provenance["indirect_commodity_exposure"] = _default_provenance(as_of_date)

    # exportFxLeverage: rubric > derive from directCommodity
    export_fx = draft.export_fx_leverage_score
    if export_fx is None:
        rubric = rubrics.get("export_fx_leverage")
        if rubric is not None:
            export_fx = rubric.score
            provenance["export_fx_leverage"] = _rubric_provenance(rubric, as_of_date)
        else:
            export_fx = direct * _EXPORT_FX_DERIVATION_FACTOR
            provenance["export_fx_leverage"] = _derived_provenance(
                as_of_date,
                f"derived: direct_commodity_exposure({direct}) * {_EXPORT_FX_DERIVATION_FACTOR}",
            )

    # --- Fragility dimensions ---

    refinancing = draft.refinancing_stress_score
    if refinancing is None:
        rubric = rubrics.get("refinancing_stress")
        if rubric is not None:
            refinancing = rubric.score
            provenance["refinancing_stress"] = _rubric_provenance(rubric, as_of_date)
        else:
            refinancing = 50.0
            provenance["refinancing_stress"] = _default_provenance(as_of_date)

    # usdDebtExposure: rubric > default 30
    usd_debt = draft.usd_debt_exposure_score
    if usd_debt is None:
        rubric = rubrics.get("usd_debt_exposure")
        if rubric is not None:
            usd_debt = rubric.score
            provenance["usd_debt_exposure"] = _rubric_provenance(rubric, as_of_date)
        else:
            usd_debt = _DEFAULT_USD_DEBT_EXPOSURE
            provenance["usd_debt_exposure"] = _default_provenance(as_of_date)

    # usdImportDependence: rubric > default 20
    usd_import = draft.usd_import_dependence_score
    if usd_import is None:
        rubric = rubrics.get("usd_import_dependence")
        if rubric is not None:
            usd_import = rubric.score
            provenance["usd_import_dependence"] = _rubric_provenance(rubric, as_of_date)
        else:
            usd_import = _DEFAULT_USD_IMPORT_DEPENDENCE
            provenance["usd_import_dependence"] = _default_provenance(as_of_date)

    # usdRevenueOffset: rubric > derive from directCommodity if high > default 10
    usd_revenue = draft.usd_revenue_offset_score
    if usd_revenue is None:
        rubric = rubrics.get("usd_revenue_offset")
        if rubric is not None:
            usd_revenue = rubric.score
            provenance["usd_revenue_offset"] = _rubric_provenance(rubric, as_of_date)
        elif direct >= _USD_REVENUE_DERIVATION_THRESHOLD:
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
