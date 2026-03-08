"""Factory for market snapshot providers — resolves source from config."""

from __future__ import annotations

from q3_fundamentals_engine.config import MARKET_SNAPSHOT_SOURCE
from q3_fundamentals_engine.providers.base import MarketSnapshotProvider
from q3_fundamentals_engine.providers.yahoo.adapter import YahooSnapshotAdapter


_PROVIDERS: dict[str, type] = {
    "yahoo": YahooSnapshotAdapter,
}


def _ensure_brapi_registered() -> None:
    """Lazily register BrapiSnapshotAdapter if not already present."""
    if "brapi" not in _PROVIDERS:
        from q3_fundamentals_engine.providers.brapi.adapter import BrapiProviderAdapter

        _PROVIDERS["brapi"] = BrapiProviderAdapter


class MarketSnapshotProviderFactory:
    """Creates market snapshot provider instances based on config."""

    @classmethod
    def create(cls, source: str | None = None) -> MarketSnapshotProvider:
        source = source or MARKET_SNAPSHOT_SOURCE
        _ensure_brapi_registered()
        if source not in _PROVIDERS:
            raise ValueError(f"Unknown market snapshot source: {source}")
        return _PROVIDERS[source]()
