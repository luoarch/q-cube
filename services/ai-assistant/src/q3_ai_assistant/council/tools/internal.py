"""Internal read-only tools for council agents and free chat.

All tools query structured internal data (source precedence level 1).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolResult:
    tool: str
    data: dict | list | None
    error: str | None = None


def get_ranked_assets(session: Session, strategy_run_id: str) -> ToolResult:
    """Get ranked assets from a strategy run."""
    from q3_shared_models.entities import StrategyRun

    run = session.query(StrategyRun).filter_by(id=strategy_run_id).first()
    if not run:
        return ToolResult(tool="get_ranked_assets", data=None, error="Strategy run not found")
    return ToolResult(tool="get_ranked_assets", data=run.result_json)


def get_refinement_results(session: Session, strategy_run_id: str) -> ToolResult:
    """Get refiner scores and flags for a strategy run."""
    from q3_shared_models.entities import RefinementResult

    rows = (
        session.query(RefinementResult)
        .filter_by(strategy_run_id=strategy_run_id)
        .order_by(RefinementResult.adjusted_rank)
        .all()
    )
    if not rows:
        return ToolResult(tool="get_refinement_results", data=None, error="No refinement results")

    data = [
        {
            "ticker": r.ticker,
            "base_rank": r.base_rank,
            "adjusted_rank": r.adjusted_rank,
            "refinement_score": float(r.refinement_score) if r.refinement_score else None,
            "earnings_quality": float(r.earnings_quality_score) if r.earnings_quality_score else None,
            "safety": float(r.safety_score) if r.safety_score else None,
            "consistency": float(r.operating_consistency_score) if r.operating_consistency_score else None,
            "capital_discipline": float(r.capital_discipline_score) if r.capital_discipline_score else None,
            "flags": r.flags_json,
            "reliability": r.score_reliability,
        }
        for r in rows
    ]
    return ToolResult(tool="get_refinement_results", data=data)


def get_company_flags(session: Session, ticker: str) -> ToolResult:
    """Get red/strength flags for a company from latest refiner run."""
    from q3_shared_models.entities import RefinementResult

    row = (
        session.query(RefinementResult)
        .filter_by(ticker=ticker)
        .order_by(RefinementResult.created_at.desc())
        .first()
    )
    if not row:
        return ToolResult(tool="get_company_flags", data=None, error="No refiner data for ticker")
    return ToolResult(tool="get_company_flags", data=row.flags_json)


def get_company_summary(session: Session, ticker: str) -> ToolResult:
    """Get basic company info from issuers + securities."""
    from q3_shared_models.entities import Issuer, Security

    security = session.query(Security).filter_by(ticker=ticker).first()
    if not security:
        return ToolResult(tool="get_company_summary", data=None, error="Ticker not found")

    issuer = session.query(Issuer).filter_by(id=security.issuer_id).first()
    if not issuer:
        return ToolResult(tool="get_company_summary", data=None, error="Issuer not found")

    return ToolResult(
        tool="get_company_summary",
        data={
            "ticker": ticker,
            "issuer_id": str(issuer.id),
            "company_name": issuer.company_name,
            "sector": issuer.sector,
            "subsector": issuer.subsector,
            "segment": issuer.segment,
        },
    )
