#!/usr/bin/env python3
"""Seed market_snapshots with Yahoo Finance historical prices for backtesting.

Fetches daily OHLCV for all primary securities covering a configurable period
(default: 2 years) and inserts into market_snapshots. This enables backtesting
over historical periods.

Unlike seed_yahoo_market_data.py (3-month window), this script covers longer
periods for research-grade backtesting.

Usage:
    cd services/quant-engine
    .venv/bin/python scripts/seed_historical_prices.py [--start 2023-01-01] [--end 2024-12-31] [--batch-size 50]
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg://127.0.0.1:5432/q3"
REQUEST_DELAY = 0.3  # seconds between tickers


def fetch_historical(ticker: str, start: str, end: str) -> list[dict]:
    """Fetch historical prices from Yahoo Finance for a date range."""
    import yfinance as yf

    yahoo_ticker = f"{ticker}.SA" if not ticker.startswith("^") else ticker
    try:
        df = yf.Ticker(yahoo_ticker).history(start=start, end=end)
        if df.empty:
            return []
        records = []
        for idx, row in df.iterrows():
            records.append({
                "date": idx.to_pydatetime().replace(tzinfo=timezone.utc),
                "close": row.get("Close"),
                "volume": row.get("Volume"),
            })
        return records
    except Exception as e:
        print(f"  ERROR {ticker}: {e}")
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed historical prices for backtesting")
    parser.add_argument("--start", default="2023-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--batch-size", type=int, default=50, help="Commit every N tickers")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tickers (0=all)")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Get primary securities
        result = conn.execute(text(
            "SELECT id, ticker FROM securities WHERE is_primary = true ORDER BY ticker"
        ))
        securities = result.fetchall()
        print(f"Found {len(securities)} primary securities")
        print(f"Period: {args.start} → {args.end}\n")

        if args.limit > 0:
            securities = securities[:args.limit]
            print(f"Limited to {args.limit} tickers\n")

        # Check existing snapshot count in the target range
        existing = conn.execute(text(
            "SELECT COUNT(*) FROM market_snapshots WHERE fetched_at >= :start AND fetched_at <= :end"
        ), {"start": args.start, "end": args.end}).scalar()
        print(f"Existing snapshots in range: {existing}\n")

        total_inserted = 0
        tickers_with_data = 0
        tickers_no_data = []

        for i, (sec_id, ticker) in enumerate(securities):
            if i > 0 and i % args.batch_size == 0:
                conn.commit()
                print(f"  Progress: {i}/{len(securities)} tickers, {total_inserted} snapshots inserted")

            prices = fetch_historical(ticker, args.start, args.end)
            time.sleep(REQUEST_DELAY)

            if not prices:
                tickers_no_data.append(ticker)
                continue

            tickers_with_data += 1
            batch_count = 0

            for p in prices:
                close_price = p.get("close")
                volume = p.get("volume")
                if close_price is None:
                    continue

                # Use ON CONFLICT to skip duplicates
                conn.execute(text("""
                    INSERT INTO market_snapshots (id, security_id, source, price, volume, currency, fetched_at, raw_json)
                    VALUES (:id, :sec_id, 'yahoo', :price, :volume, 'BRL', :fetched_at, '{}')
                    ON CONFLICT (security_id, fetched_at) DO NOTHING
                """), {
                    "id": str(uuid.uuid4()),
                    "sec_id": sec_id,
                    "price": round(float(close_price), 2),
                    "volume": round(float(volume), 0) if volume else None,
                    "fetched_at": p["date"].isoformat(),
                })
                batch_count += 1

            total_inserted += batch_count

        conn.commit()

        # Summary
        total = conn.execute(text("SELECT COUNT(*) FROM market_snapshots")).scalar()
        range_result = conn.execute(text(
            "SELECT MIN(fetched_at), MAX(fetched_at) FROM market_snapshots"
        )).fetchone()

        print(f"\n{'='*60}")
        print(f"SEED COMPLETE")
        print(f"{'='*60}")
        print(f"Tickers with data:    {tickers_with_data}/{len(securities)}")
        print(f"Tickers no data:      {len(tickers_no_data)}")
        print(f"Snapshots inserted:   {total_inserted}")
        print(f"Total snapshots (DB): {total}")
        if range_result and range_result[0]:
            print(f"Full date range:      {range_result[0]} → {range_result[1]}")
        if tickers_no_data[:20]:
            print(f"No data (first 20):   {', '.join(tickers_no_data[:20])}")
        print()


if __name__ == "__main__":
    main()
