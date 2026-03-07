"""Issuer serving endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from q3_shared_models.entities import Issuer, Security
from sqlalchemy import select

from q3_fundamentals_engine.db.session import SessionLocal

router = APIRouter(prefix="/issuers", tags=["issuers"])


@router.get("")
def list_issuers(
    status: str = Query("active", description="Filter by status"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    with SessionLocal() as session:
        query = select(Issuer).where(Issuer.status == status).offset(offset).limit(limit)
        issuers = session.execute(query).scalars().all()

        count_query = select(Issuer).where(Issuer.status == status)
        total = len(session.execute(count_query).scalars().all())

    return {
        "items": [
            {
                "id": str(i.id),
                "cvmCode": i.cvm_code,
                "legalName": i.legal_name,
                "tradeName": i.trade_name,
                "cnpj": i.cnpj,
                "sector": i.sector,
                "subsector": i.subsector,
                "segment": i.segment,
                "status": i.status,
            }
            for i in issuers
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{cvm_code}")
def get_issuer(cvm_code: str) -> dict:
    with SessionLocal() as session:
        issuer = session.execute(
            select(Issuer).where(Issuer.cvm_code == cvm_code)
        ).scalar_one_or_none()

    if issuer is None:
        raise HTTPException(status_code=404, detail=f"Issuer with cvm_code={cvm_code} not found")

    return {
        "id": str(issuer.id),
        "cvmCode": issuer.cvm_code,
        "legalName": issuer.legal_name,
        "tradeName": issuer.trade_name,
        "cnpj": issuer.cnpj,
        "sector": issuer.sector,
        "subsector": issuer.subsector,
        "segment": issuer.segment,
        "status": issuer.status,
    }


@router.get("/{cvm_code}/securities")
def get_issuer_securities(cvm_code: str) -> dict:
    with SessionLocal() as session:
        issuer = session.execute(
            select(Issuer).where(Issuer.cvm_code == cvm_code)
        ).scalar_one_or_none()

        if issuer is None:
            raise HTTPException(status_code=404, detail=f"Issuer with cvm_code={cvm_code} not found")

        securities = session.execute(
            select(Security).where(Security.issuer_id == issuer.id)
        ).scalars().all()

    return {
        "issuerId": str(issuer.id),
        "cvmCode": cvm_code,
        "securities": [
            {
                "id": str(s.id),
                "ticker": s.ticker,
                "securityClass": s.security_class,
                "isPrimary": s.is_primary,
                "validFrom": str(s.valid_from),
                "validTo": str(s.valid_to) if s.valid_to else None,
            }
            for s in securities
        ],
    }
