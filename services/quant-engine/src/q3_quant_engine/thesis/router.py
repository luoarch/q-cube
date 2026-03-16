"""Plan 2 internal API — preview/inspection endpoints.

Exposes Plan 2 results for internal validation before public UI.
All endpoints read from persisted plan2_runs + plan2_thesis_scores.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_quant_engine.db.session import SessionLocal
from q3_shared_models.entities import Plan2RubricScore, Plan2Run, Plan2ThesisScore, Issuer, Security
from q3_quant_engine.thesis.coverage import compute_coverage_summary
from q3_quant_engine.thesis.alerts import compute_run_alerts
from q3_quant_engine.thesis.monitoring import (
    IssuerRunData,
    RubricRecord,
    compute_review_queue,
    compute_rubric_aging,
    compute_run_drift,
    compute_run_monitoring,
)
from q3_quant_engine.thesis.types import ScoreProvenance, ScoreSourceType, ScoreConfidence

router = APIRouter(prefix="/plan2", tags=["plan2"])


def _get_db() -> Session:  # type: ignore[misc]
    db = SessionLocal()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()


def _provenance_from_json(prov_json: dict[str, Any]) -> dict[str, ScoreProvenance]:
    """Reconstruct ScoreProvenance objects from persisted JSON."""
    result: dict[str, ScoreProvenance] = {}
    for key, val in prov_json.items():
        if isinstance(val, dict) and "source_type" in val:
            result[key] = ScoreProvenance(
                source_type=ScoreSourceType(val["source_type"]),
                source_version=val.get("source_version", ""),
                assessed_at=val.get("assessed_at", ""),
                assessed_by=val.get("assessed_by"),
                confidence=ScoreConfidence(val.get("confidence", "low")),
                evidence_ref=val.get("evidence_ref"),
            )
    return result


@router.get("/runs")
def list_runs(
    limit: int = 20,
    db: Session = Depends(_get_db),
) -> list[dict[str, Any]]:
    """List recent Plan 2 runs."""
    rows = db.execute(
        select(Plan2Run)
        .order_by(Plan2Run.created_at.desc())
        .limit(limit)
    ).scalars().all()

    return [
        {
            "id": str(r.id),
            "strategy_run_id": str(r.strategy_run_id),
            "tenant_id": str(r.tenant_id),
            "thesis_config_version": r.thesis_config_version,
            "pipeline_version": r.pipeline_version,
            "as_of_date": str(r.as_of_date),
            "total_eligible": r.total_eligible,
            "total_ineligible": r.total_ineligible,
            "bucket_distribution": r.bucket_distribution_json,
            "status": r.status,
            "started_at": str(r.started_at) if r.started_at else None,
            "completed_at": str(r.completed_at) if r.completed_at else None,
            "created_at": str(r.created_at),
        }
        for r in rows
    ]


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Get a specific Plan 2 run with summary stats."""
    parsed_id = uuid.UUID(run_id)
    run = db.execute(
        select(Plan2Run).where(Plan2Run.id == parsed_id)
    ).scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=404, detail="Plan 2 run not found")

    return {
        "id": str(run.id),
        "strategy_run_id": str(run.strategy_run_id),
        "tenant_id": str(run.tenant_id),
        "thesis_config_version": run.thesis_config_version,
        "pipeline_version": run.pipeline_version,
        "as_of_date": str(run.as_of_date),
        "total_eligible": run.total_eligible,
        "total_ineligible": run.total_ineligible,
        "bucket_distribution": run.bucket_distribution_json,
        "status": run.status,
        "error_message": run.error_message,
        "started_at": str(run.started_at) if run.started_at else None,
        "completed_at": str(run.completed_at) if run.completed_at else None,
    }


