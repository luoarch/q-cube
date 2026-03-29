"""Spec tests for snapshot mapping pure functions (MF-RUNTIME-01A S1)."""

from __future__ import annotations

from datetime import date

import pytest

from q3_quant_engine.pilot.snapshot import map_ranking_to_snapshot_rows, SnapshotRow


def _item(
    ticker: str = "PETR3",
    model: str = "NPY_ROC",
    rank: int = 1,
    score: float = 0.15,
    status: str = "fully_evaluated",
    ey: float = 0.12,
    roc: float = 0.35,
    npy: float | None = 0.08,
) -> dict:
    return {
        "ticker": ticker,
        "modelFamily": model,
        "rankWithinModel": rank,
        "compositeScore": score,
        "investabilityStatus": status,
        "earningsYield": ey,
        "returnOnCapital": roc,
        "netPayoutYield": npy,
    }


class TestMapRankingToSnapshotRows:
    def test_basic_mapping(self) -> None:
        items = [_item(ticker="PETR3", rank=1, score=0.10, ey=0.12, roc=0.35, npy=0.08)]
        rows = map_ranking_to_snapshot_rows(items, date(2026, 3, 26))
        assert len(rows) == 1
        r = rows[0]
        assert r.snapshot_date == date(2026, 3, 26)
        assert r.ticker == "PETR3"
        assert r.model_family == "NPY_ROC"
        assert r.rank_within_model == 1
        assert r.composite_score == 0.10
        assert r.investability_status == "fully_evaluated"
        assert r.earnings_yield == 0.12
        assert r.return_on_capital == 0.35
        assert r.net_payout_yield == 0.08

    def test_preserves_model_family(self) -> None:
        items = [
            _item(ticker="A", model="NPY_ROC"),
            _item(ticker="B", model="EY_ROC", status="partially_evaluated", npy=None),
        ]
        rows = map_ranking_to_snapshot_rows(items, date(2026, 1, 1))
        assert rows[0].model_family == "NPY_ROC"
        assert rows[1].model_family == "EY_ROC"

    def test_preserves_rank_within_model(self) -> None:
        items = [_item(ticker="A", rank=5), _item(ticker="B", rank=12)]
        rows = map_ranking_to_snapshot_rows(items, date(2026, 1, 1))
        assert rows[0].rank_within_model == 5
        assert rows[1].rank_within_model == 12

    def test_preserves_factor_values(self) -> None:
        items = [_item(ey=0.25, roc=1.5, npy=0.12)]
        rows = map_ranking_to_snapshot_rows(items, date(2026, 1, 1))
        assert rows[0].earnings_yield == 0.25
        assert rows[0].return_on_capital == 1.5
        assert rows[0].net_payout_yield == 0.12

    def test_npy_none_for_ey_roc_model(self) -> None:
        items = [_item(model="EY_ROC", npy=None)]
        rows = map_ranking_to_snapshot_rows(items, date(2026, 1, 1))
        assert rows[0].net_payout_yield is None

    def test_composite_score_none(self) -> None:
        items = [_item(score=None)]  # type: ignore[arg-type]
        items[0]["compositeScore"] = None
        rows = map_ranking_to_snapshot_rows(items, date(2026, 1, 1))
        assert rows[0].composite_score is None

    def test_empty_input(self) -> None:
        rows = map_ranking_to_snapshot_rows([], date(2026, 1, 1))
        assert rows == []

    def test_multiple_items(self) -> None:
        items = [_item(ticker=f"T{i}") for i in range(10)]
        rows = map_ranking_to_snapshot_rows(items, date(2026, 1, 1))
        assert len(rows) == 10

    def test_snapshot_row_is_frozen(self) -> None:
        items = [_item()]
        rows = map_ranking_to_snapshot_rows(items, date(2026, 1, 1))
        with pytest.raises(AttributeError):
            rows[0].ticker = "MODIFIED"  # type: ignore[misc]
