"""Backfill historical market snapshots 2020-2022 at monthly cadence.

Uses yfinance for price/volume, CVM composicao_capital for PIT-correct shares.
Market cap derived as Close × net_shares.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/backfill_historical_snapshots.py
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import time
import uuid
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
from sqlalchemy import select, text

from q3_fundamentals_engine.db.session import SessionLocal
from q3_shared_models.entities import (
    MarketSnapshot,
    Security,
    SourceProvider,
    UniverseClassification,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_snapshots")


# ---------------------------------------------------------------------------
# Target dates: first business day of each month, 2020-01 through 2022-12
# ---------------------------------------------------------------------------

def _generate_monthly_targets(start_year: int, end_year: int) -> list[date]:
    targets = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            d = date(year, month, 1)
            while d.weekday() >= 5:
                d += timedelta(days=1)
            targets.append(d)
    return targets


TARGETS = _generate_monthly_targets(2020, 2022)


# ---------------------------------------------------------------------------
# CVM composicao_capital loader (PIT-correct shares)
# ---------------------------------------------------------------------------

@dataclass
class ShareEntry:
    cnpj: str
    reference_date: date
    publication_date: date  # synthetic: DFP+90d, ITR+45d
    total_shares: int
    treasury_shares: int
    net_shares: int


def _normalize_cnpj(cnpj: str) -> str:
    return re.sub(r"[^0-9]", "", cnpj)


def _load_composicao_capital() -> dict[str, list[ShareEntry]]:
    """Download and parse composicao_capital from CVM for 2019-2022."""
    result: dict[str, list[ShareEntry]] = defaultdict(list)
    base = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"

    sources = [
        ("DFP", 2020), ("ITR", 2020),
        ("DFP", 2021), ("ITR", 2021),
        ("DFP", 2022), ("ITR", 2022),
        ("DFP", 2023), ("ITR", 2023),  # for PIT at late 2022
    ]

    for doc_type, year in sources:
        url = f"{base}/{doc_type}/DADOS/{doc_type.lower()}_cia_aberta_{year}.zip"
        logger.info("Loading composicao_capital from %s %d", doc_type, year)
        try:
            resp = httpx.get(url, timeout=120, verify=False, follow_redirects=True)
            resp.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(resp.content))
            for name in z.namelist():
                if "composicao_capital" not in name.lower():
                    continue
                with z.open(name) as f:
                    data = f.read().decode("latin-1")
                    reader = csv.DictReader(io.StringIO(data), delimiter=";")
                    for row in reader:
                        cnpj = _normalize_cnpj(row.get("CNPJ_CIA", ""))
                        if not cnpj:
                            continue
                        try:
                            ref = date.fromisoformat(row["DT_REFER"])
                            total = int(row.get("QT_ACAO_TOTAL_CAP_INTEGR", "0") or "0")
                            treasury = int(row.get("QT_ACAO_TOTAL_TESOURO", "0") or "0")
                        except (ValueError, KeyError):
                            continue
                        if total <= 0:
                            continue
                        # Synthetic publication_date
                        if doc_type == "DFP":
                            pub = ref + timedelta(days=90)
                        else:
                            pub = ref + timedelta(days=45)
                        result[cnpj].append(ShareEntry(
                            cnpj=cnpj, reference_date=ref,
                            publication_date=pub,
                            total_shares=total, treasury_shares=treasury,
                            net_shares=total - treasury,
                        ))
        except Exception:
            logger.warning("Failed to load %s %d", doc_type, year, exc_info=True)

    # Sort each issuer's entries by reference_date
    for cnpj in result:
        result[cnpj].sort(key=lambda e: e.reference_date)

    logger.info("Loaded composicao_capital for %d companies", len(result))
    return result


def _find_pit_shares(entries: list[ShareEntry], as_of: date) -> ShareEntry | None:
    """Find latest PIT-correct shares: reference_date <= as_of AND publication_date <= as_of."""
    best = None
    for e in entries:
        if e.reference_date <= as_of and e.publication_date <= as_of:
            if best is None or e.reference_date > best.reference_date:
                best = e
    return best


# ---------------------------------------------------------------------------
# yfinance historical fetch
# ---------------------------------------------------------------------------

def _fetch_history(ticker: str, start: date, end: date):
    """Fetch daily OHLCV from yfinance."""
    import yfinance as yf
    yahoo = f"{ticker}.SA" if not ticker.startswith("^") else ticker
    try:
        df = yf.Ticker(yahoo).history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
        )
        return df if df is not None and not df.empty else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Load shares data
    shares_data = _load_composicao_capital()

    # Load Core tickers with CNPJ
    with SessionLocal() as session:
        tickers_info = session.execute(text("""
            SELECT se.id, se.ticker, i.cnpj
            FROM securities se
            JOIN issuers i ON i.id = se.issuer_id
            JOIN universe_classifications uc ON uc.issuer_id = i.id
                AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
            WHERE se.is_primary = true AND se.valid_to IS NULL
        """)).fetchall()

    ticker_map = {row[1]: {"sec_id": row[0], "cnpj": row[1 + 1]} for row in tickers_info}
    # Fix: map by ticker
    ticker_map = {}
    for sec_id, ticker, cnpj in tickers_info:
        ticker_map[ticker] = {"sec_id": sec_id, "cnpj": cnpj}

    logger.info("Core tickers: %d", len(ticker_map))

    # Fetch full 3-year history per ticker, then extract monthly snapshots
    created = 0
    skipped_no_data = 0
    skipped_no_shares = 0
    total_tickers = len(ticker_map)

    with SessionLocal() as session:
        for idx, (ticker, info) in enumerate(ticker_map.items(), 1):
            if idx % 50 == 0:
                logger.info("Progress: %d/%d tickers", idx, total_tickers)
                session.commit()

            # Fetch full history 2020-01 to 2023-01
            df = _fetch_history(ticker, date(2019, 12, 1), date(2023, 1, 31))
            if df is None:
                skipped_no_data += 1
                continue

            cnpj = info["cnpj"]
            sec_id = info["sec_id"]
            issuer_shares = shares_data.get(cnpj, [])

            for target in TARGETS:
                # Find price: latest trading day on or before target
                mask = df.index <= str(target)
                if not mask.any():
                    continue
                price_row = df[mask].iloc[-1]
                price_date = price_row.name.date() if hasattr(price_row.name, "date") else price_row.name
                close_price = float(price_row.get("Close", 0))
                raw_volume = float(price_row.get("Volume", 0))

                if close_price <= 0:
                    continue

                # PIT-correct shares
                shares_entry = _find_pit_shares(issuer_shares, price_date) if issuer_shares else None
                if shares_entry:
                    market_cap = close_price * shares_entry.net_shares
                    shares_outstanding = shares_entry.net_shares
                    shares_provenance = {
                        "source": "CVM_composicao_capital",
                        "reference_date": str(shares_entry.reference_date),
                        "publication_date": str(shares_entry.publication_date),
                        "total_shares": shares_entry.total_shares,
                        "treasury_shares": shares_entry.treasury_shares,
                        "net_shares": shares_entry.net_shares,
                    }
                    pit_compliant = True
                else:
                    market_cap = None
                    shares_outstanding = None
                    shares_provenance = None
                    pit_compliant = False
                    skipped_no_shares += 1

                # Compute avg_traded_value_21d for audit (NOT stored in volume column)
                window_start = price_date - timedelta(days=35)
                mask_window = (df.index >= str(window_start)) & (df.index <= str(price_date))
                window_df = df[mask_window].tail(21)
                avg_traded_value = None
                if len(window_df) >= 5:
                    traded_values = window_df["Close"] * window_df["Volume"]
                    avg_traded_value = float(traded_values.mean())

                # Build provenance
                raw_json = {
                    "source_components": {
                        "price": {
                            "source": "yfinance",
                            "field": "Close",
                            "price_date": str(price_date),
                            "target_date": str(target),
                        },
                        "volume": {
                            "source": "yfinance",
                            "field": "Volume",
                            "price_date": str(price_date),
                            "raw_share_volume": raw_volume,
                        },
                    },
                    "shares": shares_provenance,
                    "market_cap": {
                        "formula": "close_price * net_shares",
                        "value": market_cap,
                    } if market_cap else None,
                    "avg_traded_value_21d": {
                        "method": "rolling_mean(Close*Volume, 21d)",
                        "window_end": str(price_date),
                        "value": avg_traded_value,
                        "note": "audit only, not stored in volume column",
                    } if avg_traded_value else None,
                    "pit_compliant": pit_compliant,
                    "derivation": "historical_backfill_v1",
                }

                snapshot = MarketSnapshot(
                    id=uuid.uuid4(),
                    security_id=sec_id,
                    source=SourceProvider.yahoo,
                    price=close_price,
                    market_cap=market_cap,
                    volume=raw_volume,
                    shares_outstanding=shares_outstanding,
                    fetched_at=price_date,  # actual observation date
                    raw_json=raw_json,
                )
                session.add(snapshot)
                created += 1

            time.sleep(0.3)  # rate limiting

        session.commit()

    logger.info("Done: created=%d, no_yahoo=%d, no_shares_instances=%d", created, skipped_no_data, skipped_no_shares)

    # Summary
    print(f"\n{'=' * 60}")
    print("HISTORICAL SNAPSHOT BACKFILL SUMMARY")
    print(f"{'=' * 60}")
    print(f"Tickers processed: {total_tickers}")
    print(f"Snapshots created: {created}")
    print(f"Tickers with no Yahoo data: {skipped_no_data}")
    print(f"Snapshot instances with no PIT shares: {skipped_no_shares}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
