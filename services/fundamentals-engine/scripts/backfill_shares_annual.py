"""Backfill shares_outstanding from yfinance ANNUAL balance_sheet.

Targets 2023 and earlier dates not covered by quarterly_balance_sheet.
Matches annual data points to closest snapshot within +/- 30 days.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/backfill_shares_annual.py [--dry-run]
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

WINDOW_DAYS = 30


def _to_yahoo(ticker: str) -> str:
    if ticker.startswith("^"):
        return ticker
    return f"{ticker}.SA"


def _backfill_security(session, sec: Security, *, dry_run: bool) -> int:
    yahoo_ticker = _to_yahoo(sec.ticker)
    try:
        t = yf.Ticker(yahoo_ticker)
        bs = t.balance_sheet  # Annual, not quarterly
    except Exception:
        logger.warning("  yfinance failed for %s", sec.ticker)
        return 0

    if bs is None or bs.empty:
        return 0

    shares_row = None
    for candidate in ["Ordinary Shares Number", "Share Issued"]:
        if candidate in bs.index:
            shares_row = candidate
            break

    if shares_row is None:
        return 0

    updates = 0
    for col in bs.columns:
        shares_value = bs.loc[shares_row, col]
        if shares_value is None or (hasattr(shares_value, "__float__") and shares_value != shares_value):
            continue

        annual_date = col.date() if hasattr(col, "date") else col
        if not isinstance(annual_date, date):
            continue

        window_start = annual_date - timedelta(days=WINDOW_DAYS)
        window_end = annual_date + timedelta(days=WINDOW_DAYS)

        snapshot = session.execute(
            select(MarketSnapshot)
            .where(
                MarketSnapshot.security_id == sec.id,
                MarketSnapshot.fetched_at >= window_start,
                MarketSnapshot.fetched_at <= window_end,
                MarketSnapshot.shares_outstanding.is_(None),
            )
            .order_by(MarketSnapshot.fetched_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if snapshot is None:
            continue

        if dry_run:
            logger.info(
                "  [DRY RUN] %s: snapshot %s (fetched %s) <- shares=%s from annual %s",
                sec.ticker, snapshot.id, snapshot.fetched_at, int(shares_value), annual_date,
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
    parser = argparse.ArgumentParser(description="Backfill shares from annual balance sheet")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        securities = session.execute(
            select(Security).where(
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).scalars().all()

        logger.info("Processing %d primary securities (annual balance sheet)", len(securities))

        total_updates = 0
        failures = 0
        for i, sec in enumerate(securities, 1):
            if i % 50 == 0:
                logger.info("[%d/%d] ...", i, len(securities))
            try:
                updates = _backfill_security(session, sec, dry_run=args.dry_run)
                total_updates += updates
                if updates:
                    logger.info("  %s: %d snapshots updated", sec.ticker, updates)
            except Exception:
                logger.warning("  %s: FAILED", sec.ticker, exc_info=True)
                failures += 1

            time.sleep(0.3)

            if not args.dry_run and i % 50 == 0:
                session.commit()

        if not args.dry_run:
            session.commit()

        logger.info("Done. Updates: %d, failures: %d", total_updates, failures)

    finally:
        session.close()


if __name__ == "__main__":
    main()
