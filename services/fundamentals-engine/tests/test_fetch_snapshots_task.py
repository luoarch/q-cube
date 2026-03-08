"""Integration tests for the fetch_market_snapshots Celery task.

Fully mocked — no DB or network required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from q3_fundamentals_engine.providers.base import MarketSnapshotData


def _make_snap_data(ticker: str, *, price: float = 38.5, market_cap: float | None = 500e9) -> MarketSnapshotData:
    return MarketSnapshotData(
        ticker=ticker,
        price=price,
        market_cap=market_cap,
        volume=25e6,
        currency="BRL",
        raw_json={"test": True},
    )


def _make_mock_security(ticker: str) -> MagicMock:
    sec = MagicMock()
    sec.id = uuid.uuid4()
    sec.ticker = ticker
    sec.is_primary = True
    return sec


def _make_mock_session(securities: list[MagicMock]) -> MagicMock:
    session = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = securities
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock
    session.execute.return_value = execute_result
    return session


class TestFetchSnapshotsTask:
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.compute_market_metrics")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MarketSnapshotProviderFactory")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.SessionLocal")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots._SOURCE_ENABLED", {"yahoo": True})
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MARKET_SNAPSHOT_SOURCE", "yahoo")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.time")
    def test_task_creates_snapshots_in_db(self, mock_time, mock_session_cls, mock_factory, mock_chain):
        secs = [_make_mock_security("PETR4"), _make_mock_security("VALE3")]
        mock_session = _make_mock_session(secs)
        mock_session_cls.return_value = mock_session

        mock_adapter = MagicMock()
        mock_factory.create.return_value = mock_adapter

        async def mock_get_snapshot(ticker):
            return _make_snap_data(ticker)

        mock_adapter.get_snapshot = mock_get_snapshot

        from q3_fundamentals_engine.tasks.fetch_snapshots import fetch_market_snapshots
        result = fetch_market_snapshots()

        assert result["snapshots_created"] == 2
        assert result["failures"] == 0
        assert result["source"] == "yahoo"
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_called_once()

    @patch("q3_fundamentals_engine.tasks.fetch_snapshots._SOURCE_ENABLED", {"yahoo": False})
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MARKET_SNAPSHOT_SOURCE", "yahoo")
    def test_task_skipped_when_disabled(self):
        from q3_fundamentals_engine.tasks.fetch_snapshots import fetch_market_snapshots
        result = fetch_market_snapshots()
        assert result["skipped"] is True

    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.compute_market_metrics")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MarketSnapshotProviderFactory")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.SessionLocal")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots._SOURCE_ENABLED", {"yahoo": True})
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MARKET_SNAPSHOT_SOURCE", "yahoo")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.time")
    def test_task_handles_adapter_failures(self, mock_time, mock_session_cls, mock_factory, mock_chain):
        secs = [_make_mock_security("PETR4"), _make_mock_security("FAIL3")]
        mock_session = _make_mock_session(secs)
        mock_session_cls.return_value = mock_session

        mock_adapter = MagicMock()
        mock_factory.create.return_value = mock_adapter

        async def mock_get_snapshot(ticker):
            if ticker == "FAIL3":
                return None
            return _make_snap_data(ticker)

        mock_adapter.get_snapshot = mock_get_snapshot

        from q3_fundamentals_engine.tasks.fetch_snapshots import fetch_market_snapshots
        result = fetch_market_snapshots()

        assert result["snapshots_created"] == 1
        assert result["failures"] == 1

    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.compute_market_metrics")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MarketSnapshotProviderFactory")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.SessionLocal")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots._SOURCE_ENABLED", {"yahoo": True})
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MARKET_SNAPSHOT_SOURCE", "yahoo")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.time")
    def test_task_null_market_cap_tracked(self, mock_time, mock_session_cls, mock_factory, mock_chain):
        secs = [_make_mock_security("MICRO3")]
        mock_session = _make_mock_session(secs)
        mock_session_cls.return_value = mock_session

        mock_adapter = MagicMock()
        mock_factory.create.return_value = mock_adapter

        async def mock_get_snapshot(ticker):
            return _make_snap_data(ticker, market_cap=None)

        mock_adapter.get_snapshot = mock_get_snapshot

        from q3_fundamentals_engine.tasks.fetch_snapshots import fetch_market_snapshots
        result = fetch_market_snapshots()

        assert result["null_market_cap"] == 1
        assert result["snapshots_created"] == 1

    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.compute_market_metrics")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MarketSnapshotProviderFactory")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.SessionLocal")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots._SOURCE_ENABLED", {"yahoo": True})
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MARKET_SNAPSHOT_SOURCE", "yahoo")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.time")
    def test_task_one_ticker_failure_doesnt_crash_batch(self, mock_time, mock_session_cls, mock_factory, mock_chain):
        secs = [_make_mock_security("A3"), _make_mock_security("BOOM3"), _make_mock_security("B3")]
        mock_session = _make_mock_session(secs)
        mock_session_cls.return_value = mock_session

        mock_adapter = MagicMock()
        mock_factory.create.return_value = mock_adapter

        async def mock_get_snapshot(ticker):
            if ticker == "BOOM3":
                raise RuntimeError("network down")
            return _make_snap_data(ticker)

        mock_adapter.get_snapshot = mock_get_snapshot

        from q3_fundamentals_engine.tasks.fetch_snapshots import fetch_market_snapshots
        result = fetch_market_snapshots()

        assert result["snapshots_created"] == 2
        assert result["failures"] == 1

    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.compute_market_metrics")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MarketSnapshotProviderFactory")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.SessionLocal")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots._SOURCE_ENABLED", {"yahoo": True})
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.MARKET_SNAPSHOT_SOURCE", "yahoo")
    @patch("q3_fundamentals_engine.tasks.fetch_snapshots.time")
    def test_task_returns_summary_dict(self, mock_time, mock_session_cls, mock_factory, mock_chain):
        secs = [_make_mock_security("PETR4")]
        mock_session = _make_mock_session(secs)
        mock_session_cls.return_value = mock_session

        mock_adapter = MagicMock()
        mock_factory.create.return_value = mock_adapter

        async def mock_get_snapshot(ticker):
            return _make_snap_data(ticker)

        mock_adapter.get_snapshot = mock_get_snapshot

        from q3_fundamentals_engine.tasks.fetch_snapshots import fetch_market_snapshots
        result = fetch_market_snapshots()

        assert "source" in result
        assert "snapshots_created" in result
        assert "null_market_cap" in result
        assert "failures" in result
        assert "total_securities" in result
