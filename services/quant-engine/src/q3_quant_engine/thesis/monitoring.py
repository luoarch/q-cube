"""Plan 2 monitoring — compute governance metrics from persisted run data.

Pure computation functions. No DB access — caller provides data.

Four monitoring blocks:
1. Run monitoring summary (coverage, provenance, confidence, evidence quality)
2. Run drift (bucket changes, top-N changes, fragility deltas)
3. Rubric aging (stale rubrics by dimension/issuer)
4. Review queue (prioritized list for human attention)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from q3_quant_engine.thesis.coverage import compute_coverage_summary
from q3_quant_engine.thesis.types import (
    EvidenceQuality,
    ScoreProvenance,
)


# ---------------------------------------------------------------------------
# Block 1: Run Monitoring Summary
# ---------------------------------------------------------------------------

@dataclass
class DimensionCoverage:
    """Coverage breakdown for a single dimension across all eligible issuers."""
    dimension_key: str
    total_issuers: int
    source_type_counts: dict[str, int]
    confidence_counts: dict[str, int]
    non_default_pct: float


@dataclass
class RunMonitoringSummary:
    """Aggregate monitoring data for a single Plan 2 run."""
    run_id: str
    total_eligible: int
    # per-dimension coverage
    dimension_coverage: list[DimensionCoverage]
    # provenance mix (aggregate across all dimensions and issuers)
    provenance_mix: dict[str, int]
    provenance_mix_pct: dict[str, float]
    # confidence distribution (aggregate)
    confidence_distribution: dict[str, int]
    # evidence quality distribution
    evidence_quality_distribution: dict[str, int]
    evidence_quality_pct: dict[str, float]


def compute_run_monitoring(
    run_id: str,
    provenance_by_issuer: dict[str, dict[str, ScoreProvenance]],
) -> RunMonitoringSummary:
    """Compute monitoring summary for a run.

    Args:
        run_id: The plan2 run ID.
        provenance_by_issuer: issuer_id -> {dimension_key -> ScoreProvenance}.
    """
    total = len(provenance_by_issuer)

    # Aggregate provenance across all dimensions
    all_source_counts: dict[str, int] = {}
    all_confidence_counts: dict[str, int] = {}
    dim_data: dict[str, dict[str, list]] = {}  # dim -> {"sources": [...], "confidences": [...]}

    for _issuer_id, dims in provenance_by_issuer.items():
        for dim_key, prov in dims.items():
            src = prov.source_type if isinstance(prov.source_type, str) else prov.source_type.value
            conf = prov.confidence if isinstance(prov.confidence, str) else prov.confidence.value

            all_source_counts[src] = all_source_counts.get(src, 0) + 1
            all_confidence_counts[conf] = all_confidence_counts.get(conf, 0) + 1

            if dim_key not in dim_data:
                dim_data[dim_key] = {"sources": [], "confidences": []}
            dim_data[dim_key]["sources"].append(src)
            dim_data[dim_key]["confidences"].append(conf)

    # Per-dimension coverage
    dimension_coverage = []
    for dim_key in sorted(dim_data.keys()):
        sources = dim_data[dim_key]["sources"]
        confidences = dim_data[dim_key]["confidences"]
        src_counts: dict[str, int] = {}
        conf_counts: dict[str, int] = {}
        for s in sources:
            src_counts[s] = src_counts.get(s, 0) + 1
        for c in confidences:
            conf_counts[c] = conf_counts.get(c, 0) + 1

        non_default = sum(v for k, v in src_counts.items() if k != "DEFAULT")
        dim_total = len(sources)

        dimension_coverage.append(DimensionCoverage(
            dimension_key=dim_key,
            total_issuers=dim_total,
            source_type_counts=src_counts,
            confidence_counts=conf_counts,
            non_default_pct=round(non_default / dim_total * 100, 1) if dim_total > 0 else 0.0,
        ))

    # Provenance mix percentages
    total_entries = sum(all_source_counts.values())
    provenance_mix_pct = {
        k: round(v / total_entries * 100, 1) if total_entries > 0 else 0.0
        for k, v in all_source_counts.items()
    }

    # Evidence quality distribution (per-issuer)
    evidence_dist: dict[str, int] = {
        EvidenceQuality.HIGH_EVIDENCE.value: 0,
        EvidenceQuality.MIXED_EVIDENCE.value: 0,
        EvidenceQuality.LOW_EVIDENCE.value: 0,
    }
    for _issuer_id, dims in provenance_by_issuer.items():
        coverage = compute_coverage_summary(dims)
        evidence_dist[coverage.evidence_quality.value] = (
            evidence_dist.get(coverage.evidence_quality.value, 0) + 1
        )

    evidence_pct = {
        k: round(v / total * 100, 1) if total > 0 else 0.0
        for k, v in evidence_dist.items()
    }

    return RunMonitoringSummary(
        run_id=run_id,
        total_eligible=total,
        dimension_coverage=dimension_coverage,
        provenance_mix=all_source_counts,
        provenance_mix_pct=provenance_mix_pct,
        confidence_distribution=all_confidence_counts,
        evidence_quality_distribution=evidence_dist,
        evidence_quality_pct=evidence_pct,
    )


# ---------------------------------------------------------------------------
# Block 2: Run Drift
# ---------------------------------------------------------------------------

@dataclass
class IssuerDrift:
    """Per-issuer change between two runs."""
    issuer_id: str
    ticker: str
    old_bucket: str | None
    new_bucket: str | None
    bucket_changed: bool
    old_fragility: float | None
    new_fragility: float | None
    fragility_delta: float | None
    old_rank: int | None
    new_rank: int | None
    rank_delta: int | None


@dataclass
class RunDrift:
    """Drift summary between two Plan 2 runs."""
    current_run_id: str
    previous_run_id: str
    bucket_changes: int
    bucket_change_details: list[IssuerDrift]
    top10_entered: list[str]  # tickers that entered top 10
    top10_exited: list[str]   # tickers that exited top 10
    top20_entered: list[str]
    top20_exited: list[str]
    new_issuers: list[str]    # in current but not previous
    dropped_issuers: list[str]  # in previous but not current
    fragility_delta_avg: float | None
    fragility_delta_max: float | None
    fragility_delta_min: float | None


@dataclass
class IssuerRunData:
    """Minimal per-issuer data for drift comparison."""
    issuer_id: str
    ticker: str
    bucket: str | None
    fragility: float | None
    rank: int | None


def compute_run_drift(
    current_run_id: str,
    previous_run_id: str,
    current_data: list[IssuerRunData],
    previous_data: list[IssuerRunData],
) -> RunDrift:
    """Compute drift between two runs."""
    curr_by_id = {d.issuer_id: d for d in current_data}
    prev_by_id = {d.issuer_id: d for d in previous_data}

    all_ids = set(curr_by_id.keys()) | set(prev_by_id.keys())

    bucket_changes = 0
    bucket_details: list[IssuerDrift] = []
    fragility_deltas: list[float] = []

    new_issuers = []
    dropped_issuers = []

    for iid in all_ids:
        curr = curr_by_id.get(iid)
        prev = prev_by_id.get(iid)

        if curr and not prev:
            new_issuers.append(curr.ticker)
            continue
        if prev and not curr:
            dropped_issuers.append(prev.ticker)
            continue

        assert curr is not None and prev is not None
        bucket_changed = curr.bucket != prev.bucket
        if bucket_changed:
            bucket_changes += 1

        frag_delta = None
        if curr.fragility is not None and prev.fragility is not None:
            frag_delta = round(curr.fragility - prev.fragility, 2)
            fragility_deltas.append(frag_delta)

        rank_delta = None
        if curr.rank is not None and prev.rank is not None:
            rank_delta = curr.rank - prev.rank

        if bucket_changed or (frag_delta is not None and abs(frag_delta) >= 1.0):
            bucket_details.append(IssuerDrift(
                issuer_id=iid,
                ticker=curr.ticker,
                old_bucket=prev.bucket,
                new_bucket=curr.bucket,
                bucket_changed=bucket_changed,
                old_fragility=prev.fragility,
                new_fragility=curr.fragility,
                fragility_delta=frag_delta,
                old_rank=prev.rank,
                new_rank=curr.rank,
                rank_delta=rank_delta,
            ))

    # Top-N analysis
    curr_ranked = sorted(
        [d for d in current_data if d.rank is not None],
        key=lambda d: d.rank,  # type: ignore[arg-type]
    )
    prev_ranked = sorted(
        [d for d in previous_data if d.rank is not None],
        key=lambda d: d.rank,  # type: ignore[arg-type]
    )

    curr_top10 = {d.ticker for d in curr_ranked[:10]}
    prev_top10 = {d.ticker for d in prev_ranked[:10]}
    curr_top20 = {d.ticker for d in curr_ranked[:20]}
    prev_top20 = {d.ticker for d in prev_ranked[:20]}

    return RunDrift(
        current_run_id=current_run_id,
        previous_run_id=previous_run_id,
        bucket_changes=bucket_changes,
        bucket_change_details=sorted(bucket_details, key=lambda d: abs(d.fragility_delta or 0), reverse=True),
        top10_entered=sorted(curr_top10 - prev_top10),
        top10_exited=sorted(prev_top10 - curr_top10),
        top20_entered=sorted(curr_top20 - prev_top20),
        top20_exited=sorted(prev_top20 - curr_top20),
        new_issuers=sorted(new_issuers),
        dropped_issuers=sorted(dropped_issuers),
        fragility_delta_avg=round(sum(fragility_deltas) / len(fragility_deltas), 2) if fragility_deltas else None,
        fragility_delta_max=round(max(fragility_deltas), 2) if fragility_deltas else None,
        fragility_delta_min=round(min(fragility_deltas), 2) if fragility_deltas else None,
    )


# ---------------------------------------------------------------------------
# Block 3: Rubric Aging
# ---------------------------------------------------------------------------

@dataclass
class StaleRubric:
    """A single rubric that is older than the staleness threshold."""
    issuer_id: str
    ticker: str
    dimension_key: str
    source_type: str
    confidence: str
    assessed_at: date | None
    age_days: int | None
    assessed_by: str | None


@dataclass
class RubricAgingReport:
    """Rubric aging summary."""
    stale_threshold_days: int
    total_active_rubrics: int
    stale_count: int
    stale_pct: float
    stale_by_dimension: dict[str, int]
    stale_rubrics: list[StaleRubric]


@dataclass
class RubricRecord:
    """Minimal rubric data for aging/review queue computation."""
    issuer_id: str
    ticker: str
    dimension_key: str
    source_type: str
    confidence: str
    assessed_at: date | None
    assessed_by: str | None
    score: float


def compute_rubric_aging(
    rubrics: list[RubricRecord],
    stale_days: int = 30,
    as_of: date | None = None,
) -> RubricAgingReport:
    """Compute rubric aging report."""
    if as_of is None:
        as_of = date.today()

    stale_threshold = as_of - timedelta(days=stale_days)
    stale: list[StaleRubric] = []
    stale_by_dim: dict[str, int] = {}

    for r in rubrics:
        age = None
        is_stale = False

        if r.assessed_at is not None:
            age = (as_of - r.assessed_at).days
            if r.assessed_at < stale_threshold:
                is_stale = True
        else:
            # No assessed_at = treat as stale
            is_stale = True

        if is_stale:
            stale.append(StaleRubric(
                issuer_id=r.issuer_id,
                ticker=r.ticker,
                dimension_key=r.dimension_key,
                source_type=r.source_type,
                confidence=r.confidence,
                assessed_at=r.assessed_at,
                age_days=age,
                assessed_by=r.assessed_by,
            ))
            stale_by_dim[r.dimension_key] = stale_by_dim.get(r.dimension_key, 0) + 1

    total = len(rubrics)
    stale_count = len(stale)

    return RubricAgingReport(
        stale_threshold_days=stale_days,
        total_active_rubrics=total,
        stale_count=stale_count,
        stale_pct=round(stale_count / total * 100, 1) if total > 0 else 0.0,
        stale_by_dimension=stale_by_dim,
        stale_rubrics=sorted(stale, key=lambda s: s.age_days or 9999, reverse=True),
    )


# ---------------------------------------------------------------------------
# Block 4: Review Queue
# ---------------------------------------------------------------------------

@dataclass
class ReviewItem:
    """A single item in the review queue."""
    issuer_id: str
    ticker: str
    dimension_key: str
    priority: str  # "HIGH" | "MEDIUM" | "LOW"
    reasons: list[str]
    current_score: float
    source_type: str
    confidence: str
    age_days: int | None


@dataclass
class ReviewQueue:
    """Prioritized review queue."""
    total_items: int
    high_priority: int
    medium_priority: int
    low_priority: int
    items: list[ReviewItem]


def compute_review_queue(
    rubrics: list[RubricRecord],
    drift: RunDrift | None = None,
    stale_days: int = 30,
    as_of: date | None = None,
) -> ReviewQueue:
    """Compute prioritized review queue.

    Priority rules:
    - HIGH: low confidence + stale, or bucket changed in drift
    - MEDIUM: low confidence only, or stale only, or material fragility delta
    - LOW: AI_ASSISTED needing periodic human review
    """
    if as_of is None:
        as_of = date.today()

    stale_threshold = as_of - timedelta(days=stale_days)

    # Build set of issuers with bucket changes from drift
    bucket_changed_issuers: set[str] = set()
    material_fragility_issuers: set[str] = set()
    if drift:
        for d in drift.bucket_change_details:
            if d.bucket_changed:
                bucket_changed_issuers.add(d.issuer_id)
            if d.fragility_delta is not None and abs(d.fragility_delta) >= 5.0:
                material_fragility_issuers.add(d.issuer_id)

    items: list[ReviewItem] = []

    for r in rubrics:
        reasons: list[str] = []
        is_low_conf = r.confidence == "low"
        is_stale = False
        age = None

        if r.assessed_at is not None:
            age = (as_of - r.assessed_at).days
            if r.assessed_at < stale_threshold:
                is_stale = True
                reasons.append(f"stale ({age}d)")
        else:
            is_stale = True
            reasons.append("no assessed_at")

        if is_low_conf:
            reasons.append("low confidence")

        if r.issuer_id in bucket_changed_issuers:
            reasons.append("bucket changed")

        if r.issuer_id in material_fragility_issuers:
            reasons.append("material fragility delta")

        if r.source_type == "AI_ASSISTED":
            reasons.append("AI_ASSISTED (needs periodic human review)")

        if not reasons:
            continue

        # Priority assignment
        if (is_low_conf and is_stale) or r.issuer_id in bucket_changed_issuers:
            priority = "HIGH"
        elif is_low_conf or is_stale or r.issuer_id in material_fragility_issuers:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        items.append(ReviewItem(
            issuer_id=r.issuer_id,
            ticker=r.ticker,
            dimension_key=r.dimension_key,
            priority=priority,
            reasons=reasons,
            current_score=r.score,
            source_type=r.source_type,
            confidence=r.confidence,
            age_days=age,
        ))

    # Sort: HIGH first, then MEDIUM, then LOW; within priority, by age desc
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items.sort(key=lambda i: (priority_order.get(i.priority, 3), -(i.age_days or 0)))

    high = sum(1 for i in items if i.priority == "HIGH")
    med = sum(1 for i in items if i.priority == "MEDIUM")
    low = sum(1 for i in items if i.priority == "LOW")

    return ReviewQueue(
        total_items=len(items),
        high_priority=high,
        medium_priority=med,
        low_priority=low,
        items=items,
    )
