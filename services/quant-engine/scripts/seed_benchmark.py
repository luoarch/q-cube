#!/usr/bin/env python3
"""Seed IBOV benchmark data from BRAPI into market_snapshots.

Creates a pseudo-security for ^BVSP and inserts daily IBOV prices.

Usage:
    BRAPI_TOKEN=xxx python3 scripts/seed_benchmark.py
"""

import os
import sys
import uuid
from datetime import datetime, timezone

import httpx
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/q3")
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN", "")
BRAPI_BASE_URL = "https://brapi.dev/api"
IBOV_TICKER = "^BVSP"


def main():
    if not BRAPI_TOKEN:
        print("ERROR: BRAPI_TOKEN not set")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Check if ^BVSP security exists, create if not
    cur.execute("SELECT id FROM securities WHERE ticker = %s", (IBOV_TICKER,))
    row = cur.fetchone()

    if row:
        sec_id = row[0]
        print(f"Found existing ^BVSP security: {sec_id}")
    else:
        # Need an issuer first
        issuer_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO issuers (id, cvm_code, legal_name, trade_name, cnpj, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (issuer_id, "IBOV", "Ibovespa Index", "IBOV", "00000000000000", "active"))

        sec_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO securities (id, issuer_id, ticker, security_class, is_primary, valid_from, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (sec_id, issuer_id, IBOV_TICKER, "INDEX", True, "2000-01-01"))

        print(f"Created ^BVSP issuer ({issuer_id}) and security ({sec_id})")

    conn.commit()

    # 2. Clear existing IBOV snapshots
    cur.execute("""
        DELETE FROM market_snapshots WHERE security_id = %s
    """, (sec_id,))
    deleted = cur.rowcount
    print(f"Cleared {deleted} existing IBOV snapshots")

    # 3. Fetch IBOV historical from BRAPI
    print("Fetching IBOV data from BRAPI...")
    resp = httpx.get(
        f"{BRAPI_BASE_URL}/quote/%5EBVSP",
        params={"token": BRAPI_TOKEN, "range": "3mo", "interval": "1d"},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        print("ERROR: No IBOV data returned")
        sys.exit(1)

    prices = results[0].get("historicalDataPrice", [])
    print(f"Got {len(prices)} data points")

    # 4. Insert snapshots
    insert_sql = """
        INSERT INTO market_snapshots (id, security_id, source, price, market_cap, volume, currency, fetched_at, raw_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    batch = []
    for p in prices:
        ts = p.get("date")
        if not ts:
            continue
        close = p.get("close")
        volume = p.get("volume")
        if close is None:
            continue

        fetched_at = datetime.fromtimestamp(ts, tz=timezone.utc)
        batch.append((
            str(uuid.uuid4()), sec_id, "brapi",
            round(float(close), 2), None,
            round(float(volume), 0) if volume else None,
            "BRL", fetched_at.isoformat(), "{}",
        ))

    cur.executemany(insert_sql, batch)
    conn.commit()

    # 5. Verify
    cur.execute("""
        SELECT COUNT(*), MIN(fetched_at)::date, MAX(fetched_at)::date
        FROM market_snapshots WHERE security_id = %s
    """, (sec_id,))
    count, min_date, max_date = cur.fetchone()

    print(f"\nIBOV benchmark seeded:")
    print(f"  Snapshots: {count}")
    print(f"  Range:     {min_date} -> {max_date}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
