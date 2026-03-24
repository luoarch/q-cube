"""Ticker Decision Engine — type definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


class BlockReason(str, Enum):
    LOW_YIELD = "LOW_YIELD"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    DATA_MISSING = "DATA_MISSING"
    MARGINAL = "MARGINAL"


class ValuationLabel(str, Enum):
    CHEAP = "CHEAP"
    FAIR = "FAIR"
    EXPENSIVE = "EXPENSIVE"


class ConfidenceLabel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DriverType(str, Enum):
    STRUCTURAL = "structural"
    CYCLICAL = "cyclical"
    HISTORICAL = "historical"


@dataclass
class QualityBlock:
    score: float
    label: str  # HIGH / MEDIUM / LOW
    earnings_quality: float | None = None
    safety: float | None = None
    operating_consistency: float | None = None
    capital_discipline: float | None = None


@dataclass
class ValuationBlock:
    label: ValuationLabel | None = None
    valuation_method: str = "earnings_yield_normalization_proxy"
    earnings_yield: float | None = None
    ey_universe_percentile: float | None = None
    ey_sector_percentile: float | None = None
    ey_sector_median: float | None = None
    sector_issuers_count: int = 0
    sector_fallback: bool = False
    implied_price: float | None = None
    implied_value_range: tuple[float, float] | None = None
    current_price: float | None = None
    upside: float | None = None


@dataclass
class ImpliedYieldBlock:
    earnings_yield: float | None = None
    net_payout_yield: float | None = None
    total_yield: float | None = None
    label: str = ""
    meets_minimum: bool = False
    minimum_threshold: float = 0.0


@dataclass
class Driver:
    signal: str
    source: str
    driver_type: DriverType
    magnitude: str = ""
    value: float | str | None = None
    valuation_impact: float | None = None  # estimated bps impact on yield


@dataclass
class Risk:
    signal: str
    source: str
    critical: bool = False


@dataclass
class ConfidenceBlock:
    score: float
    label: ConfidenceLabel
    data_completeness: float
    evidence_quality: str
    penalties: list[str] = field(default_factory=list)


@dataclass
class DecisionBlock:
    status: DecisionStatus
    block_reason: BlockReason | None = None
    reason: str = ""
    governance_note: str = ""


@dataclass
class ProvenanceBlock:
    ranking_source: str = ""
    refiner_run_id: str | None = None
    thesis_run_id: str | None = None
    metrics_reference_date: str = ""
    snapshot_date: str = ""
    universe_policy: str = "v1"


@dataclass
class TickerDecision:
    ticker: str
    name: str
    sector: str
    generated_at: str

    quality: QualityBlock | None
    valuation: ValuationBlock | None
    implied_yield: ImpliedYieldBlock | None
    drivers: list[Driver]
    risks: list[Risk]
    confidence: ConfidenceBlock
    decision: DecisionBlock
    provenance: ProvenanceBlock
