"""Plan 2 internal API — preview/inspection endpoints.

Exposes Plan 2 results for internal validation before public UI.
All endpoints read from persisted plan2_runs + plan2_thesis_scores.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_quant_engine.db.session import SessionLocal
from q3_shared_models.entities import Plan2Run, Plan2ThesisScore, Issuer
from q3_quant_engine.thesis.coverage import compute_coverage_summary
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