def _build_score_response(score: Plan2ThesisScore, issuer: Issuer | None) -> dict[str, Any]:
    """Build response dict for a single thesis score with coverage summary."""
    # Reconstruct provenance from persisted JSON
    prov_json = score.feature_input_json.get("provenance", {})
    provenance = _provenance_from_json(prov_json)
    coverage = compute_coverage_summary(provenance)

    return {
        "issuer_id": str(score.issuer_id),
        "ticker": issuer.trade_name if issuer and issuer.trade_name else str(score.issuer_id),
        "company_name": issuer.legal_name if issuer else None,
        "sector": issuer.sector if issuer else None,
        "subsector": issuer.subsector if issuer else None,
        "eligible": score.eligible,
        "eligibility": score.eligibility_json,
        # scores
        "bucket": score.bucket,
        "thesis_rank_score": float(score.thesis_rank_score) if score.thesis_rank_score is not None else None,
        "thesis_rank": score.thesis_rank,
        # opportunity
        "direct_commodity_exposure_score": float(score.direct_commodity_exposure_score) if score.direct_commodity_exposure_score is not None else None,
        "indirect_commodity_exposure_score": float(score.indirect_commodity_exposure_score) if score.indirect_commodity_exposure_score is not None else None,
        "export_fx_leverage_score": float(score.export_fx_leverage_score) if score.export_fx_leverage_score is not None else None,
        "final_commodity_affinity_score": float(score.final_commodity_affinity_score) if score.final_commodity_affinity_score is not None else None,
        # fragility
        "refinancing_stress_score": float(score.refinancing_stress_score) if score.refinancing_stress_score is not None else None,
        "usd_debt_exposure_score": float(score.usd_debt_exposure_score) if score.usd_debt_exposure_score is not None else None,
        "usd_import_dependence_score": float(score.usd_import_dependence_score) if score.usd_import_dependence_score is not None else None,
        "usd_revenue_offset_score": float(score.usd_revenue_offset_score) if score.usd_revenue_offset_score is not None else None,
        "final_dollar_fragility_score": float(score.final_dollar_fragility_score) if score.final_dollar_fragility_score is not None else None,
        # explanation
        "explanation": score.explanation_json,
        # coverage & evidence quality
        "coverage": asdict(coverage),
        # raw provenance (for deep inspection)
        "provenance": prov_json,
    }


