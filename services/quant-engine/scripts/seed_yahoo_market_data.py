#!/usr/bin/env python3
"""Seed market_snapshots with Yahoo Finance historical prices via yfinance.

Fetches 3 months of daily OHLCV for all primary securities and inserts
into market_snapshots with source='yahoo'. Also adjusts filing available_at
dates so PIT queries can find fundamentals within the price period.

Usage:
    python3 scripts/seed_yahoo_market_data.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timezone

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/q3")
REQUEST_DELAY = 0.5  # seconds between tickers


def fetch_historical(ticker: str, period: str = "3mo") -> list[dict]:
    """Fetch historical prices from Yahoo Finance."""
    import yfinance as yf

    yahoo_ticker = f"{ticker}.SA" if not ticker.startswith("^") else ticker
    try:
        df = yf.Ticker(yahoo_ticker).history(period=period)
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
        print(f"  ERROR fetching {ticker}: {e}")
        return []


def fetch_market_cap(ticker: str) -> float | None:
    """Fetch current market cap from Yahoo Finance."""
    import yfinance as yf

    yahoo_ticker = f"{ticker}.SA"
    try:
        info = yf.Ticker(yahoo_ticker).info
        return info.get("marketCap")
    except Exception:
        return None


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Get all primary securities
    cur.execute("SELECT id, ticker FROM securities WHERE is_primary = true ORDER BY ticker")
    securities = cur.fetchall()
    print(f"Found {len(securities)} primary securities\n")

    # 2. Fetch and insert real data
    insert_sql = """
        INSERT INTO market_snapshots (id, security_id, source, price, market_cap, volume, currency, fetched_at, raw_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    total_inserted = 0
    tickers_with_data = 0
    tickers_no_data = []

    for i, (sec_id, ticker) in enumerate(securities):
        if i % 50 == 0 and i > 0:
            print(f"  Progress: {i}/{len(securities)} tickers processed, {total_inserted} snapshots inserted")
            conn.commit()

        # Fetch historical prices
        prices = fetch_historical(ticker)
        time.sleep(REQUEST_DELAY)

        if not prices:
            tickers_no_data.append(ticker)
            continue

        tickers_with_data += 1

        # Fetch current market_cap
        market_cap = fetch_market_cap(ticker)
        time.sleep(REQUEST_DELAY)

        batch = []
        for p in prices:
            close_price = p.get("close")
            volume = p.get("volume")

            if close_price is None:
                continue

            batch.append((
                str(uuid.uuid4()),
                sec_id,
                "yahoo",
                round(float(close_price), 2),
                round(float(market_cap), 2) if market_cap else None,
                round(float(volume), 0) if volume else None,
                "BRL",
                p["date"].isoformat(),
                "{}",
            ))

        if batch:
            cur.executemany(insert_sql, batch)
            total_inserted += len(batch)

    conn.commit()

    # 3. Adjust filing available_at to match price period
    cur.execute("SELECT MIN(fetched_at) FROM market_snapshots WHERE source = 'yahoo'")
    min_price_date = cur.fetchone()[0]

    if min_price_date:
        print(f"\nEarliest price date: {min_price_date}")
        cur.execute("""
            UPDATE filings
            SET available_at = CASE
                WHEN reference_date <= '2024-06-30' THEN %s::timestamptz - INTERVAL '90 days'
                WHEN reference_date <= '2024-09-30' THEN %s::timestamptz - INTERVAL '60 days'
                ELSE %s::timestamptz - INTERVAL '30 days'
            END
        """, (min_price_date, min_price_date, min_price_date))
        updated_filings = cur.rowcount
        print(f"Updated available_at for {updated_filings} filings")
        conn.commit()

    # 4. Summary
    cur.execute("SELECT COUNT(*) FROM market_snapshots WHERE source = 'yahoo'")
    total_yahoo = cur.fetchone()[0]

    cur.execute("""
        SELECT MIN(fetched_at), MAX(fetched_at)
        FROM market_snapshots WHERE source = 'yahoo'
    """)
    date_range = cur.fetchone()

    print(f"\n{'='*60}")
    print(f"SEED COMPLETE (Yahoo/yfinance)")
    print(f"{'='*60}")
    print(f"Tickers with data:    {tickers_with_data}/{len(securities)}")
    print(f"Tickers no data:      {len(tickers_no_data)}")
    print(f"Total snapshots:      {total_yahoo}")
    if date_range[0]:
        print(f"Date range:           {date_range[0]} -> {date_range[1]}")
    if tickers_no_data[:20]:
        print(f"No data (first 20):   {', '.join(tickers_no_data[:20])}")
    print()

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
