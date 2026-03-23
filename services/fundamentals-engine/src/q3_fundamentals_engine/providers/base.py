from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict


@dataclass
class DownloadedFile:
    """Represents a downloaded raw file with integrity metadata."""

    filename: str
    url: str
    content: bytes
    sha256_hash: str
    size_bytes: int


class FundamentalsProviderAdapter(abc.ABC):
    """Abstract adapter for fundamentals data providers (CVM, brapi, etc.)."""

    @abc.abstractmethod
    async def download_filings(
        self, year: int, doc_types: list[str]
    ) -> list[DownloadedFile]: ...

    @abc.abstractmethod
    async def download_cadastro(self) -> list[dict[str, str]]: ...


# ---------------------------------------------------------------------------
# Market snapshot protocol — separate from FundamentalsProviderAdapter
# because market data and filing data have completely different interfaces.
# ---------------------------------------------------------------------------


class YahooInfoPayload(TypedDict, total=False):
    """Shape of yfinance Ticker.info dict — fields the Q3 adapter reads.

    yfinance is community-maintained; fields may appear/disappear.
    Only keys consumed by Q3 are listed. ``total=False`` because every
    key is optional in practice (partial payloads are common).
    """

    regularMarketPrice: float | None
    currentPrice: float | None
    marketCap: float | int | None
    regularMarketVolume: float | int | None
    sharesOutstanding: float | int | None
    currency: str
    symbol: str
    shortName: str
    longName: str
    quoteType: str
    exchange: str


@dataclass(frozen=True, slots=True)
class OHLCVRecord:
    """Single OHLCV data point returned by ``get_historical``."""

    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | int | None


@dataclass
class MarketSnapshotData:
    """Normalized market snapshot from any provider."""

    ticker: str
    price: float | None
    market_cap: float | None
    volume: float | None
    currency: str
    raw_json: dict[str, Any]
    shares_outstanding: float | int | None = None


class MarketSnapshotProvider(Protocol):
    """Protocol for market snapshot data providers (Yahoo, BRAPI, etc.)."""

    async def get_snapshot(self, ticker: str) -> MarketSnapshotData | None: ...

    async def get_snapshots_batch(self, tickers: list[str]) -> list[MarketSnapshotData]: ...

    async def get_historical(self, ticker: str, *, period: str, interval: str) -> list[OHLCVRecord]: ...
