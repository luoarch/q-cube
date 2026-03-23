"""Backfill CVM DFP/ITR filings for 2020–2023.

Runs the existing import_batch pipeline for each year/doc_type.
Idempotent, resumable, year-by-year.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/backfill_historical_filings.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time

from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.facade import FundamentalsIngestionFacade as FundamentalsEngineFacade

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_historical")

YEARS = [2020, 2021, 2022, 2023]
DOC_TYPES = ["DFP", "ITR"]


async def _run_batch(year: int, doc_type: str) -> dict:
    """Run a single batch with a fresh facade instance (fresh session)."""
    logger.info("=" * 60)
    logger.info("Starting %s %d", doc_type, year)
    logger.info("=" * 60)
    start = time.time()
    try:
        facade = FundamentalsEngineFacade()
        result = await facade.import_batch(year, [doc_type])
        elapsed = time.time() - start
        logger.info(
            "%s %d complete in %.1fs: %s",
            doc_type, year, elapsed,
            {k: v for k, v in result.items() if v > 0},
        )
        return {"year": year, "doc_type": doc_type, "status": "ok", "elapsed": elapsed, **result}
    except Exception as e:
        elapsed = time.time() - start
        logger.error("%s %d FAILED after %.1fs: %s", doc_type, year, elapsed, e, exc_info=True)
        return {"year": year, "doc_type": doc_type, "status": "error", "error": str(e), "elapsed": elapsed}


async def main() -> None:
    results = []

    # DFP first (annual), then ITR (quarterly)
    for doc_type in DOC_TYPES:
        for year in YEARS:
            result = await _run_batch(year, doc_type)
            results.append(result)

    # Backfill publication_date for new filings
    logger.info("Backfilling publication_date for new filings...")
    with SessionLocal() as session:
        from sqlalchemy import text
        updated = session.execute(text("""
            UPDATE filings
            SET publication_date = CASE
                WHEN filing_type = 'DFP' THEN reference_date + INTERVAL '90 days'
                WHEN filing_type = 'ITR' THEN reference_date + INTERVAL '45 days'
                ELSE reference_date + INTERVAL '90 days'
            END
            WHERE publication_date IS NULL
        """)).rowcount
        session.commit()
        logger.info("Backfilled publication_date for %d filings", updated)

    # Summary
    print(f"\n{'=' * 70}")
    print("BACKFILL SUMMARY")
    print(f"{'=' * 70}")
    for r in results:
        status = r["status"]
        if status == "ok":
            print(f"  {r['doc_type']} {r['year']}: OK ({r['elapsed']:.0f}s) — "
                  f"filings={r.get('filings_created', 0)}, "
                  f"metrics={r.get('metrics_computed', 0)}")
        else:
            print(f"  {r['doc_type']} {r['year']}: FAILED — {r.get('error', 'unknown')}")

    # Coverage report
    print(f"\n{'=' * 70}")
    print("COVERAGE REPORT")
    print(f"{'=' * 70}")
    with SessionLocal() as session:
        from sqlalchemy import text
        rows = session.execute(text("""
            SELECT EXTRACT(YEAR FROM reference_date)::int as yr,
                   filing_type,
                   count(*) as filings,
                   count(DISTINCT issuer_id) as issuers
            FROM filings WHERE status = 'completed'
            GROUP BY yr, filing_type
            ORDER BY yr, filing_type
        """)).fetchall()
        for yr, ft, cnt, iss in rows:
            print(f"  {yr} {ft}: {cnt} filings, {iss} issuers")

        total = session.execute(text("SELECT count(*) FROM filings WHERE status = 'completed'")).scalar()
        total_sl = session.execute(text("SELECT count(*) FROM statement_lines")).scalar()
        print(f"\n  Total filings: {total:,}")
        print(f"  Total statement_lines: {total_sl:,}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
