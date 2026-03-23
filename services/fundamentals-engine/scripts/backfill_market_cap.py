"""Backfill market_cap = shares_outstanding * price for snapshots missing market_cap.

Provenance: sets market_cap as a derived value (shares * price) only where
both shares_outstanding and price are available and market_cap is currently NULL.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/backfill_market_cap.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import select, update, and_, text

sys.path.insert(0, "src")

from q3_fundamentals_engine.db.session import SessionLocal  # noqa: E402
from q3_shared_models.entities import MarketSnapshot  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill market_cap from shares * price")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        # Count candidates
        candidates = session.execute(
            select(MarketSnapshot.id, MarketSnapshot.price, MarketSnapshot.shares_outstanding)
            .where(
                MarketSnapshot.price.isnot(None),
                MarketSnapshot.price > 0,
                MarketSnapshot.shares_outstanding.isnot(None),
                MarketSnapshot.shares_outstanding > 0,
                MarketSnapshot.market_cap.is_(None),
            )
        ).all()

        logger.info("Found %d snapshots to backfill (have price+shares, no market_cap)", len(candidates))

        if not candidates:
            logger.info("Nothing to backfill.")
            return

        # Sample
        for snap_id, price, shares in candidates[:5]:
            mcap = float(price) * float(shares)
            logger.info("  Sample: price=%.2f × shares=%.0f = market_cap=%.0f", float(price), float(shares), mcap)

        if args.dry_run:
            logger.info("[DRY RUN] Would update %d rows. Exiting.", len(candidates))
            return

        # Bulk update via SQL for efficiency
        updated = session.execute(
            text("""
                UPDATE market_snapshots
                SET market_cap = shares_outstanding * price
                WHERE price IS NOT NULL AND price > 0
                AND shares_outstanding IS NOT NULL AND shares_outstanding > 0
                AND market_cap IS NULL
            """)
        ).rowcount

        session.commit()
        logger.info("Updated %d snapshots with derived market_cap.", updated)

        # Verify
        remaining = session.execute(
            select(MarketSnapshot.id)
            .where(
                MarketSnapshot.price.isnot(None),
                MarketSnapshot.price > 0,
                MarketSnapshot.shares_outstanding.isnot(None),
                MarketSnapshot.shares_outstanding > 0,
                MarketSnapshot.market_cap.is_(None),
            )
        ).all()
        logger.info("Remaining NULL market_cap with price+shares: %d", len(remaining))

    finally:
        session.close()


if __name__ == "__main__":
    main()
