"""Metrics serving endpoints."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query
from q3_shared_models.entities import ComputedMetric, Issuer, Security
from sqlalchemy import select

from q3_fundamentals_engine.db.session import SessionLocal


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

router = APIRouter(prefix="", tags=["metrics"])


@router.get("/issuers/{cvm_code}/metrics")
def get_issuer_metrics(
    cvm_code: str,
    codes: str | None = Query(None, description="Comma-separated metric codes (e.g. roic,ebit_margin)"),
    reference_date: str | None = Query(None, description="Filter by reference date (YYYY-MM-DD)"),
) -> dict:
    with SessionLocal() as session:
        issuer = session.execute(
            select(Issuer).where(Issuer.cvm_code == cvm_code)
        ).scalar_one_or_none()

        if issuer is None:
            raise HTTPException(status_code=404, detail=f"Issuer with cvm_code={cvm_code} not found")

        query = select(ComputedMetric).where(ComputedMetric.issuer_id == issuer.id)
        if codes:
            code_list = [c.strip() for c in codes.split(",")]
            query = query.where(ComputedMetric.metric_code.in_(code_list))
        if reference_date:
            query = query.where(ComputedMetric.reference_date == _parse_date(reference_date))
        query = query.order_by(ComputedMetric.reference_date.desc(), ComputedMetric.metric_code)

        metrics = session.execute(query).scalars().all()

    return {
        "issuerId": str(issuer.id),
        "cvmCode": cvm_code,
        "metrics": [
            {
                "id": str(m.id),
                "metricCode": m.metric_code,
                "periodType": m.period_type.value if hasattr(m.period_type, "value") else str(m.period_type),
                "referenceDate": str(m.reference_date),
                "value": float(m.value) if m.value is not None else None,
                "formulaVersion": m.formula_version,
                "inputsSnapshot": m.inputs_snapshot_json,
                "sourceFilingIds": m.source_filing_ids_json,
            }
            for m in metrics
        ],
    }


@router.get("/rankings")
def get_rankings(
    strategy: str = Query("magic_formula", description="Ranking strategy"),
    reference_date: str | None = Query(None),
    limit: int = Query(50, le=200),
    exclude_sectors: str | None = Query(
        "Financeiro,Seguros",
        description="Comma-separated sectors to exclude (regulated sectors distort ROIC/EY)",
    ),
) -> dict:
    with SessionLocal() as session:
        # Get latest reference date if not specified
        if not reference_date:
            latest = session.execute(
                select(ComputedMetric.reference_date)
                .where(ComputedMetric.metric_code == "roic")
                .order_by(ComputedMetric.reference_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest is None:
                return {"strategy": strategy, "referenceDate": None, "rankings": []}
            reference_date = str(latest)

        ref_date = _parse_date(reference_date)

        # Load EY and ROIC for all issuers at this date
        ey_metrics = session.execute(
            select(ComputedMetric)
            .where(
                ComputedMetric.metric_code == "earnings_yield",
                ComputedMetric.reference_date == ref_date,
                ComputedMetric.value.is_not(None),
            )
        ).scalars().all()

        roic_metrics = session.execute(
            select(ComputedMetric)
            .where(
                ComputedMetric.metric_code == "roic",
                ComputedMetric.reference_date == ref_date,
                ComputedMetric.value.is_not(None),
            )
        ).scalars().all()

        # Also load ebit_margin as EY proxy when earnings_yield unavailable
        ebit_margin_metrics = session.execute(
            select(ComputedMetric)
            .where(
                ComputedMetric.metric_code == "ebit_margin",
                ComputedMetric.reference_date == ref_date,
                ComputedMetric.value.is_not(None),
            )
        ).scalars().all()

        # Build maps — use earnings_yield if available, else ebit_margin as proxy
        ey_by_issuer = {m.issuer_id: float(m.value) for m in ey_metrics if m.value is not None}
        if not ey_by_issuer:
            ey_by_issuer = {m.issuer_id: float(m.value) for m in ebit_margin_metrics if m.value is not None}
        roic_by_issuer = {m.issuer_id: float(m.value) for m in roic_metrics if m.value is not None}

        # Only rank issuers with both metrics
        common_issuers = set(ey_by_issuer.keys()) & set(roic_by_issuer.keys())
        if not common_issuers:
            return {"strategy": strategy, "referenceDate": reference_date, "rankings": []}

        # Filter out excluded sectors (e.g. financials, insurance)
        if exclude_sectors:
            excluded = {s.strip() for s in exclude_sectors.split(",")}
            issuer_sectors = {
                i.id: i.sector
                for i in session.execute(
                    select(Issuer).where(Issuer.id.in_(common_issuers))
                ).scalars().all()
            }
            common_issuers = {
                iid for iid in common_issuers
                if issuer_sectors.get(iid) not in excluded
            }
            if not common_issuers:
                return {"strategy": strategy, "referenceDate": reference_date, "rankings": []}

        # Rank EY descending (higher = better)
        ey_sorted = sorted(common_issuers, key=lambda i: ey_by_issuer[i], reverse=True)
        ey_ranks = {issuer_id: rank + 1 for rank, issuer_id in enumerate(ey_sorted)}

        # Rank ROIC descending
        roic_sorted = sorted(common_issuers, key=lambda i: roic_by_issuer[i], reverse=True)
        roic_ranks = {issuer_id: rank + 1 for rank, issuer_id in enumerate(roic_sorted)}

        # Combined rank
        combined = [
            (issuer_id, ey_ranks[issuer_id] + roic_ranks[issuer_id])
            for issuer_id in common_issuers
        ]
        combined.sort(key=lambda x: x[1])

        # Fetch issuer info + primary ticker
        results = []
        for rank, (issuer_id, score) in enumerate(combined[:limit], 1):
            issuer = session.execute(
                select(Issuer).where(Issuer.id == issuer_id)
            ).scalar_one_or_none()

            primary_ticker = session.execute(
                select(Security.ticker)
                .where(Security.issuer_id == issuer_id, Security.is_primary.is_(True))
                .limit(1)
            ).scalar_one_or_none()

            if issuer is None:
                continue

            results.append({
                "rank": rank,
                "cvmCode": issuer.cvm_code,
                "legalName": issuer.legal_name,
                "ticker": primary_ticker,
                "sector": issuer.sector,
                "earningsYield": ey_by_issuer[issuer_id],
                "roic": roic_by_issuer[issuer_id],
                "eyRank": ey_ranks[issuer_id],
                "roicRank": roic_ranks[issuer_id],
                "combinedScore": score,
            })

    return {
        "strategy": strategy,
        "referenceDate": reference_date,
        "rankings": results,
    }
