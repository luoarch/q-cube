"""Yahoo Finance market snapshot adapter via yfinance."""

from __future__ import annotations

import asyncio
import logging

from q3_fundamentals_engine.providers.base import (
    MarketSnapshotData,
    OHLCVRecord,
    YahooInfoPayload,
)

logger = logging.getLogger(__name__)


def to_yahoo_ticker(b3_ticker: str) -> str:
    """Convert a B3 ticker to Yahoo Finance format.

    Indices (starting with ^) are passed through unchanged.
    Regular tickers get the .SA suffix for the Sao Paulo exchange.
    """
    if b3_ticker.startswith("^"):
        return b3_ticker
    return f"{b3_ticker}.SA"


def _parse_snapshot(ticker: str, info: YahooInfoPayload) -> MarketSnapshotData | None:
    """Parse a YahooInfoPayload into a MarketSnapshotData.

    Returns None when no usable price exists.
    """
    if info.get("regularMarketPrice") is None:
        return None
    return MarketSnapshotData(
        ticker=ticker,
        price=info.get("regularMarketPrice") or info.get("currentPrice"),
        market_cap=info.get("marketCap"),
        volume=info.get("regularMarketVolume"),
        currency=info.get("currency", "BRL"),
        raw_json=dict(info),
        shares_outstanding=info.get("sharesOutstanding"),
    )


class YahooSnapshotAdapter:
    """Yahoo Finance market snapshot adapter. yfinance is ONLY imported here."""

    async def get_snapshot(self, ticker: str) -> MarketSnapshotData | None:
        yahoo_ticker = to_yahoo_ticker(ticker)
        try:
            info = await asyncio.to_thread(self._fetch_info, yahoo_ticker)
        except Exception:
            logger.warning("yahoo snapshot failed for %s", ticker, exc_info=True)
            return None
        if not info:
            return None
        return _parse_snapshot(ticker, info)

    async def get_snapshots_batch(self, tickers: list[str]) -> list[MarketSnapshotData]:
        results: list[MarketSnapshotData] = []
        for ticker in tickers:
            try:
                snapshot = await self.get_snapshot(ticker)
                if snapshot is not None:
                    results.append(snapshot)
            except Exception:
                logger.warning("yahoo snapshot failed for %s", ticker, exc_info=True)
        return results

    async def get_historical(self, ticker: str, *, period: str = "3mo", interval: str = "1d") -> list[OHLCVRecord]:
        yahoo_ticker = to_yahoo_ticker(ticker)
        return await asyncio.to_thread(self._fetch_historical, yahoo_ticker, period, interval)

    def _fetch_info(self, yahoo_ticker: str) -> YahooInfoPayload | None:
        import yfinance as yf

        try:
            raw = yf.Ticker(yahoo_ticker).info
            return YahooInfoPayload(**{k: v for k, v in raw.items() if k in YahooInfoPayload.__annotations__})
        except Exception:
            logger.warning("yfinance info failed for %s", yahoo_ticker, exc_info=True)
            return None

    def _fetch_historical(self, yahoo_ticker: str, period: str, interval: str) -> list[OHLCVRecord]:
        import yfinance as yf

        try:
            df = yf.Ticker(yahoo_ticker).history(period=period, interval=interval)
            if df.empty:
                return []
            records: list[OHLCVRecord] = []
            for idx, row in df.iterrows():
                records.append(OHLCVRecord(
                    date=idx.isoformat(),
                    open=row.get("Open"),
                    high=row.get("High"),
                    low=row.get("Low"),
                    close=row.get("Close"),
                    volume=row.get("Volume"),
                ))
            return records
        except Exception:
            logger.warning("yfinance history failed for %s", yahoo_ticker, exc_info=True)
            return []
