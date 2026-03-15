"""Coverage and evidence quality assessment for Plan 2 scores.

Derives per-issuer quality flags from provenance metadata so the system
never presents false precision. Every score's origin is classified and
aggregated into a single EvidenceQuality flag.

Rules:
  HIGH_EVIDENCE   — majority (>50%) of dimensions are QUANTITATIVE or RUBRIC_MANUAL
  MIXED_EVIDENCE  — at least one QUANTITATIVE or RUBRIC_MANUAL, but <=50%
  LOW_EVIDENCE    — zero QUANTITATIVE or RUBRIC_MANUAL (all proxy/derived/default)
"""

from __future__ import annotations

from q3_quant_engine.thesis.types import (
    CoverageSummary,
    EvidenceQuality,
    ScoreProvenance,
    ScoreSourceType,
)


def compute_coverage_summary(
    provenance: dict[str, ScoreProvenance],
) -> CoverageSummary:
    """Compute coverage breakdown and evidence quality from provenance map.

    Args:
        provenance: dimension_key → ScoreProvenance (typically 7 entries from Plan2FeatureInput).

    Returns:
        CoverageSummary with counts, percentages, and aggregate evidence quality.
    """
    total = len(provenance)
    if total == 0:
        return CoverageSummary(
            total_dimensions=0,
            quantitative_count=0,
            sector_proxy_count=0,
            rubric_manual_count=0,
            derived_count=0,
            default_count=0,
            quantitative_pct=0.0,
            sector_proxy_pct=0.0,
            rubric_manual_pct=0.0,
            derived_pct=0.0,
            default_pct=0.0,
            evidence_quality=EvidenceQuality.LOW_EVIDENCE,
        )

    counts = {
        ScoreSourceType.QUANTITATIVE: 0,
        ScoreSourceType.SECTOR_PROXY: 0,
        ScoreSourceType.RUBRIC_MANUAL: 0,
        ScoreSourceType.DERIVED: 0,
        ScoreSourceType.DEFAULT: 0,
    }

    for prov in provenance.values():
        counts[prov.source_type] = counts.get(prov.source_type, 0) + 1

    hard_evidence = counts[ScoreSourceType.QUANTITATIVE] + counts[ScoreSourceType.RUBRIC_MANUAL]
    hard_pct = hard_evidence / total

    if hard_pct > 0.5:
        quality = EvidenceQuality.HIGH_EVIDENCE
    elif hard_evidence > 0:
        quality = EvidenceQuality.MIXED_EVIDENCE
    else:
        quality = EvidenceQuality.LOW_EVIDENCE

    return CoverageSummary(
        total_dimensions=total,
        quantitative_count=counts[ScoreSourceType.QUANTITATIVE],
        sector_proxy_count=counts[ScoreSourceType.SECTOR_PROXY],
        rubric_manual_count=counts[ScoreSourceType.RUBRIC_MANUAL],
        derived_count=counts[ScoreSourceType.DERIVED],
        default_count=counts[ScoreSourceType.DEFAULT],
        quantitative_pct=round(counts[ScoreSourceType.QUANTITATIVE] / total * 100, 1),
        sector_proxy_pct=round(counts[ScoreSourceType.SECTOR_PROXY] / total * 100, 1),
        rubric_manual_pct=round(counts[ScoreSourceType.RUBRIC_MANUAL] / total * 100, 1),
        derived_pct=round(counts[ScoreSourceType.DERIVED] / total * 100, 1),
        default_pct=round(counts[ScoreSourceType.DEFAULT] / total * 100, 1),
        evidence_quality=quality,
    )
