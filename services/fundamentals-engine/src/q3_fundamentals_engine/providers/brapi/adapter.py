"""brapi.dev provider adapter — secondary for market data / enrichment."""

from __future__ import annotations

import logging

import httpx

from q3_fundamentals_engine.config import BRAPI_BASE_URL, BRAPI_TOKEN
from q3_fundamentals_engine.providers.base import (
    DownloadedFile,
    FundamentalsProviderAdapter,
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
