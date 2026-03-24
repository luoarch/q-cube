"""Confidence scoring with explicit penalties."""
from __future__ import annotations

from q3_quant_engine.decision.types import ConfidenceBlock, ConfidenceBreakdown, ConfidenceLabel, ValuationBlock


EVIDENCE_MAP = {
    "HIGH_EVIDENCE": 1.0,
    "MIXED_EVIDENCE": 0.6,
    "LOW_EVIDENCE": 0.3,
}


def compute_confidence(
    data_completeness: float | None,
    evidence_quality: str | None,
    valuation: ValuationBlock | None,
    driver_count: int,
    sector_fallback: bool,
    has_refiner: bool,
) -> ConfidenceBlock:
    """Compute confidence with explicit penalties for missing data."""
    base_data = data_completeness if data_completeness is not None else 0.5
    base_evidence = EVIDENCE_MAP.get(evidence_quality or "", 0.5)

    raw = base_data * 0.6 + base_evidence * 0.4

    penalties: list[str] = []
    penalty_total = 0.0
    breakdown = ConfidenceBreakdown()

    val_missing = valuation is None or valuation.earnings_yield is None
    if val_missing:
        penalties.append("valuation_null (-0.20)")
        penalty_total += 0.20
        breakdown.valuation_missing_penalty = True

    if driver_count < 3:
        penalties.append(f"drivers_insufficient ({driver_count}<3, -0.10)")
        penalty_total += 0.10
        breakdown.drivers_count_penalty = True

    if sector_fallback:
        penalties.append("sector_fallback (-0.10)")
        penalty_total += 0.10
        breakdown.sector_fallback_used = True

    if not has_refiner:
        penalties.append("refiner_missing (-0.15)")
        penalty_total += 0.15
        breakdown.missing_refiner_data = True

    if evidence_quality is None:
        breakdown.missing_thesis_data = True

    score = max(0.0, raw - penalty_total)

    if score >= 0.7:
        label = ConfidenceLabel.HIGH
    elif score >= 0.4:
        label = ConfidenceLabel.MEDIUM
    else:
        label = ConfidenceLabel.LOW

    return ConfidenceBlock(
        score=round(score, 4),
        label=label,
        data_completeness=round(base_data, 4),
        evidence_quality=evidence_quality or "UNKNOWN",
        penalties=penalties,
        breakdown=breakdown,
    )
