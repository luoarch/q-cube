"""S3.5 Data Remediation — Fill gaps in market_snapshots for NPY computation.

Three remediation steps:
1. Backfill market_cap = shares_outstanding × price (where shares exist but mcap missing)
2. Backfill shares_outstanding = market_cap / price (where mcap exists but shares missing)
3. Post-remediation coverage audit

Provenance:
- Derived market_cap is marked by being computed from shares × price (not from provider)
- Derived shares is marked by being computed from market_cap / price (not from provider)
- Neither overwrites existing non-NULL values

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/s35_data_remediation.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import date, timedelta

from sqlalchemy import text, select, func, distinct

sys.path.insert(0, "src")

from q3_fundamentals_engine.db.session import SessionLocal  # noqa: E402
from q3_shared_models.entities import (  # noqa: E402
    Filing,
    FilingStatus,
    MarketSnapshot,
    Security,
    StatementLine,
)
from q3_fundamentals_engine.metrics.snapshot_anchor import find_anchored_snapshot  # noqa: E402
from q3_fundamentals_engine.metrics.ttm import (  # noqa: E402
    quarter_end_dates,
    load_quarterly_ytd_values,
    extract_standalone_quarters,
    _subtract_quarter,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def step1_backfill_market_cap(session, *, dry_run: bool) -> int:
    """Backfill market_cap = shares_outstanding × price."""
    logger.info("\n=== STEP 1: Backfill market_cap from shares × price ===")

    count = session.execute(text("""
        SELECT count(*) FROM market_snapshots
        WHERE price IS NOT NULL AND price > 0
        AND shares_outstanding IS NOT NULL AND shares_outstanding > 0
        AND (market_cap IS NULL OR market_cap = 0)
    """)).scalar()

    logger.info("Candidates: %d snapshots", count)

    if dry_run:
        logger.info("[DRY RUN] Would update %d rows.", count)
        return count

    updated = session.execute(text("""
        UPDATE market_snapshots
        SET market_cap = shares_outstanding * price
        WHERE price IS NOT NULL AND price > 0
        AND shares_outstanding IS NOT NULL AND shares_outstanding > 0
        AND (market_cap IS NULL OR market_cap = 0)
    """)).rowcount

    session.commit()
    logger.info("Updated %d snapshots.", updated)
    return updated


def step2_backfill_shares(session, *, dry_run: bool) -> int:
    """Backfill shares_outstanding = market_cap / price."""
    logger.info("\n=== STEP 2: Backfill shares_outstanding from market_cap / price ===")

    count = session.execute(text("""
        SELECT count(*) FROM market_snapshots
        WHERE market_cap IS NOT NULL AND market_cap > 0
        AND price IS NOT NULL AND price > 0
        AND (shares_outstanding IS NULL OR shares_outstanding = 0)
    """)).scalar()

    logger.info("Candidates: %d snapshots", count)

    if dry_run:
        logger.info("[DRY RUN] Would update %d rows.", count)
        return count

    updated = session.execute(text("""
        UPDATE market_snapshots
        SET shares_outstanding = market_cap / price
        WHERE market_cap IS NOT NULL AND market_cap > 0
        AND price IS NOT NULL AND price > 0
        AND (shares_outstanding IS NULL OR shares_outstanding = 0)
    """)).rowcount

    session.commit()
    logger.info("Updated %d snapshots.", updated)
    return updated


def step3_coverage_audit(session) -> None:
    """Post-remediation coverage audit."""
    logger.info("\n=== STEP 3: Coverage Audit ===")

    anchor = date(2024, 12, 31)
    logger.info("Reference anchor: %s", anchor)

    # Get distribution issuers
    dist_issuers = session.execute(
        select(distinct(Filing.issuer_id))
        .join(StatementLine, StatementLine.filing_id == Filing.id)
        .where(
            Filing.status == FilingStatus.completed,
            StatementLine.canonical_key == "shareholder_distributions",
        )
    ).scalars().all()

    logger.info("Total distribution issuers: %d", len(dist_issuers))

    dy_ok = 0
    nby_ok = 0
    both_ok = 0

    dy_reasons: dict[str, int] = {
        "no_4q": 0,
        "no_primary": 0,
        "no_snap": 0,
        "no_mcap": 0,
    }
    nby_reasons: dict[str, int] = {
        "no_primary": 0,
        "no_snap_t": 0,
        "no_shares_t": 0,
        "no_snap_t4": 0,
        "no_shares_t4": 0,
    }

    for issuer_id in dist_issuers:
        has_dy = False
        has_nby = False

        # DY check
        dates = quarter_end_dates(anchor)
        ytd = load_quarterly_ytd_values(session, issuer_id, "shareholder_distributions", dates)
        standalones = extract_standalone_quarters(ytd, dates)

        if standalones is None:
            dy_reasons["no_4q"] += 1
        else:
            snap = find_anchored_snapshot(session, issuer_id, anchor)
            if snap is None:
                # Check if it's because no primary security
                from q3_fundamentals_engine.metrics.snapshot_anchor import _get_primary_security_id
                if _get_primary_security_id(session, issuer_id) is None:
                    dy_reasons["no_primary"] += 1
                else:
                    dy_reasons["no_snap"] += 1
            elif snap.market_cap is None or float(snap.market_cap) <= 0:
                dy_reasons["no_mcap"] += 1
            else:
                has_dy = True
                dy_ok += 1

        # NBY check
        snap_t = find_anchored_snapshot(session, issuer_id, anchor)
        if snap_t is None:
            from q3_fundamentals_engine.metrics.snapshot_anchor import _get_primary_security_id
            if _get_primary_security_id(session, issuer_id) is None:
                nby_reasons["no_primary"] += 1
            else:
                nby_reasons["no_snap_t"] += 1
        elif snap_t.shares_outstanding is None or float(snap_t.shares_outstanding) <= 0:
            nby_reasons["no_shares_t"] += 1
        else:
            t4 = anchor
            for _ in range(4):
                t4 = _subtract_quarter(t4)
            snap_t4 = find_anchored_snapshot(session, issuer_id, t4)
            if snap_t4 is None:
                nby_reasons["no_snap_t4"] += 1
            elif snap_t4.shares_outstanding is None or float(snap_t4.shares_outstanding) <= 0:
                nby_reasons["no_shares_t4"] += 1
            else:
                has_nby = True
                nby_ok += 1

        if has_dy and has_nby:
            both_ok += 1

    logger.info("\n--- COVERAGE RESULTS ---")
    logger.info("DY computable: %d / %d (%.1f%%)", dy_ok, len(dist_issuers), dy_ok / len(dist_issuers) * 100)
    for reason, cnt in sorted(dy_reasons.items(), key=lambda x: -x[1]):
        logger.info("  NULL — %s: %d", reason, cnt)

    logger.info("")
    logger.info("NBY computable: %d / %d (%.1f%%)", nby_ok, len(dist_issuers), nby_ok / len(dist_issuers) * 100)
    for reason, cnt in sorted(nby_reasons.items(), key=lambda x: -x[1]):
        logger.info("  NULL — %s: %d", reason, cnt)

    logger.info("")
    logger.info("NPY computable (DY ∩ NBY): %d / %d (%.1f%%)", both_ok, len(dist_issuers), both_ok / len(dist_issuers) * 100)

    gate = "PASSED" if both_ok >= 30 else "FAILED"
    logger.info("\n--- GATE CHECK: NPY ≥ 30 issuers → %s (%d issuers) ---", gate, both_ok)


def main() -> None:
    parser = argparse.ArgumentParser(description="S3.5 Data Remediation for NPY")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        step1_backfill_market_cap(session, dry_run=args.dry_run)
        step2_backfill_shares(session, dry_run=args.dry_run)
        step3_coverage_audit(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
