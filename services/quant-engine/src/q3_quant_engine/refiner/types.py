"""Refiner data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class PeriodValue:
    reference_date: date
    value: float | None


@dataclass
class ScoringBlock:
    name: str
    score: float  # 0–1
    components: dict[str, float | str | None]


@dataclass
class Flag:
    code: str
    category: str  # "red" or "strength"
    description: str


@dataclass
class DataCompleteness:
    periods_available: int  # 0–3
    metrics_available: int
    metrics_expected: int
    completeness_ratio: float
    missing_critical: list[str] = field(default_factory=list)
    proxy_used: list[str] = field(default_factory=list)


SCORE_RELIABILITY_HIGH = "high"
SCORE_RELIABILITY_MEDIUM = "medium"
SCORE_RELIABILITY_LOW = "low"
SCORE_RELIABILITY_UNAVAILABLE = "unavailable"


@dataclass
class RefinementResult:
    issuer_id: str
    ticker: str
    base_rank: int
    earnings_quality_score: float
    safety_score: float
    operating_consistency_score: float
    capital_discipline_score: float
    refinement_score: float
    adjusted_score: float
    adjusted_rank: int
    flags: dict[str, list[str]]  # {red: [...], strength: [...]}
    trend_data: dict[str, list[PeriodValue]]
    scoring_details: dict[str, object]
    data_completeness: DataCompleteness
    score_reliability: str
    issuer_classification: str
    formula_version: int = 1
    weights_version: int = 1