@router.get("/runs/{run_id}/ranking")
def get_ranking(
    run_id: str,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Get ranked results for a Plan 2 run with coverage summaries."""
    parsed_id = uuid.UUID(run_id)

    run = db.execute(
        select(Plan2Run).where(Plan2Run.id == parsed_id)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Plan 2 run not found")

    scores = db.execute(
        select(Plan2ThesisScore)
        .where(Plan2ThesisScore.plan2_run_id == parsed_id)
        .order_by(
            Plan2ThesisScore.thesis_rank.asc().nulls_last(),
        )
    ).scalars().all()

    # Batch-load issuers
    issuer_ids = [s.issuer_id for s in scores]
    issuers_by_id: dict[uuid.UUID, Issuer] = {}
    if issuer_ids:
        issuers = db.execute(
            select(Issuer).where(Issuer.id.in_(issuer_ids))
        ).scalars().all()
        issuers_by_id = {i.id: i for i in issuers}

    items = [
        _build_score_response(s, issuers_by_id.get(s.issuer_id))
        for s in scores
    ]

    # Aggregate coverage across all eligible issuers
    eligible_items = [i for i in items if i["eligible"]]
    run_evidence_distribution = _aggregate_evidence_quality(eligible_items)

    return {
        "run_id": str(run.id),
        "as_of_date": str(run.as_of_date),
        "thesis_config_version": run.thesis_config_version,
        "pipeline_version": run.pipeline_version,
        "total_eligible": run.total_eligible,
        "total_ineligible": run.total_ineligible,
        "bucket_distribution": run.bucket_distribution_json,
        "evidence_distribution": run_evidence_distribution,
        "items": items,
    }


@router.get("/runs/{run_id}/issuer/{issuer_id}")
def get_issuer_detail(
    run_id: str,
    issuer_id: str,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Get detailed Plan 2 score for a specific issuer in a run."""
    parsed_run_id = uuid.UUID(run_id)
    parsed_issuer_id = uuid.UUID(issuer_id)

    score = db.execute(
        select(Plan2ThesisScore).where(
            Plan2ThesisScore.plan2_run_id == parsed_run_id,
            Plan2ThesisScore.issuer_id == parsed_issuer_id,
        )
    ).scalar_one_or_none()

    if score is None:
        raise HTTPException(status_code=404, detail="Score not found for this issuer/run")

    issuer = db.execute(
        select(Issuer).where(Issuer.id == parsed_issuer_id)
    ).scalar_one_or_none()

    response = _build_score_response(score, issuer)

    # Add full feature input JSON for deep inspection
    response["feature_input_raw"] = score.feature_input_json

    return response


def _aggregate_evidence_quality(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate evidence quality across all eligible items."""
    if not items:
        return {
            "high_evidence_count": 0,
            "mixed_evidence_count": 0,
            "low_evidence_count": 0,
            "high_evidence_pct": 0.0,
            "mixed_evidence_pct": 0.0,
            "low_evidence_pct": 0.0,
        }

    total = len(items)
    high = sum(1 for i in items if i.get("coverage", {}).get("evidence_quality") == "HIGH_EVIDENCE")
    mixed = sum(1 for i in items if i.get("coverage", {}).get("evidence_quality") == "MIXED_EVIDENCE")
    low = sum(1 for i in items if i.get("coverage", {}).get("evidence_quality") == "LOW_EVIDENCE")

    return {
        "high_evidence_count": high,
        "mixed_evidence_count": mixed,
        "low_evidence_count": low,
        "high_evidence_pct": round(high / total * 100, 1),
        "mixed_evidence_pct": round(mixed / total * 100, 1),
        "low_evidence_pct": round(low / total * 100, 1),
    }


# ---------------------------------------------------------------------------
# Monitoring endpoints (F3.1)
# ---------------------------------------------------------------------------

def _extract_provenance_by_issuer(
    scores: Sequence[Plan2ThesisScore],
) -> dict[str, dict[str, ScoreProvenance]]:
    """Extract provenance maps from persisted thesis scores."""
    result: dict[str, dict[str, ScoreProvenance]] = {}
    for s in scores:
        if not s.eligible:
            continue
        fi = s.feature_input_json or {}
        prov_raw = fi.get("provenance", {})
        provenance = _provenance_from_json(prov_raw)
        if provenance:
            result[str(s.issuer_id)] = provenance
    return result


def _extract_issuer_run_data(
    scores: Sequence[Plan2ThesisScore],
    ticker_map: dict[uuid.UUID, str],
) -> list[IssuerRunData]:
    """Extract minimal run data for drift comparison."""
    return [
        IssuerRunData(
            issuer_id=str(s.issuer_id),
            ticker=ticker_map.get(s.issuer_id, str(s.issuer_id)[:8]),
            bucket=s.bucket,
            fragility=float(s.final_dollar_fragility_score) if s.final_dollar_fragility_score is not None else None,
            rank=s.thesis_rank,
        )
        for s in scores
        if s.eligible
    ]


def _build_ticker_map(db: Session, issuer_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Build issuer_id -> ticker map via securities table."""
    if not issuer_ids:
        return {}
    rows = db.execute(
        select(Security.issuer_id, Security.ticker)
        .where(Security.issuer_id.in_(issuer_ids), Security.is_primary.is_(True))
    ).all()
    return {r[0]: r[1] for r in rows}


@router.get("/runs/{run_id}/monitoring")
def get_run_monitoring(
    run_id: str,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Get monitoring summary for a Plan 2 run: coverage, provenance, confidence, evidence quality."""
    parsed_id = uuid.UUID(run_id)

    run = db.execute(
        select(Plan2Run).where(Plan2Run.id == parsed_id)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Plan 2 run not found")

    scores = db.execute(
        select(Plan2ThesisScore).where(Plan2ThesisScore.plan2_run_id == parsed_id)
    ).scalars().all()

    provenance_by_issuer = _extract_provenance_by_issuer(scores)
    summary = compute_run_monitoring(run_id, provenance_by_issuer)

    return {
        "run_id": summary.run_id,
        "total_eligible": summary.total_eligible,
        "dimension_coverage": [
            {
                "dimension_key": dc.dimension_key,
                "total_issuers": dc.total_issuers,
                "source_type_counts": dc.source_type_counts,
                "confidence_counts": dc.confidence_counts,
                "non_default_pct": dc.non_default_pct,
            }
            for dc in summary.dimension_coverage
        ],
        "provenance_mix": summary.provenance_mix,
        "provenance_mix_pct": summary.provenance_mix_pct,
        "confidence_distribution": summary.confidence_distribution,
        "evidence_quality_distribution": summary.evidence_quality_distribution,
        "evidence_quality_pct": summary.evidence_quality_pct,
    }


@router.get("/runs/{run_id}/drift")
def get_run_drift(
    run_id: str,
    vs_run_id: str | None = None,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Get drift between current run and a previous run.

    If vs_run_id is not provided, auto-detects the most recent previous run.
    """
    parsed_id = uuid.UUID(run_id)

    run = db.execute(
        select(Plan2Run).where(Plan2Run.id == parsed_id)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Plan 2 run not found")

    # Find previous run
    if vs_run_id:
        prev_run_id = uuid.UUID(vs_run_id)
    else:
        prev_run = db.execute(
            select(Plan2Run)
            .where(
                Plan2Run.id != parsed_id,
                Plan2Run.status == "completed",
                Plan2Run.created_at < run.created_at,
            )
            .order_by(Plan2Run.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if prev_run is None:
            return {"error": "No previous run found for drift comparison"}
        prev_run_id = prev_run.id

    # Load scores for both runs
    curr_scores = db.execute(
        select(Plan2ThesisScore).where(Plan2ThesisScore.plan2_run_id == parsed_id)
    ).scalars().all()
    prev_scores = db.execute(
        select(Plan2ThesisScore).where(Plan2ThesisScore.plan2_run_id == prev_run_id)
    ).scalars().all()

    # Build ticker map
    all_issuer_ids = list({s.issuer_id for s in curr_scores} | {s.issuer_id for s in prev_scores})
    ticker_map = _build_ticker_map(db, all_issuer_ids)

    curr_data = _extract_issuer_run_data(curr_scores, ticker_map)
    prev_data = _extract_issuer_run_data(prev_scores, ticker_map)

    drift = compute_run_drift(run_id, str(prev_run_id), curr_data, prev_data)

    return {
        "current_run_id": drift.current_run_id,
        "previous_run_id": drift.previous_run_id,
        "bucket_changes": drift.bucket_changes,
        "bucket_change_details": [
            {
                "issuer_id": d.issuer_id,
                "ticker": d.ticker,
                "old_bucket": d.old_bucket,
                "new_bucket": d.new_bucket,
                "fragility_delta": d.fragility_delta,
                "old_rank": d.old_rank,
                "new_rank": d.new_rank,
                "rank_delta": d.rank_delta,
            }
            for d in drift.bucket_change_details
        ],
        "top10_entered": drift.top10_entered,
        "top10_exited": drift.top10_exited,
        "top20_entered": drift.top20_entered,
        "top20_exited": drift.top20_exited,
        "new_issuers": drift.new_issuers,
        "dropped_issuers": drift.dropped_issuers,
        "fragility_delta_avg": drift.fragility_delta_avg,
        "fragility_delta_max": drift.fragility_delta_max,
        "fragility_delta_min": drift.fragility_delta_min,
    }


@router.get("/rubrics/aging")
def get_rubric_aging(
    stale_days: int = 30,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Get rubric aging report: stale rubrics by dimension and issuer."""
    rows = db.execute(
        select(
            Plan2RubricScore.issuer_id,
            Plan2RubricScore.dimension_key,
            Plan2RubricScore.score,
            Plan2RubricScore.source_type,
            Plan2RubricScore.confidence,
            Plan2RubricScore.assessed_at,
            Plan2RubricScore.assessed_by,
        ).where(Plan2RubricScore.superseded_at.is_(None))
    ).all()

    # Build ticker map
    issuer_ids = list({r[0] for r in rows})
    ticker_map = _build_ticker_map(db, issuer_ids)

    rubrics = [
        RubricRecord(
            issuer_id=str(r[0]),
            ticker=ticker_map.get(r[0], str(r[0])[:8]),
            dimension_key=r[1],
            source_type=r[3],
            confidence=r[4] or "low",
            assessed_at=r[5].date() if r[5] else None,
            assessed_by=r[6],
            score=float(r[2]),
        )
        for r in rows
    ]

    report = compute_rubric_aging(rubrics, stale_days=stale_days)

    return {
        "stale_threshold_days": report.stale_threshold_days,
        "total_active_rubrics": report.total_active_rubrics,
        "stale_count": report.stale_count,
        "stale_pct": report.stale_pct,
        "stale_by_dimension": report.stale_by_dimension,
        "stale_rubrics": [
            {
                "issuer_id": s.issuer_id,
                "ticker": s.ticker,
                "dimension_key": s.dimension_key,
                "source_type": s.source_type,
                "confidence": s.confidence,
                "assessed_at": str(s.assessed_at) if s.assessed_at else None,
                "age_days": s.age_days,
                "assessed_by": s.assessed_by,
            }
            for s in report.stale_rubrics
        ],
    }


@router.get("/rubrics/review-queue")
def get_review_queue(
    stale_days: int = 30,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Get prioritized review queue combining aging, confidence, and drift signals."""
    # Load active rubrics
    rows = db.execute(
        select(
            Plan2RubricScore.issuer_id,
            Plan2RubricScore.dimension_key,
            Plan2RubricScore.score,
            Plan2RubricScore.source_type,
            Plan2RubricScore.confidence,
            Plan2RubricScore.assessed_at,
            Plan2RubricScore.assessed_by,
        ).where(Plan2RubricScore.superseded_at.is_(None))
    ).all()

    issuer_ids = list({r[0] for r in rows})
    ticker_map = _build_ticker_map(db, issuer_ids)

    rubrics = [
        RubricRecord(
            issuer_id=str(r[0]),
            ticker=ticker_map.get(r[0], str(r[0])[:8]),
            dimension_key=r[1],
            source_type=r[3],
            confidence=r[4] or "low",
            assessed_at=r[5].date() if r[5] else None,
            assessed_by=r[6],
            score=float(r[2]),
        )
        for r in rows
    ]

    # Try to compute drift from latest two runs
    drift = None
    latest_runs = db.execute(
        select(Plan2Run)
        .where(Plan2Run.status == "completed")
        .order_by(Plan2Run.created_at.desc())
        .limit(2)
    ).scalars().all()

    if len(latest_runs) >= 2:
        curr_run, prev_run = latest_runs[0], latest_runs[1]
        curr_scores = db.execute(
            select(Plan2ThesisScore).where(Plan2ThesisScore.plan2_run_id == curr_run.id)
        ).scalars().all()
        prev_scores = db.execute(
            select(Plan2ThesisScore).where(Plan2ThesisScore.plan2_run_id == prev_run.id)
        ).scalars().all()

        all_ids = list({s.issuer_id for s in curr_scores} | {s.issuer_id for s in prev_scores})
        drift_ticker_map = _build_ticker_map(db, all_ids)

        curr_data = _extract_issuer_run_data(curr_scores, drift_ticker_map)
        prev_data = _extract_issuer_run_data(prev_scores, drift_ticker_map)

        drift = compute_run_drift(
            str(curr_run.id), str(prev_run.id), curr_data, prev_data,
        )

    queue = compute_review_queue(rubrics, drift=drift, stale_days=stale_days)

    return {
        "total_items": queue.total_items,
        "high_priority": queue.high_priority,
        "medium_priority": queue.medium_priority,
        "low_priority": queue.low_priority,
        "items": [
            {
                "issuer_id": i.issuer_id,
                "ticker": i.ticker,
                "dimension_key": i.dimension_key,
                "priority": i.priority,
                "reasons": i.reasons,
                "current_score": i.current_score,
                "source_type": i.source_type,
                "confidence": i.confidence,
                "age_days": i.age_days,
            }
            for i in queue.items
        ],
    }


@router.get("/runs/{run_id}/alerts")
def get_run_alerts(
    run_id: str,
    stale_days: int = 30,
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    """Get automated governance alerts for a Plan 2 run.

    Computes alerts from monitoring summary, drift, aging, and review queue.
    """
    from dataclasses import asdict as _asdict

    parsed_id = uuid.UUID(run_id)

    run = db.execute(
        select(Plan2Run).where(Plan2Run.id == parsed_id)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Plan 2 run not found")

    # 1. Monitoring summary
    scores = db.execute(
        select(Plan2ThesisScore).where(Plan2ThesisScore.plan2_run_id == parsed_id)
    ).scalars().all()
    provenance_by_issuer = _extract_provenance_by_issuer(scores)
    monitoring = compute_run_monitoring(run_id, provenance_by_issuer)

    # 2. Drift (auto-detect previous run)
    drift = None
    prev_run = db.execute(
        select(Plan2Run)
        .where(
            Plan2Run.id != parsed_id,
            Plan2Run.status == "completed",
            Plan2Run.created_at < run.created_at,
        )
        .order_by(Plan2Run.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if prev_run is not None:
        prev_scores = db.execute(
            select(Plan2ThesisScore).where(Plan2ThesisScore.plan2_run_id == prev_run.id)
        ).scalars().all()
        all_issuer_ids = list({s.issuer_id for s in scores} | {s.issuer_id for s in prev_scores})
        ticker_map = _build_ticker_map(db, all_issuer_ids)
        curr_data = _extract_issuer_run_data(scores, ticker_map)
        prev_data = _extract_issuer_run_data(prev_scores, ticker_map)
        drift = compute_run_drift(run_id, str(prev_run.id), curr_data, prev_data)

    # 3. Rubric aging
    rubric_rows = db.execute(
        select(
            Plan2RubricScore.issuer_id,
            Plan2RubricScore.dimension_key,
            Plan2RubricScore.score,
            Plan2RubricScore.source_type,
            Plan2RubricScore.confidence,
            Plan2RubricScore.assessed_at,
            Plan2RubricScore.assessed_by,
        ).where(Plan2RubricScore.superseded_at.is_(None))
    ).all()

    rubric_issuer_ids = list({r[0] for r in rubric_rows})
    rubric_ticker_map = _build_ticker_map(db, rubric_issuer_ids)

    rubrics = [
        RubricRecord(
            issuer_id=str(r[0]),
            ticker=rubric_ticker_map.get(r[0], str(r[0])[:8]),
            dimension_key=r[1],
            source_type=r[3],
            confidence=r[4] or "low",
            assessed_at=r[5].date() if r[5] else None,
            assessed_by=r[6],
            score=float(r[2]),
        )
        for r in rubric_rows
    ]

    aging = compute_rubric_aging(rubrics, stale_days=stale_days)

    # 4. Review queue
    review_queue = compute_review_queue(rubrics, drift=drift, stale_days=stale_days)

    # 5. Compute alerts
    alerts = compute_run_alerts(
        monitoring=monitoring,
        drift=drift,
        aging=aging,
        review_queue=review_queue,
    )

    return {
        "run_id": run_id,
        "alert_count": len(alerts),
        "critical_count": sum(1 for a in alerts if a.severity == "CRITICAL"),
        "warning_count": sum(1 for a in alerts if a.severity == "WARNING"),
        "alerts": [_asdict(a) for a in alerts],
    }
