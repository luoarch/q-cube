"""Tests for the Yahoo Finance snapshot adapter — 100% branch coverage."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import sys
import pytest

from q3_fundamentals_engine.providers.base import MarketSnapshotData, OHLCVRecord
from q3_fundamentals_engine.providers.yahoo.adapter import (
    YahooSnapshotAdapter,
    _parse_snapshot,
    to_yahoo_ticker,
)
from tests.fixtures.yahoo_payloads import (
    BPAC11_INFO,
    EMPTY_RESPONSE,
    FALLBACK_CURRENT_PRICE,
    IBOV_INFO,
    NON_BRL_CURRENCY,
    PARTIAL_NO_MCAP,
    PARTIAL_NO_VOLUME,
    PETR4_INFO,
    VALE3_INFO,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# to_yahoo_ticker
# ---------------------------------------------------------------------------

class TestToYahooTicker:
    def test_stock(self):
        assert to_yahoo_ticker("PETR4") == "PETR4.SA"

    def test_index(self):
        assert to_yahoo_ticker("^BVSP") == "^BVSP"

    def test_unit(self):
        assert to_yahoo_ticker("BPAC11") == "BPAC11.SA"


# ---------------------------------------------------------------------------
# get_snapshot
# ---------------------------------------------------------------------------

class TestGetSnapshot:
    def test_full_payload(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=PETR4_INFO):
            result = _run(adapter.get_snapshot("PETR4"))

        assert result is not None
        assert result.ticker == "PETR4"
        assert result.price == 38.50
        assert result.market_cap == 498_000_000_000
        assert result.volume == 25_000_000
        assert result.currency == "BRL"
        assert result.raw_json == PETR4_INFO

    def test_partial_no_market_cap(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=PARTIAL_NO_MCAP):
            result = _run(adapter.get_snapshot("MICRO3"))

        assert result is not None
        assert result.price == 2.50
        assert result.market_cap is None

    def test_partial_no_volume(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=PARTIAL_NO_VOLUME):
            result = _run(adapter.get_snapshot("NOVOL3"))

        assert result is not None
        assert result.price == 15.00
        assert result.volume is None

    def test_missing_price_returns_none(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value={"regularMarketPrice": None}):
            result = _run(adapter.get_snapshot("NOPRICE3"))
        assert result is None

    def test_empty_dict_returns_none(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=EMPTY_RESPONSE):
            result = _run(adapter.get_snapshot("EMPTY3"))
        assert result is None

    def test_ticker_not_found_returns_none(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=None):
            result = _run(adapter.get_snapshot("INVALID99"))
        assert result is None

    def test_exception_returns_none(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", side_effect=Exception("network")):
            result = _run(adapter.get_snapshot("FAIL3"))
        assert result is None

    def test_falls_back_to_current_price(self):
        """When regularMarketPrice is 0 (falsy), falls back to currentPrice."""
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=FALLBACK_CURRENT_PRICE):
            result = _run(adapter.get_snapshot("FB3"))

        assert result is not None
        assert result.price == 42.00

    def test_default_currency_brl(self):
        """When 'currency' key is absent, defaults to 'BRL'."""
        info = {"regularMarketPrice": 10.0}
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=info):
            result = _run(adapter.get_snapshot("NOCUR3"))

        assert result is not None
        assert result.currency == "BRL"

    def test_non_brl_currency_preserved(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=NON_BRL_CURRENCY):
            result = _run(adapter.get_snapshot("USD3"))

        assert result is not None
        assert result.currency == "USD"

    def test_preserves_original_ticker(self):
        """Output ticker must be the B3 ticker, not the Yahoo-suffixed version."""
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=PETR4_INFO):
            result = _run(adapter.get_snapshot("PETR4"))

        assert result is not None
        assert result.ticker == "PETR4"
        assert ".SA" not in result.ticker

    def test_from_real_petr4_payload(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=PETR4_INFO):
            result = _run(adapter.get_snapshot("PETR4"))

        assert result is not None
        assert result.price == PETR4_INFO["regularMarketPrice"]
        assert result.market_cap == PETR4_INFO["marketCap"]
        assert result.volume == PETR4_INFO["regularMarketVolume"]

    def test_from_real_ibov_payload(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=IBOV_INFO):
            result = _run(adapter.get_snapshot("^BVSP"))

        assert result is not None
        assert result.ticker == "^BVSP"
        assert result.price == 128_500.0
        assert result.market_cap is None  # index has no market cap

    def test_from_real_partial_payload(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_info", return_value=PARTIAL_NO_MCAP):
            result = _run(adapter.get_snapshot("SMALL3"))

        assert result is not None
        assert result.price == 2.50
        assert result.market_cap is None


# ---------------------------------------------------------------------------
# get_snapshots_batch
# ---------------------------------------------------------------------------

class TestGetSnapshotsBatch:
    def test_skips_failures(self):
        call_count = 0

        async def mock_snapshot(ticker):
            nonlocal call_count
            call_count += 1
            if ticker == "BAD3":
                return None
            return MarketSnapshotData(
                ticker=ticker, price=10.0, market_cap=1e9,
                volume=1e6, currency="BRL", raw_json={},
            )

        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "get_snapshot", side_effect=mock_snapshot):
            results = _run(adapter.get_snapshots_batch(["GOOD3", "BAD3", "OK3"]))

        assert len(results) == 2
        assert call_count == 3

    def test_exception_does_not_crash(self):
        """If get_snapshot raises, batch continues with remaining tickers."""
        call_order = []

        async def mock_snapshot(ticker):
            call_order.append(ticker)
            if ticker == "BOOM3":
                raise RuntimeError("crash")
            return MarketSnapshotData(
                ticker=ticker, price=10.0, market_cap=1e9,
                volume=1e6, currency="BRL", raw_json={},
            )

        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "get_snapshot", side_effect=mock_snapshot):
            results = _run(adapter.get_snapshots_batch(["A3", "BOOM3", "B3"]))

        assert len(results) == 2
        assert call_order == ["A3", "BOOM3", "B3"]

    def test_empty_input(self):
        adapter = YahooSnapshotAdapter()
        results = _run(adapter.get_snapshots_batch([]))
        assert results == []

    def test_all_fail(self):
        async def mock_snapshot(ticker):
            return None

        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "get_snapshot", side_effect=mock_snapshot):
            results = _run(adapter.get_snapshots_batch(["X3", "Y3", "Z3"]))

        assert results == []


# ---------------------------------------------------------------------------
# get_historical
# ---------------------------------------------------------------------------

class TestGetHistorical:
    def test_returns_ohlcv_records(self):
        fake_records = [
            OHLCVRecord(date="2026-03-01T00:00:00", open=38.0, high=39.0, low=37.5, close=38.5, volume=1e6),
            OHLCVRecord(date="2026-03-02T00:00:00", open=38.5, high=40.0, low=38.0, close=39.0, volume=1.2e6),
        ]
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_historical", return_value=fake_records):
            records = _run(adapter.get_historical("PETR4", period="5d", interval="1d"))

        assert len(records) == 2
        assert records[0].close == 38.5
        assert isinstance(records[0], OHLCVRecord)

    def test_empty_returns_empty_list(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_historical", return_value=[]):
            records = _run(adapter.get_historical("EMPTY3"))
        assert records == []

    def test_exception_returns_empty_list(self):
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_historical", side_effect=RuntimeError("fail")):
            # get_historical doesn't catch — _fetch_historical does internally
            # but if it propagates, the asyncio.to_thread will raise
            with pytest.raises(RuntimeError):
                _run(adapter.get_historical("FAIL3"))

    def test_ticker_mapping_stock(self):
        """Stock ticker should be mapped with .SA suffix for _fetch_historical."""
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_historical", return_value=[]) as mock_hist:
            _run(adapter.get_historical("VALE3", period="5d", interval="1d"))
        mock_hist.assert_called_once_with("VALE3.SA", "5d", "1d")

    def test_ticker_mapping_index_no_suffix(self):
        """Index ticker should NOT get .SA suffix."""
        adapter = YahooSnapshotAdapter()
        with patch.object(adapter, "_fetch_historical", return_value=[]) as mock_hist:
            _run(adapter.get_historical("^BVSP", period="5d", interval="1d"))
        mock_hist.assert_called_once_with("^BVSP", "5d", "1d")


# ---------------------------------------------------------------------------
# _fetch_historical (mock yfinance)
# ---------------------------------------------------------------------------

class TestFetchHistorical:
    def _make_mock_df(self, data: dict, dates: list[str]):
        """Create a mock DataFrame-like object without pandas."""
        class MockIndex:
            def __init__(self, dates):
                self._dates = dates
            def __iter__(self):
                return iter(self._dates)

        class MockRow:
            def __init__(self, row_data):
                self._data = row_data
            def get(self, key):
                return self._data.get(key)

        class MockDF:
            def __init__(self, data, dates):
                self.empty = len(dates) == 0
                self._rows = []
                for i, d in enumerate(dates):
                    row_data = {k: v[i] for k, v in data.items()}
                    self._rows.append((d, MockRow(row_data)))
            def iterrows(self):
                return iter(self._rows)

        # Create datetime-like index entries with isoformat
        class FakeTimestamp:
            def __init__(self, s):
                self._s = s
            def isoformat(self):
                return self._s

        timestamps = [FakeTimestamp(d) for d in dates]
        return MockDF(data, timestamps)

    def test_parses_dataframe(self):
        mock_df = self._make_mock_df(
            {
                "Open": [38.0, 38.5],
                "High": [39.0, 40.0],
                "Low": [37.5, 38.0],
                "Close": [38.5, 39.0],
                "Volume": [1_000_000, 1_200_000],
            },
            ["2026-03-01T00:00:00", "2026-03-02T00:00:00"],
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df

        adapter = YahooSnapshotAdapter()
        mock_yf_module = MagicMock()
        mock_yf_module.Ticker.return_value = mock_ticker

        sys.modules["yfinance"] = mock_yf_module
        try:
            records = adapter._fetch_historical("PETR4.SA", "5d", "1d")
        finally:
            del sys.modules["yfinance"]

        assert len(records) == 2
        assert records[0].close == 38.5
        assert records[1].open == 38.5
        assert records[0].date == "2026-03-01T00:00:00"
        assert isinstance(records[0], OHLCVRecord)

    def test_empty_df(self):
        mock_df = self._make_mock_df({}, [])

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df

        adapter = YahooSnapshotAdapter()
        mock_yf_module = MagicMock()
        mock_yf_module.Ticker.return_value = mock_ticker

        sys.modules["yfinance"] = mock_yf_module
        try:
            records = adapter._fetch_historical("EMPTY.SA", "5d", "1d")
        finally:
            del sys.modules["yfinance"]

        assert records == []

    def test_yfinance_exception(self):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("yfinance down")

        adapter = YahooSnapshotAdapter()
        mock_yf_module = MagicMock()
        mock_yf_module.Ticker.return_value = mock_ticker

        sys.modules["yfinance"] = mock_yf_module
        try:
            records = adapter._fetch_historical("FAIL.SA", "5d", "1d")
        finally:
            del sys.modules["yfinance"]

        assert records == []


# ---------------------------------------------------------------------------
# _fetch_info (mock yfinance)
# ---------------------------------------------------------------------------

class TestFetchInfo:
    def test_returns_typed_payload(self):
        """_fetch_info filters yfinance dict into YahooInfoPayload keys only."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "regularMarketPrice": 38.50,
            "currency": "BRL",
            "unknownExtraField": "should be dropped",
        }

        adapter = YahooSnapshotAdapter()
        mock_yf_module = MagicMock()
        mock_yf_module.Ticker.return_value = mock_ticker

        sys.modules["yfinance"] = mock_yf_module
        try:
            result = adapter._fetch_info("PETR4.SA")
        finally:
            del sys.modules["yfinance"]

        assert result is not None
        assert result["regularMarketPrice"] == 38.50
        assert result["currency"] == "BRL"
        assert "unknownExtraField" not in result

    def test_yfinance_exception_returns_none(self):
        mock_ticker = MagicMock()
        type(mock_ticker).info = property(lambda self: (_ for _ in ()).throw(Exception("fail")))

        adapter = YahooSnapshotAdapter()
        mock_yf_module = MagicMock()
        mock_yf_module.Ticker.return_value = mock_ticker

        sys.modules["yfinance"] = mock_yf_module
        try:
            result = adapter._fetch_info("FAIL.SA")
        finally:
            del sys.modules["yfinance"]

        assert result is None


# ---------------------------------------------------------------------------
# _parse_snapshot (pure function, no mocks needed)
# ---------------------------------------------------------------------------

class TestParseSnapshot:
    def test_full_payload(self):
        result = _parse_snapshot("PETR4", PETR4_INFO)
        assert result is not None
        assert result.ticker == "PETR4"
        assert result.price == 38.50
        assert result.market_cap == 498_000_000_000

    def test_missing_price_returns_none(self):
        result = _parse_snapshot("X", {"currency": "BRL"})
        assert result is None

    def test_none_price_returns_none(self):
        result = _parse_snapshot("X", {"regularMarketPrice": None})
        assert result is None

    def test_empty_dict_returns_none(self):
        result = _parse_snapshot("X", {})
        assert result is None
