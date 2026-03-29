"""Backfill cvm_share_counts from CVM composicao_capital CSVs (2020-2024).

Downloads DFP/ITR ZIP files from CVM, extracts composicao_capital CSVs,
parses them via shares/parser.py, and persists via shares/loader.py.

Idempotent: safe to run multiple times (upsert).

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/backfill_cvm_shares.py
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile

import httpx

from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.shares.loader import persist_share_counts, _build_issuer_map
from q3_fundamentals_engine.shares.parser import parse_composicao_capital

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_cvm_shares")

CVM_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"

# DFP 2020-2024 + ITR 2020-2024
SOURCES = [
    ("DFP", year) for year in range(2020, 2025)
] + [
    ("ITR", year) for year in range(2020, 2025)
]


def _download_composicao_capital(doc_type: str, year: int) -> list[dict[str, str]]:
    """Download and extract composicao_capital CSV from CVM ZIP."""
    url = f"{CVM_BASE}/{doc_type}/DADOS/{doc_type.lower()}_cia_aberta_{year}.zip"
    logger.info("Downloading %s %d from %s", doc_type, year, url)
    resp = httpx.get(url, timeout=120, verify=False, follow_redirects=True)
    resp.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    for name in z.namelist():
        if "composicao_capital" in name.lower():
            with z.open(name) as f:
                data = f.read().decode("latin-1")
                reader = csv.DictReader(io.StringIO(data), delimiter=";")
                rows = list(reader)
                logger.info("  %s: %d rows", name, len(rows))
                return rows
    logger.warning("  No composicao_capital found in %s %d ZIP", doc_type, year)
    return []


def main() -> None:
    with SessionLocal() as session:
        issuer_map = _build_issuer_map(session)
        logger.info("Issuer map: %d CNPJs", len(issuer_map))

        total_inserted = 0
        total_updated = 0
        total_skipped = 0
        total_parsed = 0

        for doc_type, year in SOURCES:
            rows = _download_composicao_capital(doc_type, year)
            if not rows:
                continue

            source_file = f"CVM_{doc_type}_{year}_composicao_capital"
            parsed = parse_composicao_capital(rows, doc_type, source_file)
            total_parsed += len(parsed)
            logger.info("  Parsed %d share count rows", len(parsed))

            result = persist_share_counts(session, parsed, issuer_map=issuer_map)
            total_inserted += result.inserted
            total_updated += result.updated
            total_skipped += result.skipped_no_issuer

        session.commit()

        # --- Report ---
        from sqlalchemy import text

        total_rows = session.execute(text("SELECT count(*) FROM cvm_share_counts")).scalar()
        total_issuers = session.execute(text("SELECT count(DISTINCT issuer_id) FROM cvm_share_counts")).scalar()

        # Core coverage
        core_covered = session.execute(text("""
            SELECT count(DISTINCT c.issuer_id)
            FROM cvm_share_counts c
            JOIN universe_classifications uc ON uc.issuer_id = c.issuer_id
                AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
        """)).scalar()

        core_total = session.execute(text("""
            SELECT count(DISTINCT uc.issuer_id)
            FROM universe_classifications uc
            WHERE uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
        """)).scalar()

        # Temporal coverage (issuers with >= 2 distinct reference_dates)
        temporal = session.execute(text("""
            SELECT count(*) FROM (
                SELECT issuer_id
                FROM cvm_share_counts
                GROUP BY issuer_id
                HAVING count(DISTINCT reference_date) >= 2
            ) sub
        """)).scalar()

        # Per-quarter distribution
        quarter_dist = session.execute(text("""
            SELECT reference_date, document_type, count(*)
            FROM cvm_share_counts
            GROUP BY 1, 2
            ORDER BY 1, 2
        """)).fetchall()

        print(f"\n{'=' * 60}")
        print("CVM Share Counts Backfill Report")
        print(f"{'=' * 60}")
        print(f"Sources: {len(SOURCES)} ZIPs (DFP+ITR 2020-2024)")
        print(f"Parsed rows: {total_parsed}")
        print(f"Inserted: {total_inserted}")
        print(f"Updated: {total_updated}")
        print(f"Skipped (no issuer match): {total_skipped}")
        print(f"\nDB total rows: {total_rows}")
        print(f"DB total issuers: {total_issuers}")
        print(f"Core covered: {core_covered}/{core_total} ({core_covered/core_total*100:.1f}%)" if core_total else "Core: N/A")
        print(f"Issuers with >= 2 dates (temporal): {temporal}")
        print(f"\nPer quarter-end distribution:")
        for ref, doc, cnt in quarter_dist:
            print(f"  {ref} {doc}: {cnt}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
