"""brapi.dev API client — secondary source for market data and enrichment.

API docs: https://brapi.dev/docs
Quote-centric model: endpoints keyed by ticker.

Plan limits (affects which methods are usable):
┌────────────┬──────────────┬─────────────┬──────────┬──────────────────────┐
│ Plan       │ Req/month    │ Assets/req  │ History  │ Fundamentals (BP/DRE)│
├────────────┼──────────────┼─────────────┼──────────┼──────────────────────┤
│ Gratuito   │ 15,000       │ 1           │ 3 months │ NO                   │
│ Startup    │ 150,000      │ 10          │ 1 year   │ YES (annual)         │
│ Pro        │ 500,000      │ 20          │ 10+ yrs  │ YES (since 2009)     │
└────────────┴──────────────┴─────────────┴──────────┴──────────────────────┘

On the free plan, only these methods work:
  - list_stocks()     → asset listing with sector (basic data)
  - get_quote()       → price, marketCap, volume (30-min delay)
  - get_historical()  → max 3 months of OHLCV

These require Startup+ plan:
  - get_fundamentals() → modules (BP, DRE, DFC, financialData, keyStatistics)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from q3_market_ingestion.config import BRAPI_BASE_URL, BRAPI_TOKEN

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Free plan: max 3 months of historical data
FREE_PLAN_MAX_HISTORY = "3mo"


def _params(**extra: Any) -> dict[str, Any]:
    p: dict[str, Any] = {}
    if BRAPI_TOKEN:
        p["token"] = BRAPI_TOKEN
    p.update(extra)
    return p


async def list_stocks(
    *,
    stock_type: str = "stock",
    limit: int = 999,
) -> list[dict[str, Any]]:
    """GET /quote/list — list all B3 stocks with sector info.

    Available on all plans (free included).
    Returns basic data: ticker, name, sector, type.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{BRAPI_BASE_URL}/quote/list",
            params=_params(type=stock_type, limit=limit),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("stocks", [])  # type: ignore[no-any-return]


async def get_quote(ticker: str) -> dict[str, Any] | None:
    """GET /quote/{ticker} — current price, market cap, volume.

    Available on all plans (free included). 1 asset per request on free.
    Data delay: ~30min (free), ~15min (startup), ~5min (pro).
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{BRAPI_BASE_URL}/quote/{ticker}",
            params=_params(),
        )
        if resp.status_code != 200:
            logger.warning("brapi quote %s returned %d", ticker, resp.status_code)
            return None
        results = resp.json().get("results", [])
        return results[0] if results else None  # type: ignore[no-any-return]


async def get_fundamentals(
    ticker: str,
    *,
    modules: str = "defaultKeyStatistics,financialData,summaryProfile",
) -> dict[str, Any] | None:
    """GET /quote/{ticker}?modules=... — fundamental data modules.

    REQUIRES Startup+ plan. Will return None on free plan (HTTP 400/402).

    Available modules (paid plans only):
      - defaultKeyStatistics: enterpriseValue, forwardPE, priceToBook
      - financialData: ebitda, totalDebt, returnOnEquity, profitMargins
      - summaryProfile: sector, industry, longBusinessSummary
      - balanceSheetHistory: totalCurrentAssets, currentLiabilities, PP&E
      - incomeStatementHistory: ebit, totalRevenue, grossProfit
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{BRAPI_BASE_URL}/quote/{ticker}",
            params=_params(modules=modules),
        )
        if resp.status_code != 200:
            logger.warning("brapi fundamentals %s returned %d (paid plan required?)", ticker, resp.status_code)
            return None
        results = resp.json().get("results", [])
        return results[0] if results else None  # type: ignore[no-any-return]


async def get_historical(
    ticker: str,
    *,
    time_range: str = FREE_PLAN_MAX_HISTORY,
    interval: str = "1d",
) -> list[dict[str, Any]]:
    """GET /quote/{ticker}?range=...&interval=... — OHLCV history.

    Free plan: max 3 months. Startup: 1 year. Pro: 10+ years.
    Default range is 3mo (safe for all plans).
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{BRAPI_BASE_URL}/quote/{ticker}",
            params=_params(range=time_range, interval=interval),
        )
        if resp.status_code != 200:
            logger.warning("brapi historical %s returned %d", ticker, resp.status_code)
            return []
        results = resp.json().get("results", [])
        if not results:
            return []
        return results[0].get("historicalDataPrice", [])  # type: ignore[no-any-return]
