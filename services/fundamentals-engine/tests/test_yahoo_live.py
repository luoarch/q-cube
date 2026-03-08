"""Live smoke tests -- real Yahoo Finance API.

Run manually: pytest tests/test_yahoo_live.py -v -m live
NOT included in CI by default.
"""

from __future__ import annotations

import asyncio

import pytest

from q3_fundamentals_engine.providers.yahoo.adapter import YahooSnapshotAdapter

pytestmark = pytest.mark.live


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def adapter():
    return YahooSnapshotAdapter()


class TestYahooLive:
    def test_petr4_snapshot(self, adapter):
        result = _run(adapter.get_snapshot("PETR4"))
        assert result is not None
        assert result.ticker == "PETR4"
        assert result.price > 0
        assert result.market_cap > 1e9

    def test_ibov_index(self, adapter):
        result = _run(adapter.get_snapshot("^BVSP"))
        assert result is not None
        assert result.price > 50_000

    def test_invalid_ticker(self, adapter):
        result = _run(adapter.get_snapshot("XYZINVALID99"))
        assert result is None

    def test_historical_petr4(self, adapter):
        records = _run(adapter.get_historical("PETR4", period="5d", interval="1d"))
        assert len(records) >= 3
        assert records[0].close > 0

    def test_batch_mixed(self, adapter):
        results = _run(adapter.get_snapshots_batch(["PETR4", "XYZINVALID99", "VALE3"]))
        tickers = [r.ticker for r in results]
        assert "PETR4" in tickers
        assert "VALE3" in tickers
        assert "XYZINVALID99" not in tickers
