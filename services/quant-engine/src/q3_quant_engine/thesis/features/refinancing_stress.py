"""Refinancing stress score — quantitative computation from financial data.

Formula (spec-02):
    shortTermDebtRatioNorm = clamp(short_term_debt / (short_term_debt + long_term_debt) * 100, 0, 100)
    leverageComponent = clamp(debt_to_ebitda / 6.0 * 100, 0, 100)
    coverageComponent = clamp((1 - interest_coverage / 10.0) * 100, 0, 100)

    refinancingStressScore = 0.35 * shortTermDebtRatioNorm
                           + 0.35 * leverageComponent
                           + 0.30 * coverageComponent

Fallback: if any input is missing, score = 50.0 (neutral) with INCOMPLETE provenance.
"""

from __future__ import annotations

from dataclasses import dataclass

from q3_quant_engine.thesis.types import ScoreConfidence, ScoreProvenance, ScoreSourceType

REFINANCING_STRESS_VERSION = "quant-v1"

# Component weights
_W_SHORT_TERM_DEBT_RATIO = 0.35
_W_LEVERAGE = 0.35
_W_COVERAGE = 0.30

# Normalization ceilings
_LEVERAGE_CEILING = 6.0  # debt_to_ebitda of 6x maps to 100
_COVERAGE_CEILING = 10.0  # interest_coverage of 10x maps to 0 (excellent)

NEUTRAL_FALLBACK_SCORE = 50.0


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class RefinancingStressResult:
    score: float
    short_term_debt_ratio_norm: float | None
    leverage_component: float | None
    coverage_component: float | None
    is_complete: bool


def compute_refinancing_stress_score(
    short_term_debt: float | None,
    long_term_debt: float | None,
    debt_to_ebitda: float | None,
    interest_coverage: float | None,
    as_of_date: str,
) -> tuple[float, ScoreProvenance, RefinancingStressResult]:
    """Compute refinancing stress score from financial data.

    Returns (score, provenance, detailed_result).
    If any input is None, returns neutral fallback (50.0) with low confidence.
    """
    all_available = (
        short_term_debt is not None
        and long_term_debt is not None
        and debt_to_ebitda is not None
        and interest_coverage is not None
    )

    if not all_available:
        provenance = ScoreProvenance(
            source_type=ScoreSourceType.QUANTITATIVE,
            source_version=REFINANCING_STRESS_VERSION,
            assessed_at=as_of_date,
            assessed_by=None,
            confidence=ScoreConfidence.LOW,
            evidence_ref="INCOMPLETE — missing financial inputs",
        )
        result = RefinancingStressResult(
            score=NEUTRAL_FALLBACK_SCORE,
            short_term_debt_ratio_norm=None,
            leverage_component=None,
            coverage_component=None,
            is_complete=False,
        )
        return NEUTRAL_FALLBACK_SCORE, provenance, result

    # All inputs guaranteed non-None from here
    assert short_term_debt is not None
    assert long_term_debt is not None
    assert debt_to_ebitda is not None
    assert interest_coverage is not None

    # Short-term debt ratio: higher = more short-term debt pressure
    total_debt = short_term_debt + long_term_debt
    if total_debt > 0:
        short_term_ratio = short_term_debt / total_debt
    else:
        short_term_ratio = 0.0
    short_term_debt_ratio_norm = _clamp(short_term_ratio * 100.0)

    # Leverage component: 6x debt/EBITDA = 100 (ceiling)
    leverage_component = _clamp(debt_to_ebitda / _LEVERAGE_CEILING * 100.0)

    # Coverage component: inverted — lower coverage = higher stress
    coverage_component = _clamp((1.0 - interest_coverage / _COVERAGE_CEILING) * 100.0)

    score = _clamp(
        _W_SHORT_TERM_DEBT_RATIO * short_term_debt_ratio_norm
        + _W_LEVERAGE * leverage_component
        + _W_COVERAGE * coverage_component
    )

    provenance = ScoreProvenance(
        source_type=ScoreSourceType.QUANTITATIVE,
        source_version=REFINANCING_STRESS_VERSION,
        assessed_at=as_of_date,
        assessed_by=None,
        confidence=ScoreConfidence.HIGH,
        evidence_ref=None,
    )

    result = RefinancingStressResult(
        score=score,
        short_term_debt_ratio_norm=short_term_debt_ratio_norm,
        leverage_component=leverage_component,
        coverage_component=coverage_component,
        is_complete=True,
    )

    return score, provenance, result
