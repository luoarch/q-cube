"""Tests for the market snapshot provider factory."""

from __future__ import annotations

import pytest

from q3_fundamentals_engine.providers.base import MarketSnapshotProvider
from q3_fundamentals_engine.providers.market_snapshot_factory import (
    MarketSnapshotProviderFactory,
)
from q3_fundamentals_engine.providers.yahoo.adapter import YahooSnapshotAdapter


def test_factory_creates_yahoo():
    provider = MarketSnapshotProviderFactory.create("yahoo")
    assert isinstance(provider, YahooSnapshotAdapter)


def test_factory_creates_brapi():
    from q3_fundamentals_engine.providers.brapi.adapter import BrapiProviderAdapter

    provider = MarketSnapshotProviderFactory.create("brapi")
    assert isinstance(provider, BrapiProviderAdapter)


def test_factory_invalid_source():
    with pytest.raises(ValueError, match="Unknown market snapshot source"):
        MarketSnapshotProviderFactory.create("nonexistent")


def test_factory_default_source_is_yahoo():
    """create(None) should default to Yahoo (MARKET_SNAPSHOT_SOURCE='yahoo')."""
    provider = MarketSnapshotProviderFactory.create(None)
    assert isinstance(provider, YahooSnapshotAdapter)


def test_factory_brapi_idempotent():
    """Creating brapi adapter twice should work without error."""
    p1 = MarketSnapshotProviderFactory.create("brapi")
    p2 = MarketSnapshotProviderFactory.create("brapi")
    assert type(p1) == type(p2)


def test_brapi_adapter_implements_protocol():
    """BrapiProviderAdapter must have all MarketSnapshotProvider methods."""
    from q3_fundamentals_engine.providers.brapi.adapter import BrapiProviderAdapter

    adapter = BrapiProviderAdapter()
    assert hasattr(adapter, "get_snapshot")
    assert hasattr(adapter, "get_snapshots_batch")
    assert hasattr(adapter, "get_historical")
    assert callable(adapter.get_snapshot)
    assert callable(adapter.get_snapshots_batch)
    assert callable(adapter.get_historical)


def test_yahoo_adapter_implements_protocol():
    """YahooSnapshotAdapter must have all MarketSnapshotProvider methods."""
    adapter = YahooSnapshotAdapter()
    assert hasattr(adapter, "get_snapshot")
    assert hasattr(adapter, "get_snapshots_batch")
    assert hasattr(adapter, "get_historical")
    assert callable(adapter.get_snapshot)
    assert callable(adapter.get_snapshots_batch)
    assert callable(adapter.get_historical)
