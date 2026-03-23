"""One-time backfill: populate shares_outstanding in market_snapshots.

Uses yfinance quarterly_balance_sheet to get historical share counts,
then matches each to the closest market_snapshot within +/- 30 days.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/backfill_shares_outstanding.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, timedelta

import yfinance as yf
from sqlalchemy import select, update

sys.path.insert(0, "src")

from q3_fundamentals_engine.db.session import SessionLocal  # noqa: E402
from q3_shared_models.entities import MarketSnapshot, Security  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

QUARTER_WINDOW_DAYS = 30


def _to_yahoo(ticker: str) -> str:
    if ticker.startswith("^"):
        return ticker
    return f"{ticker}.SA"


def _backfill_security(session, sec: Security, *, dry_run: bool) -> int:
    """Backfill shares_outstanding for one security. Returns count of updates."""
    yahoo_ticker = _to_yahoo(sec.ticker)
    try:
        t = yf.Ticker(yahoo_ticker)
        bs = t.quarterly_balance_sheet
    except Exception:
        logger.warning("  yfinance failed for %s", sec.ticker)
        return 0

    if bs is None or bs.empty:
        logger.info("  no quarterly_balance_sheet for %s", sec.ticker)
        return 0

    # Extract Ordinary Shares Number or Share Issued
    shares_row = None
    for candidate in ["Ordinary Shares Number", "Share Issued"]:
        if candidate in bs.index:
            shares_row = candidate
            break

    if shares_row is None:
        logger.info("  no shares row in balance sheet for %s", sec.ticker)
        return 0

    updates = 0
    for col in bs.columns:
        shares_value = bs.loc[shares_row, col]
        if shares_value is None or (hasattr(shares_value, "__float__") and shares_value != shares_value):
            continue  # NaN check

        quarter_date = col.date() if hasattr(col, "date") else col
        if not isinstance(quarter_date, date):
            continue

        # Find closest snapshot within +/- 30 days
        window_start = quarter_date - timedelta(days=QUARTER_WINDOW_DAYS)
        window_end = quarter_date + timedelta(days=QUARTER_WINDOW_DAYS)

        snapshot = session.execute(
            select(MarketSnapshot)
            .where(
                MarketSnapshot.security_id == sec.id,
                MarketSnapshot.fetched_at >= window_start,
                MarketSnapshot.fetched_at <= window_end,
                MarketSnapshot.shares_outstanding.is_(None),
            )
            .order_by(
                # Closest to quarter-end first
                MarketSnapshot.fetched_at.desc()
            )
            .limit(1)
        ).scalar_one_or_none()

        if snapshot is None:
            continue

        if dry_run:
            logger.info(
                "  [DRY RUN] would update snapshot %s (fetched %s) with shares=%s for quarter %s",
                snapshot.id, snapshot.fetched_at, int(shares_value), quarter_date,
            )
        else:
            session.execute(
                update(MarketSnapshot)
                .where(MarketSnapshot.id == snapshot.id)
                .values(shares_outstanding=float(shares_value))
            )
        updates += 1

    return updates


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill shares_outstanding in market_snapshots")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        securities = session.execute(
            select(Security).where(
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).scalars().all()

        logger.info("Backfilling shares_outstanding for %d primary securities", len(securities))

        total_updates = 0
        failures = 0
        for i, sec in enumerate(securities, 1):
            logger.info("[%d/%d] Processing %s...", i, len(securities), sec.ticker)
            try:
                updates = _backfill_security(session, sec, dry_run=args.dry_run)
                total_updates += updates
                if updates:
                    logger.info("  -> %d snapshots updated", updates)
            except Exception:
                logger.warning("  -> FAILED", exc_info=True)
                failures += 1

            time.sleep(0.3)  # rate limiting

            # Commit in batches of 50
            if not args.dry_run and i % 50 == 0:
                session.commit()
                logger.info("  committed batch")

        if not args.dry_run:
            session.commit()

        logger.info(
            "Done. Total updates: %d, failures: %d, securities: %d",
            total_updates, failures, len(securities),
        )

        # Coverage report
        from sqlalchemy import func
        total = session.execute(select(func.count()).select_from(MarketSnapshot)).scalar()
        filled = session.execute(
            select(func.count()).select_from(MarketSnapshot).where(
                MarketSnapshot.shares_outstanding.isnot(None)
            )
        ).scalar()
        logger.info("Coverage: %d / %d snapshots (%.1f%%)", filled, total, filled * 100 / total if total else 0)

    finally:
        session.close()


if __name__ == "__main__":
    main()
