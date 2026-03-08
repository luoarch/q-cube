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
    from q3_shared_models.entities import RefinementResultModel

    rows = (
        session.query(RefinementResultModel)
        .filter_by(strategy_run_id=strategy_run_id)
        .order_by(RefinementResultModel.adjusted_rank)
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
    from q3_shared_models.entities import RefinementResultModel

    row = (
        session.query(RefinementResultModel)
        .filter_by(ticker=ticker)
        .order_by(RefinementResultModel.created_at.desc())
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
            "company_name": issuer.legal_name,
            "trade_name": issuer.trade_name,
            "sector": issuer.sector,
            "subsector": issuer.subsector,
            "segment": issuer.segment,
        },
    )


def get_company_financials_3p(session: Session, ticker: str) -> ToolResult:
    """Get 3-period financial data for a company."""
    from q3_shared_models.entities import ComputedMetric, Security

    security = session.query(Security).filter_by(ticker=ticker).first()
    if not security:
        return ToolResult(tool="get_company_financials_3p", data=None, error="Ticker not found")

    metrics = (
        session.query(ComputedMetric)
        .filter_by(issuer_id=security.issuer_id, period_type="annual")
        .order_by(ComputedMetric.reference_date.desc())
        .limit(30)
        .all()
    )

    trends: dict[str, list[dict]] = {}
    for m in metrics:
        code = m.metric_code
        val = float(m.value) if m.value is not None else None
        ref_date = str(m.reference_date)
        trends.setdefault(code, []).append({"reference_date": ref_date, "value": val})

    for code in trends:
        trends[code] = sorted(trends[code], key=lambda x: x["reference_date"])[-3:]

    return ToolResult(tool="get_company_financials_3p", data=trends)


def get_market_snapshot(session: Session, ticker: str) -> ToolResult:
    """Get latest market snapshot for a ticker."""
    from q3_shared_models.entities import MarketSnapshot, Security

    security = session.query(Security).filter_by(ticker=ticker).first()
    if not security:
        return ToolResult(tool="get_market_snapshot", data=None, error="Ticker not found")

    snapshot = (
        session.query(MarketSnapshot)
        .filter_by(security_id=security.id)
        .order_by(MarketSnapshot.fetched_at.desc())
        .first()
    )
    if not snapshot:
        return ToolResult(tool="get_market_snapshot", data=None, error="No market snapshot")

    return ToolResult(
        tool="get_market_snapshot",
        data={
            "ticker": ticker,
            "price": float(snapshot.price) if snapshot.price else None,
            "market_cap": float(snapshot.market_cap) if snapshot.market_cap else None,
            "volume": float(snapshot.volume) if snapshot.volume else None,
            "fetched_at": str(snapshot.fetched_at),
            "source": snapshot.source.value if snapshot.source else None,
        },
    )


def get_strategy_definition(strategy_type: str) -> ToolResult:
    """Get strategy definition (deterministic, no DB needed)."""
    definitions = {
        "magic_formula": {
            "name": "Magic Formula (Greenblatt)",
            "description": "Ranks companies by earnings yield + ROIC. Combines value and quality.",
            "metrics": ["earnings_yield", "roic"],
            "ranking_method": "Combined percentile rank (50% EY + 50% ROIC)",
        },
    }

    defn = definitions.get(strategy_type)
    if not defn:
        return ToolResult(
            tool="get_strategy_definition", data=None,
            error=f"Unknown strategy: {strategy_type}",
        )
    return ToolResult(tool="get_strategy_definition", data=defn)


def get_data_lineage(session: Session, ticker: str, metric_code: str) -> ToolResult:
    """Trace data lineage: filing -> statement_line -> computed_metric."""
    from q3_shared_models.entities import ComputedMetric, Security

    security = session.query(Security).filter_by(ticker=ticker).first()
    if not security:
        return ToolResult(tool="get_data_lineage", data=None, error="Ticker not found")

    metric = (
        session.query(ComputedMetric)
        .filter_by(issuer_id=security.issuer_id, metric_code=metric_code)
        .order_by(ComputedMetric.reference_date.desc())
        .first()
    )
    if not metric:
        return ToolResult(
            tool="get_data_lineage", data=None,
            error=f"Metric {metric_code} not found for {ticker}",
        )

    return ToolResult(
        tool="get_data_lineage",
        data={
            "ticker": ticker,
            "metric_code": metric_code,
            "value": float(metric.value) if metric.value is not None else None,
            "reference_date": str(metric.reference_date),
            "period_type": metric.period_type,
            "issuer_id": str(metric.issuer_id),
            "source": "computed_metrics (derived from statement_lines <- filings <- CVM)",
        },
    )


def compare_companies(session: Session, tickers: list[str]) -> ToolResult:
    """Run lightweight metric comparison between 2-3 tickers."""
    from q3_shared_models.entities import ComputedMetric, Security

    if len(tickers) < 2 or len(tickers) > 3:
        return ToolResult(
            tool="compare_companies", data=None,
            error="Provide 2-3 tickers",
        )

    comparison_metrics = [
        "earnings_yield", "roic", "roe", "gross_margin",
        "ebit_margin", "net_margin", "debt_to_ebitda",
    ]

    ticker_data: dict[str, dict[str, float | None]] = {}
    for ticker in tickers:
        security = session.query(Security).filter_by(ticker=ticker).first()
        if not security:
            continue

        metrics = (
            session.query(ComputedMetric)
            .filter_by(issuer_id=security.issuer_id, period_type="annual")
            .order_by(ComputedMetric.reference_date.desc())
            .limit(30)
            .all()
        )

        latest: dict[str, float | None] = {}
        for m in metrics:
            if m.metric_code not in latest and m.metric_code in comparison_metrics:
                latest[m.metric_code] = float(m.value) if m.value is not None else None
        ticker_data[ticker] = latest

    if len(ticker_data) < 2:
        return ToolResult(
            tool="compare_companies", data=None,
            error="Could not find at least 2 of the requested tickers",
        )

    return ToolResult(
        tool="compare_companies",
        data={
            "tickers": list(ticker_data.keys()),
            "metrics": ticker_data,
        },
    )
