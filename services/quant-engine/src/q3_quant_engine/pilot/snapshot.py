"""Pure snapshot mapping — no DB, no HTTP, no side effects.

Transforms ranking items into SnapshotRow dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TypedDict


class RankingItemInput(TypedDict):
    """Expected shape of ranking items from the split-model endpoint."""

    ticker: str
    modelFamily: str
    rankWithinModel: int
    investabilityStatus: str
    compositeScore: float | None
    earningsYield: float | None
    returnOnCapital: float | None
    netPayoutYield: float | None


@dataclass(frozen=True)
class SnapshotRow:
    """One row for ranking_snapshots table.

    Preserves ranking factor values for future correlation with forward returns.
    """

    snapshot_date: date
    ticker: str
    model_family: str
    rank_within_model: int
    composite_score: float | None
    investability_status: str
    earnings_yield: float | None
    return_on_capital: float | None
    net_payout_yield: float | None


def map_ranking_to_snapshot_rows(
    ranking_items: list[RankingItemInput],
    snapshot_date: date,
) -> list[SnapshotRow]:
    """Map ranking response items to snapshot rows.

    Args:
        ranking_items: Items from primaryRanking or secondaryRanking.
            Must have keys: ticker, modelFamily, rankWithinModel, investabilityStatus.
            Input is expected from the typed ranking endpoint — no re-validation here.
        snapshot_date: Date of the snapshot capture.

    Returns:
        List of SnapshotRow (frozen dataclasses).
    """
    return [
        SnapshotRow(
            snapshot_date=snapshot_date,
            ticker=item["ticker"],
            model_family=item["modelFamily"],
            rank_within_model=item["rankWithinModel"],
            composite_score=item.get("compositeScore"),
            investability_status=item["investabilityStatus"],
            earnings_yield=item.get("earningsYield"),
            return_on_capital=item.get("returnOnCapital"),
            net_payout_yield=item.get("netPayoutYield"),
        )
        for item in ranking_items
    ]
