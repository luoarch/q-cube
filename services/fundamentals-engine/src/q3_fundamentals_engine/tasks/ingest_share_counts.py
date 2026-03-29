"""Ingest CVM composicao_capital from a DFP/ITR ZIP file.

Called by the filing pipeline when processing a CVM ZIP.
Extracts composicao_capital CSV if present, parses, and persists.

Owner: fundamentals-engine (Plan 5 §6.3).
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile

from sqlalchemy.orm import Session

from q3_fundamentals_engine.shares.loader import persist_share_counts, LoadResult, _build_issuer_map
from q3_fundamentals_engine.shares.parser import parse_composicao_capital

logger = logging.getLogger(__name__)


def ingest_share_counts_from_zip(
    session: Session,
    zip_bytes: bytes,
    document_type: str,
    year: int,
) -> LoadResult | None:
    """Extract and persist composicao_capital from a CVM ZIP.

    Args:
        session: SQLAlchemy session (caller manages commit).
        zip_bytes: Raw ZIP file content.
        document_type: 'DFP' or 'ITR'.
        year: Fiscal year of the ZIP.

    Returns:
        LoadResult if composicao_capital CSV found, None otherwise.
    """
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for name in z.namelist():
        if "composicao_capital" in name.lower():
            with z.open(name) as f:
                data = f.read().decode("latin-1")
                reader = csv.DictReader(io.StringIO(data), delimiter=";")
                rows = list(reader)

            logger.info("Found composicao_capital: %s (%d rows)", name, len(rows))
            source_file = f"CVM_{document_type}_{year}_composicao_capital"
            parsed = parse_composicao_capital(rows, document_type, source_file)

            if not parsed:
                logger.info("No valid share count rows after parsing")
                return LoadResult()

            issuer_map = _build_issuer_map(session)
            return persist_share_counts(session, parsed, issuer_map=issuer_map)

    logger.debug("No composicao_capital CSV found in ZIP")
    return None
