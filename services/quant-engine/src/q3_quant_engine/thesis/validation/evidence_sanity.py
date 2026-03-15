"""Evidence-weight sanity — checks if top-ranked issuers have adequate evidence.

If the top of the ranking is dominated by LOW_EVIDENCE scores, the ranking
is presenting false precision. This check flags that condition.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from q3_quant_engine.thesis.coverage import compute_coverage_summary
from q3_quant_engine.thesis.types import (
    EvidenceQuality,
    Plan2RankingSnapshot,
)


@dataclass
class EvidenceSanityResult:
    """Result of evidence-weight sanity check."""

    top_n: int
    high_evidence_count: int
    mixed_evidence_count: int
    low_evidence_count: int
    low_evidence_pct: float
    is_acceptable: bool
    details: list[dict[str, str]] = field(default_factory=list)


# Alert if more than this % of top-N has LOW_EVIDENCE
_MAX_LOW_EVIDENCE_PCT_TOP10 = 0.70  # 70%
_MAX_LOW_EVIDENCE_PCT_TOP20 = 0.80  # 80%


def check_evidence_sanity(
    snapshots: list[Plan2RankingSnapshot],
    top_n: int = 10,
    max_low_evidence_pct: float | None = None,
) -> EvidenceSanityResult:
    """Check if top-ranked issuers have acceptable evidence quality.

    Args:
        snapshots: Ranked snapshots (should already be sorted by thesis_rank).
        top_n: How many top issuers to check.
        max_low_evidence_pct: Override threshold. Default depends on top_n.

    Returns:
        EvidenceSanityResult with acceptability flag.
    """
    if max_low_evidence_pct is None:
        max_low_evidence_pct = _MAX_LOW_EVIDENCE_PCT_TOP10 if top_n <= 10 else _MAX_LOW_EVIDENCE_PCT_TOP20

    # Get top N eligible issuers
    eligible_ranked = [
        s for s in snapshots
        if s.eligible and s.thesis_rank is not None
    ]
    eligible_ranked.sort(key=lambda s: s.thesis_rank or 999)
    top = eligible_ranked[:top_n]

    high = 0
    mixed = 0
    low = 0
    details: list[dict[str, str]] = []

    for s in top:
        coverage = compute_coverage_summary(s.provenance)
        quality = coverage.evidence_quality

        if quality == EvidenceQuality.HIGH_EVIDENCE:
            high += 1
        elif quality == EvidenceQuality.MIXED_EVIDENCE:
            mixed += 1
        else:
            low += 1

        details.append({
            "ticker": s.ticker,
            "thesis_rank": str(s.thesis_rank),
            "bucket": s.bucket.value if s.bucket else "None",
            "evidence_quality": quality.value,
            "quantitative_pct": f"{coverage.quantitative_pct}%",
            "default_pct": f"{coverage.default_pct}%",
        })

    total = len(top)
    low_pct = low / total if total > 0 else 0.0

    return EvidenceSanityResult(
        top_n=top_n,
        high_evidence_count=high,
        mixed_evidence_count=mixed,
        low_evidence_count=low,
        low_evidence_pct=round(low_pct, 3),
        is_acceptable=low_pct <= max_low_evidence_pct,
        details=details,
    )
