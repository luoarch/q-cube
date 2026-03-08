#!/usr/bin/env python3
"""Seed market_snapshots with real BRAPI historical prices.

Fetches 3 months of daily OHLCV from brapi.dev for all primary securities
and inserts into market_snapshots. Also adjusts filing available_at dates
so PIT queries can find fundamentals within the price period.

Usage:
    BRAPI_TOKEN=xxx python3 scripts/seed_real_market_data.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/q3")
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN", "")
BRAPI_BASE_URL = "https://brapi.dev/api"

# Rate limiting: free plan = 15K req/month, be polite
REQUEST_DELAY = 0.3  # seconds between requests


def fetch_historical(ticker: str) -> list[dict]:
    """Fetch 3 months of daily prices from BRAPI."""
    params = {"token": BRAPI_TOKEN, "range": "3mo", "interval": "1d"}
    try:
        resp = httpx.get(f"{BRAPI_BASE_URL}/quote/{ticker}", params=params, timeout=30)
        if resp.status_code != 200:
            return []
        results = resp.json().get("results", [])
        if not results:
            return []
        return results[0].get("historicalDataPrice", [])
    except Exception as e:
        print(f"  ERROR fetching {ticker}: {e}")
        return []


def fetch_quote(ticker: str) -> dict | None:
    """Fetch current quote from BRAPI."""
    params = {"token": BRAPI_TOKEN}
    try:
        resp = httpx.get(f"{BRAPI_BASE_URL}/quote/{ticker}", params=params, timeout=30)
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"  ERROR fetching quote {ticker}: {e}")
        return None


def main():
    if not BRAPI_TOKEN:
        print("ERROR: BRAPI_TOKEN not set. Export it or pass via env.")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Get all primary securities
    cur.execute("SELECT id, ticker FROM securities WHERE is_primary = true ORDER BY ticker")
    securities = cur.fetchall()
    print(f"Found {len(securities)} primary securities\n")

    # 2. Clear synthetic market_snapshots
    cur.execute("DELETE FROM market_snapshots WHERE source = 'manual'")
    deleted = cur.rowcount
    print(f"Cleared {deleted} synthetic snapshots\n")
    conn.commit()

    # 3. Fetch and insert real data
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
        batch = []

        # Also fetch current quote for market_cap
        quote = fetch_quote(ticker)
        time.sleep(REQUEST_DELAY)
        market_cap = quote.get("marketCap") if quote else None

        for p in prices:
            ts = p.get("date")
            if not ts:
                continue

            fetched_at = datetime.fromtimestamp(ts, tz=timezone.utc)
            close_price = p.get("adjustedClose") or p.get("close")
            volume = p.get("volume")

            if close_price is None:
                continue

            batch.append((
                str(uuid.uuid4()),
                sec_id,
                "brapi",
                round(float(close_price), 2),
                round(float(market_cap), 2) if market_cap else None,
                round(float(volume), 0) if volume else None,
                "BRL",
                fetched_at.isoformat(),
                "{}",
            ))

        if batch:
            cur.executemany(insert_sql, batch)
            total_inserted += len(batch)

    conn.commit()

    # 4. Adjust filing available_at to match price period
    # Find the earliest price date
    cur.execute("SELECT MIN(fetched_at) FROM market_snapshots WHERE source = 'brapi'")
    min_price_date = cur.fetchone()[0]

    if min_price_date:
        print(f"\nEarliest price date: {min_price_date}")

        # Set available_at for all filings to before the price period
        # So PIT queries find fundamentals during backtest
        # Filing with reference_date Q4 2024 → available_at set to 2 months before earliest price
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

    # 5. Summary
    cur.execute("SELECT COUNT(*) FROM market_snapshots WHERE source = 'brapi'")
    total_brapi = cur.fetchone()[0]

    cur.execute("""
        SELECT MIN(fetched_at), MAX(fetched_at)
        FROM market_snapshots WHERE source = 'brapi'
    """)
    date_range = cur.fetchone()

    print(f"\n{'='*60}")
    print(f"SEED COMPLETE")
    print(f"{'='*60}")
    print(f"Tickers with data:    {tickers_with_data}/{len(securities)}")
    print(f"Tickers no data:      {len(tickers_no_data)}")
    print(f"Total snapshots:      {total_brapi}")
    print(f"Date range:           {date_range[0]} → {date_range[1]}")
    if tickers_no_data[:20]:
        print(f"No data (first 20):   {', '.join(tickers_no_data[:20])}")
    print()

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
