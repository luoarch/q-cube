"""Filing serving endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from q3_shared_models.entities import Filing, Issuer, StatementLine
from sqlalchemy import select

from q3_fundamentals_engine.db.session import SessionLocal

router = APIRouter(prefix="", tags=["filings"])


@router.get("/issuers/{cvm_code}/filings")
def get_issuer_filings(
    cvm_code: str,
    filing_type: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> dict:
    with SessionLocal() as session:
        issuer = session.execute(
            select(Issuer).where(Issuer.cvm_code == cvm_code)
        ).scalar_one_or_none()

        if issuer is None:
            raise HTTPException(status_code=404, detail=f"Issuer with cvm_code={cvm_code} not found")

        query = select(Filing).where(Filing.issuer_id == issuer.id)
        if filing_type:
            query = query.where(Filing.filing_type == filing_type)
        query = query.order_by(Filing.reference_date.desc()).limit(limit)

        filings = session.execute(query).scalars().all()

    return {
        "issuerId": str(issuer.id),
        "cvmCode": cvm_code,
        "filings": [
            {
                "id": str(f.id),
                "filingType": f.filing_type.value if hasattr(f.filing_type, "value") else str(f.filing_type),
                "referenceDate": str(f.reference_date),
                "versionNumber": f.version_number,
                "isRestatement": f.is_restatement,
                "status": f.status.value if hasattr(f.status, "value") else str(f.status),
                "source": f.source.value if hasattr(f.source, "value") else str(f.source),
            }
            for f in filings
        ],
    }


@router.get("/filings/{filing_id}/statement-lines")
def get_filing_statement_lines(
    filing_id: uuid.UUID,
    statement_type: str | None = Query(None),
    canonical_only: bool = Query(False, description="Only return lines with canonical_key"),
) -> dict:
    with SessionLocal() as session:
        filing = session.execute(
            select(Filing).where(Filing.id == filing_id)
        ).scalar_one_or_none()

        if filing is None:
            raise HTTPException(status_code=404, detail=f"Filing {filing_id} not found")

        query = select(StatementLine).where(StatementLine.filing_id == filing_id)
        if statement_type:
            query = query.where(StatementLine.statement_type == statement_type)
        if canonical_only:
            query = query.where(StatementLine.canonical_key.is_not(None))
        query = query.order_by(StatementLine.as_reported_code)

        lines = session.execute(query).scalars().all()

    return {
        "filingId": str(filing_id),
        "referenceDate": str(filing.reference_date),
        "lines": [
            {
                "id": str(line.id),
                "statementType": line.statement_type.value if hasattr(line.statement_type, "value") else str(line.statement_type),
                "scope": line.scope.value if hasattr(line.scope, "value") else str(line.scope),
                "canonicalKey": line.canonical_key,
                "asReportedCode": line.as_reported_code,
                "asReportedLabel": line.as_reported_label,
                "normalizedValue": float(line.normalized_value) if line.normalized_value is not None else None,
                "currency": line.currency,
                "unitScale": line.unit_scale,
            }
            for line in lines
        ],
    }
