"""B3 COTAHIST market snapshot adapter.

Bulk-first: downloads COTAHIST once, parses all tickers, caches result.
market_cap derived: B3 close_price × CVM net_shares.

Follows MarketSnapshotProvider protocol.
"""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import date

import httpx

from q3_fundamentals_engine.providers.b3.parser import CotahistRecord, parse_cotahist
from q3_fundamentals_engine.providers.base import MarketSnapshotData

logger = logging.getLogger(__name__)

# B3 COTAHIST URLs
_ANNUAL_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
_DAILY_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{ddmmyyyy}.ZIP"


def _download_cotahist_annual(year: int) -> str:
    """Download annual COTAHIST ZIP and return text content."""
    url = _ANNUAL_URL.format(year=year)
    logger.info("Downloading COTAHIST %d from %s", year, url)
    resp = httpx.get(url, timeout=180, follow_redirects=True, verify=False)
    resp.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    with z.open(z.namelist()[0]) as f:
        text = f.read().decode("latin-1")
    logger.info("COTAHIST %d: %d bytes", year, len(text))
    return text


def _download_cotahist_daily(target_date: date) -> str | None:
    """Download daily COTAHIST. Returns None if not available yet."""
    ddmmyyyy = target_date.strftime("%d%m%Y")
    url = _DAILY_URL.format(ddmmyyyy=ddmmyyyy)
    logger.info("Downloading daily COTAHIST %s from %s", target_date, url)
    try:
        resp = httpx.get(url, timeout=60, follow_redirects=True, verify=False)
        if resp.status_code == 404:
            logger.info("Daily COTAHIST not available yet for %s", target_date)
            return None
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Daily COTAHIST download failed for %s", target_date, exc_info=True)
        return None

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    with z.open(z.namelist()[0]) as f:
        return f.read().decode("latin-1")


def parse_annual(year: int) -> list[CotahistRecord]:
    """Download and parse full annual COTAHIST."""
    text = _download_cotahist_annual(year)
    return parse_cotahist(text)


def parse_daily(target_date: date) -> list[CotahistRecord] | None:
    """Download and parse daily COTAHIST. Returns None if unavailable."""
    text = _download_cotahist_daily(target_date)
    if text is None:
        return None
    return parse_cotahist(text)


def get_latest_close(
    records: list[CotahistRecord],
    ticker: str,
) -> CotahistRecord | None:
    """Get the most recent CotahistRecord for a ticker from parsed records."""
    ticker_records = [r for r in records if r.ticker == ticker]
    if not ticker_records:
        return None
    return max(ticker_records, key=lambda r: r.date)


def build_snapshot_data(
    record: CotahistRecord,
    derived_market_cap: float | None = None,
    shares_quarter: str | None = None,
) -> MarketSnapshotData:
    """Convert CotahistRecord to MarketSnapshotData with derived market_cap."""
    raw = {
        "source": "b3_cotahist",
        "price_source": "COTAHIST PREULT",
        "close": record.close,
        "open": record.open,
        "high": record.high,
        "low": record.low,
        "volume_brl": record.volume,
        "n_trades": record.n_trades,
        "quantity": record.quantity,
        "date": str(record.date),
    }

    if derived_market_cap is not None:
        raw["derivation"] = "close × CVM net_shares"
        raw["shares_source"] = "CVM composicao_capital"
        if shares_quarter:
            raw["shares_quarter"] = shares_quarter

    return MarketSnapshotData(
        ticker=record.ticker,
        price=record.close,
        market_cap=derived_market_cap,
        volume=record.volume,
        currency="BRL",
        shares_outstanding=None,  # Not in COTAHIST — shares come from CVM
        raw_json=raw,
    )
