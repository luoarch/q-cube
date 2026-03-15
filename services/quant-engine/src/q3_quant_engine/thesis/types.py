"""Plan 2 data types — mirrors shared-contracts/domains/thesis.ts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ThesisBucket(StrEnum):
    A_DIRECT = "A_DIRECT"
    B_INDIRECT = "B_INDIRECT"
    C_NEUTRAL = "C_NEUTRAL"
    D_FRAGILE = "D_FRAGILE"


class ScoreSourceType(StrEnum):
    QUANTITATIVE = "QUANTITATIVE"
    SECTOR_PROXY = "SECTOR_PROXY"
    RUBRIC_MANUAL = "RUBRIC_MANUAL"
    DERIVED = "DERIVED"
    DEFAULT = "DEFAULT"


class ScoreConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ScoreProvenance:
    source_type: ScoreSourceType
    source_version: str
    assessed_at: str  # ISO date
    assessed_by: str | None = None
    confidence: ScoreConfidence = ScoreConfidence.LOW
    evidence_ref: str | None = None


@dataclass
class BaseEligibility:
    eligible_for_plan2: bool
    failed_reasons: list[str] = field(default_factory=list)
    passed_core_screening: bool = False
    has_valid_financials: bool = False
    interest_coverage: float | None = None
    debt_to_ebitda: float | None = None


@dataclass
class OpportunityVector:
    direct_commodity_exposure_score: float
    indirect_commodity_exposure_score: float
    export_fx_leverage_score: float
    final_commodity_affinity_score: float


@dataclass
class FragilityVector:
    refinancing_stress_score: float
    usd_debt_exposure_score: float
    usd_import_dependence_score: float
    usd_revenue_offset_score: float
    final_dollar_fragility_score: float


@dataclass
class Plan2Explanation:
    ticker: str
    bucket: ThesisBucket
    thesis_rank_score: float
    positives: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class Plan2FeatureInput:
    """Complete feature input for scoring engine (B2 output).

    All 7 dimension scores are required (non-nullable). B2 guarantees completeness
    by filling defaults/derivations for dimensions F1 left as None.
    """

    issuer_id: str
    ticker: str
    # eligibility inputs
    passed_core_screening: bool
    has_valid_financials: bool
    interest_coverage: float | None
    debt_to_ebitda: float | None
    core_rank_percentile: float
    # opportunity (required — B2 ensures all present)
    direct_commodity_exposure_score: float
    indirect_commodity_exposure_score: float
    export_fx_leverage_score: float
    # fragility (required)
    refinancing_stress_score: float
    usd_debt_exposure_score: float
    usd_import_dependence_score: float
    usd_revenue_offset_score: float
    # provenance per dimension key
    provenance: dict[str, ScoreProvenance] = field(default_factory=dict)


@dataclass
class Plan2FeatureDraft:
    """Partial feature draft from automatic extraction (F1).

    Scores are nullable — F1 only produces dimensions it can compute automatically.
    B2 later fills defaults/derivations to produce complete Plan2FeatureInput.
    """

    issuer_id: str
    ticker: str
    # eligibility inputs
    passed_core_screening: bool
    has_valid_financials: bool
    interest_coverage: float | None
    debt_to_ebitda: float | None
    core_rank_percentile: float
    # opportunity (nullable — F1 only fills what it can compute)
    direct_commodity_exposure_score: float | None = None
    indirect_commodity_exposure_score: float | None = None
    export_fx_leverage_score: float | None = None
    # fragility (nullable)
    refinancing_stress_score: float | None = None
    usd_debt_exposure_score: float | None = None
    usd_import_dependence_score: float | None = None
    usd_revenue_offset_score: float | None = None
    # provenance per dimension key
    provenance: dict[str, ScoreProvenance] = field(default_factory=dict)


class EvidenceQuality(StrEnum):
    """Aggregate evidence quality flag for a scored issuer."""

    HIGH_EVIDENCE = "HIGH_EVIDENCE"
    MIXED_EVIDENCE = "MIXED_EVIDENCE"
    LOW_EVIDENCE = "LOW_EVIDENCE"


@dataclass
class CoverageSummary:
    """Per-issuer coverage breakdown of how scores were produced."""

    total_dimensions: int
    quantitative_count: int
    sector_proxy_count: int
    rubric_manual_count: int
    derived_count: int
    default_count: int
    quantitative_pct: float
    sector_proxy_pct: float
    rubric_manual_pct: float
    derived_pct: float
    default_pct: float
    evidence_quality: EvidenceQuality


@dataclass
class Plan2RankingSnapshot:
    issuer_id: str
    ticker: str
    company_name: str
    sector: str | None
    eligible: bool
    eligibility: BaseEligibility
    opportunity_vector: OpportunityVector | None = None
    fragility_vector: FragilityVector | None = None
    bucket: ThesisBucket | None = None
    thesis_rank_score: float | None = None
    thesis_rank: int | None = None
    base_core_score: float = 0.0
    explanation: Plan2Explanation | None = None
    provenance: dict[str, ScoreProvenance] = field(default_factory=dict)
