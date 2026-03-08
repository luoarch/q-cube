"""brapi.dev provider adapter — secondary for market data / enrichment."""

from __future__ import annotations

import logging

import httpx

from q3_fundamentals_engine.config import BRAPI_BASE_URL, BRAPI_TOKEN
from q3_fundamentals_engine.providers.base import (
    DownloadedFile,
    FundamentalsProviderAdapter,
    MarketSnapshotData,
    OHLCVRecord,
)

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class BrapiProviderAdapter(FundamentalsProviderAdapter):
    """Adapter for brapi.dev market data.

    brapi is quote-centric (keyed by ticker), so it does not provide
    filings or cadastro. It's only used for market data enrichment.
    """

    async def download_filings(self, year: int, doc_types: list[str]) -> list[DownloadedFile]:
        raise NotImplementedError("brapi does not provide filing downloads")

    async def download_cadastro(self) -> list[dict[str, str]]:
        raise NotImplementedError("brapi does not provide cadastro data")

    async def get_quote(self, ticker: str) -> dict | None:
        """Fetch quote data for a ticker."""
        url = f"{BRAPI_BASE_URL}/quote/{ticker}"
        params: dict[str, str] = {}
        if BRAPI_TOKEN:
            params["token"] = BRAPI_TOKEN

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning("brapi quote failed for %s: %d", ticker, resp.status_code)
                return None
            data = resp.json()
            results = data.get("results", [])
            return results[0] if results else None

    async def get_market_cap(self, ticker: str) -> float | None:
        """Get market cap for a ticker."""
        quote = await self.get_quote(ticker)
        if quote is None:
            return None
        return quote.get("marketCap")

    # -- MarketSnapshotProvider protocol methods --

    async def get_snapshot(self, ticker: str) -> MarketSnapshotData | None:
        """Return a normalized market snapshot from brapi quote data."""
        quote = await self.get_quote(ticker)
        if not quote or quote.get("regularMarketPrice") is None:
            return None
        return MarketSnapshotData(
            ticker=ticker,
            price=quote.get("regularMarketPrice"),
            market_cap=quote.get("marketCap"),
            volume=quote.get("regularMarketVolume"),
            currency=quote.get("currency", "BRL"),
            raw_json=quote,
        )

    async def get_snapshots_batch(self, tickers: list[str]) -> list[MarketSnapshotData]:
        """Fetch snapshots for multiple tickers; skip failures."""
        results: list[MarketSnapshotData] = []
        for ticker in tickers:
            try:
                snap = await self.get_snapshot(ticker)
                if snap is not None:
                    results.append(snap)
            except Exception:
                logger.warning("brapi snapshot failed for %s", ticker, exc_info=True)
        return results

    async def get_historical(self, ticker: str, *, period: str = "3mo", interval: str = "1d") -> list[OHLCVRecord]:
        """Not implemented — use Yahoo adapter for historical data."""
        raise NotImplementedError("brapi historical not implemented — use Yahoo adapter")
