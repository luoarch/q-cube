"""PIT-aware lookup for CVM share counts.

Exact match by quarter-end. No nearest-neighbor approximation.
DFP > ITR precedence (Plan 5 §6.5) implemented here as the single
point of decision — consumers must NOT reimplement this ordering.

Owner: fundamentals-engine (Plan 5 §6.3).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_shared_models.entities import CVMShareCount

logger = logging.getLogger(__name__)

_DOC_PRIORITY = {"DFP": 0, "ITR": 1}


def find_cvm_shares(
    session: Session,
    issuer_id: uuid.UUID,
    target_quarter_end: date,
    *,
    knowledge_date: date | None = None,
) -> CVMShareCount | None:
    """Find CVM share count for an issuer at a specific quarter-end.

    Args:
        session: SQLAlchemy session.
        issuer_id: Target issuer.
        target_quarter_end: Exact quarter-end date (e.g. 2024-12-31).
            **No window/approximation** — reference_date must match exactly.
        knowledge_date: When provided, only rows with
            publication_date_estimated <= knowledge_date are considered
            (strict PIT mode). When None, all rows are returned (relaxed mode).

    Returns:
        CVMShareCount or None. When both DFP and ITR exist for the same date,
        DFP is preferred (§6.5 precedence).
    """
    all_rows = session.execute(
        select(CVMShareCount).where(
            CVMShareCount.issuer_id == issuer_id,
            CVMShareCount.reference_date == target_quarter_end,
        )
    ).scalars().all()

    if not all_rows:
        return None

    candidates: list[CVMShareCount] = list(all_rows)

    # PIT filter: only rows whose publication_date_estimated <= knowledge_date
    if knowledge_date is not None:
        candidates = [r for r in candidates if r.publication_date_estimated <= knowledge_date]
        if not candidates:
            return None

    # DFP > ITR precedence (§6.5): sort by document priority, pick first
    candidates.sort(key=lambda r: _DOC_PRIORITY.get(r.document_type, 99))
    return candidates[0]
