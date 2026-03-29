"""Tests for B3 COTAHIST adapter (Plan 7 S2)."""

from __future__ import annotations

from datetime import date

import pytest

from q3_fundamentals_engine.providers.b3.parser import CotahistRecord
from q3_fundamentals_engine.providers.b3.adapter import (
    build_snapshot_data,
    get_latest_close,
)


def _rec(
    ticker: str = "PETR4",
    dt: date = date(2024, 12, 30),
    close: float = 36.19,
    volume: float = 5_000_000.0,
) -> CotahistRecord:
    return CotahistRecord(
        ticker=ticker, date=dt, close=close, open=36.0, high=37.0, low=35.5,
        volume=volume, n_trades=1000, quantity=50000,
    )


class TestGetLatestClose:
    def test_single_record(self) -> None:
        records = [_rec(dt=date(2024, 12, 30))]
        result = get_latest_close(records, "PETR4")
        assert result is not None
        assert result.date == date(2024, 12, 30)

    def test_picks_most_recent(self) -> None:
        records = [
            _rec(dt=date(2024, 12, 28), close=35.0),
            _rec(dt=date(2024, 12, 30), close=36.19),
            _rec(dt=date(2024, 12, 29), close=35.5),
        ]
        result = get_latest_close(records, "PETR4")
        assert result is not None
        assert result.close == 36.19

    def test_ticker_not_found(self) -> None:
        records = [_rec(ticker="VALE3")]
        assert get_latest_close(records, "PETR4") is None

    def test_empty_records(self) -> None:
        assert get_latest_close([], "PETR4") is None


class TestBuildSnapshotData:
    def test_basic(self) -> None:
        rec = _rec(close=36.19)
        snap = build_snapshot_data(rec)
        assert snap.ticker == "PETR4"
        assert snap.price == 36.19
        assert snap.market_cap is None  # No CVM shares provided
        assert snap.currency == "BRL"
        assert snap.raw_json["source"] == "b3_cotahist"

    def test_with_derived_mcap(self) -> None:
        rec = _rec(close=36.19)
        # CVM net_shares = 13B, close = 36.19 → mcap = 470.47B
        mcap = 36.19 * 13_000_000_000
        snap = build_snapshot_data(rec, derived_market_cap=mcap, shares_quarter="2024-12-31")
        assert snap.market_cap == mcap
        assert snap.raw_json["derivation"] == "close × CVM net_shares"
        assert snap.raw_json["shares_source"] == "CVM composicao_capital"
        assert snap.raw_json["shares_quarter"] == "2024-12-31"

    def test_no_mcap_when_no_shares(self) -> None:
        rec = _rec(close=36.19)
        snap = build_snapshot_data(rec, derived_market_cap=None)
        assert snap.market_cap is None
        assert "derivation" not in snap.raw_json

    def test_raw_json_has_ohlcv(self) -> None:
        rec = _rec(close=36.19)
        snap = build_snapshot_data(rec)
        assert snap.raw_json["close"] == 36.19
        assert snap.raw_json["open"] == 36.0
        assert snap.raw_json["high"] == 37.0
        assert snap.raw_json["low"] == 35.5
        assert snap.raw_json["n_trades"] == 1000
