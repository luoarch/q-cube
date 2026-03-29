"""Backfill market_snapshots from B3 COTAHIST (2020-2024).

Downloads annual COTAHIST ZIPs, parses, matches to securities,
derives market_cap = close × CVM net_shares, persists.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/backfill_b3_cotahist.py
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import select, text

from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.providers.b3.adapter import parse_annual, build_snapshot_data, get_latest_close
from q3_fundamentals_engine.providers.b3.parser import CotahistRecord
from q3_fundamentals_engine.shares.lookup import find_cvm_shares
from q3_shared_models.entities import MarketSnapshot, Security, SourceProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_b3")

YEARS = [2020, 2021, 2022, 2023, 2024]


def _snap_to_quarter_end(d: date) -> date:
    """Snap a date to its quarter-end."""
    m = d.month
    if m <= 3:
        return date(d.year, 3, 31)
    elif m <= 6:
        return date(d.year, 6, 30)
    elif m <= 9:
        return date(d.year, 9, 30)
    else:
        return date(d.year, 12, 31)


def main() -> None:
    with SessionLocal() as session:
        # Build ticker → security_id map (primary, valid)
        sec_rows = session.execute(
            select(Security.ticker, Security.id, Security.issuer_id).where(
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).all()
        ticker_to_sec = {r[0]: (r[1], r[2]) for r in sec_rows}
        logger.info("Securities: %d tickers", len(ticker_to_sec))

        # CVM shares cache: (issuer_id, quarter_end) → net_shares
        cvm_cache: dict[tuple, float | None] = {}

        def get_cvm_net_shares(issuer_id: uuid.UUID, as_of: date) -> float | None:
            qe = _snap_to_quarter_end(as_of)
            key = (issuer_id, qe)
            if key not in cvm_cache:
                cvm = find_cvm_shares(session, issuer_id, qe)
                cvm_cache[key] = float(cvm.net_shares) if cvm else None
            return cvm_cache[key]

        total_inserted = 0
        total_skipped_no_sec = 0
        total_skipped_dup = 0
        total_with_mcap = 0

        for year in YEARS:
            logger.info("Processing COTAHIST %d...", year)
            records = parse_annual(year)
            logger.info("  Parsed %d records", len(records))

            # Group by (ticker, date) — take last record per day (dedup)
            by_ticker_date: dict[tuple[str, date], CotahistRecord] = {}
            for rec in records:
                by_ticker_date[(rec.ticker, rec.date)] = rec

            # Get last trading day per ticker for this year (for snapshot insert)
            # We insert ONE snapshot per ticker per month (last trading day of each month)
            by_ticker_month: dict[tuple[str, int, int], CotahistRecord] = {}
            for (ticker, dt), rec in by_ticker_date.items():
                key = (ticker, dt.year, dt.month)
                if key not in by_ticker_month or dt > by_ticker_month[key].date:
                    by_ticker_month[key] = rec

            logger.info("  Monthly snapshots to insert: %d", len(by_ticker_month))

            batch_inserted = 0
            for (ticker, yr, mo), rec in by_ticker_month.items():
                sec_info = ticker_to_sec.get(ticker)
                if sec_info is None:
                    total_skipped_no_sec += 1
                    continue

                sec_id, issuer_id = sec_info

                # Derive market_cap
                net_shares = get_cvm_net_shares(issuer_id, rec.date)
                derived_mcap = rec.close * net_shares if net_shares else None
                shares_quarter = str(_snap_to_quarter_end(rec.date)) if net_shares else None

                # Check for existing snapshot (avoid duplicate)
                fetched_at = datetime(rec.date.year, rec.date.month, rec.date.day, 23, 59, 0, tzinfo=timezone.utc)
                existing = session.execute(
                    select(MarketSnapshot.id).where(
                        MarketSnapshot.security_id == sec_id,
                        MarketSnapshot.source == SourceProvider.b3,
                        MarketSnapshot.fetched_at == fetched_at,
                    )
                ).scalar_one_or_none()

                if existing:
                    total_skipped_dup += 1
                    continue

                session.add(MarketSnapshot(
                    id=uuid.uuid4(),
                    security_id=sec_id,
                    source=SourceProvider.b3,
                    price=rec.close,
                    market_cap=derived_mcap,
                    volume=rec.volume,
                    currency="BRL",
                    shares_outstanding=None,
                    fetched_at=fetched_at,
                    raw_json={
                        "source": "b3_cotahist",
                        "close": rec.close,
                        "open": rec.open,
                        "high": rec.high,
                        "low": rec.low,
                        "volume_brl": rec.volume,
                        "n_trades": rec.n_trades,
                        "date": str(rec.date),
                        "derivation": "close × CVM net_shares" if derived_mcap else None,
                        "shares_quarter": shares_quarter,
                    },
                ))

                batch_inserted += 1
                if derived_mcap:
                    total_with_mcap += 1

                if batch_inserted % 1000 == 0:
                    session.flush()

            session.flush()
            total_inserted += batch_inserted
            logger.info("  Year %d: inserted=%d", year, batch_inserted)

        session.commit()

        # Refresh compat view
        session.execute(text("REFRESH MATERIALIZED VIEW v_financial_statements_compat"))
        session.commit()

        # Report
        total_b3 = session.execute(text("SELECT count(*) FROM market_snapshots WHERE source = 'b3'")).scalar()
        view_mcap = session.execute(text("SELECT count(*) FROM v_financial_statements_compat WHERE market_cap IS NOT NULL AND market_cap > 0")).scalar()
        view_total = session.execute(text("SELECT count(*) FROM v_financial_statements_compat")).scalar()
        dy_count = session.execute(text("SELECT count(*) FROM v_financial_statements_compat WHERE dividend_yield IS NOT NULL")).scalar()

        print(f"\n{'='*60}")
        print("B3 COTAHIST Backfill Report")
        print(f"{'='*60}")
        print(f"Years: {YEARS}")
        print(f"Inserted: {total_inserted}")
        print(f"Skipped (no security): {total_skipped_no_sec}")
        print(f"Skipped (duplicate): {total_skipped_dup}")
        print(f"With derived mcap: {total_with_mcap}")
        print(f"\nDB total B3 snapshots: {total_b3}")
        print(f"Compat view: {view_total} total, {view_mcap} with mcap ({view_mcap/view_total*100:.1f}%)")
        print(f"DY coverage: {dy_count}/{view_total} = {dy_count/view_total*100:.1f}%")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
