#!/usr/bin/env python3
"""Seed IBOV benchmark data from Yahoo Finance into market_snapshots.

Creates a pseudo-security for ^BVSP and inserts daily IBOV prices using yfinance.

Usage:
    python3 scripts/seed_yahoo_benchmark.py
"""

import os
import uuid
from datetime import timezone

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/q3")
IBOV_TICKER = "^BVSP"


def main():
    import yfinance as yf

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Check if ^BVSP security exists, create if not
    cur.execute("SELECT id FROM securities WHERE ticker = %s", (IBOV_TICKER,))
    row = cur.fetchone()

    if row:
        sec_id = row[0]
        print(f"Found existing ^BVSP security: {sec_id}")
    else:
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
    cur.execute("DELETE FROM market_snapshots WHERE security_id = %s", (sec_id,))
    deleted = cur.rowcount
    print(f"Cleared {deleted} existing IBOV snapshots")

    # 3. Fetch IBOV historical from Yahoo Finance
    print("Fetching IBOV data from Yahoo Finance...")
    df = yf.Ticker(IBOV_TICKER).history(period="3mo")
    if df.empty:
        print("ERROR: No IBOV data returned")
        cur.close()
        conn.close()
        return

    print(f"Got {len(df)} data points")

    # 4. Insert snapshots
    insert_sql = """
        INSERT INTO market_snapshots (id, security_id, source, price, market_cap, volume, currency, fetched_at, raw_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    batch = []
    for idx, row in df.iterrows():
        close = row.get("Close")
        volume = row.get("Volume")
        if close is None:
            continue

        fetched_at = idx.to_pydatetime().replace(tzinfo=timezone.utc)
        batch.append((
            str(uuid.uuid4()), sec_id, "yahoo",
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

    print(f"\nIBOV benchmark seeded (Yahoo/yfinance):")
    print(f"  Snapshots: {count}")
    print(f"  Range:     {min_date} -> {max_date}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
