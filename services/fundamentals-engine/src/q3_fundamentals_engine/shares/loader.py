"""Persist ShareCountRow objects into cvm_share_counts table.

Idempotent upsert by (issuer_id, reference_date, document_type).
Owner: fundamentals-engine (Plan 5 §6.3).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_shared_models.entities import CVMShareCount, Issuer

from q3_fundamentals_engine.shares.parser import ShareCountRow

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Stats from a persist_share_counts call."""

    inserted: int = 0
    updated: int = 0
    skipped_no_issuer: int = 0
    total_rows: int = 0


def _normalize_cnpj(cnpj: str) -> str:
    return re.sub(r"[^0-9]", "", cnpj)


def _build_issuer_map(session: Session) -> dict[str, uuid.UUID]:
    """Build normalized CNPJ (digits-only) → issuer_id map from issuers table."""
    rows = session.execute(select(Issuer.cnpj, Issuer.id)).all()
    return {_normalize_cnpj(cnpj): issuer_id for cnpj, issuer_id in rows}


def persist_share_counts(
    session: Session,
    share_rows: list[ShareCountRow],
    *,
    issuer_map: dict[str, uuid.UUID] | None = None,
) -> LoadResult:
    """Upsert ShareCountRows into cvm_share_counts.

    Args:
        session: SQLAlchemy session (caller manages commit).
        share_rows: Parsed rows from parser.
        issuer_map: Optional pre-built CNPJ→issuer_id map. Built on demand if None.

    Returns:
        LoadResult with insert/update/skip stats.
    """
    if issuer_map is None:
        issuer_map = _build_issuer_map(session)

    # Deduplicate by (cnpj, reference_date, document_type) — keep last row
    # (CVM CSVs can contain restatements for same issuer/date)
    deduped: dict[tuple[str, date, str], ShareCountRow] = {}
    for row in share_rows:
        key = (row.cnpj, row.reference_date, row.document_type)
        deduped[key] = row  # last wins (latest version)
    unique_rows = list(deduped.values())

    result = LoadResult(total_rows=len(share_rows))

    FLUSH_EVERY = 500

    for i, row in enumerate(unique_rows):
        issuer_id = issuer_map.get(row.cnpj)
        if issuer_id is None:
            result.skipped_no_issuer += 1
            continue

        existing = session.execute(
            select(CVMShareCount)
            .where(
                CVMShareCount.issuer_id == issuer_id,
                CVMShareCount.reference_date == row.reference_date,
                CVMShareCount.document_type == row.document_type,
            )
            .with_for_update()
        ).scalar_one_or_none()

        if existing is not None:
            existing.total_shares = row.total_shares
            existing.treasury_shares = row.treasury_shares
            existing.net_shares = row.net_shares
            existing.publication_date_estimated = row.publication_date_estimated
            existing.source_file = row.source_file
            result.updated += 1
        else:
            session.add(CVMShareCount(
                id=uuid.uuid4(),
                issuer_id=issuer_id,
                reference_date=row.reference_date,
                document_type=row.document_type,
                total_shares=row.total_shares,
                treasury_shares=row.treasury_shares,
                net_shares=row.net_shares,
                publication_date_estimated=row.publication_date_estimated,
                source_file=row.source_file,
            ))
            result.inserted += 1

        # Flush periodically so subsequent SELECTs can see pending inserts
        # (avoids unique constraint violations from cross-batch duplicates)
        if (i + 1) % FLUSH_EVERY == 0:
            session.flush()

    if share_rows:
        session.flush()

    logger.info(
        "persist_share_counts: inserted=%d updated=%d skipped_no_issuer=%d total=%d",
        result.inserted, result.updated, result.skipped_no_issuer, result.total_rows,
    )
    return result
