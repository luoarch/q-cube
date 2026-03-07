"""Walk-forward analysis tests."""

from __future__ import annotations

from datetime import date, timedelta

from q3_quant_engine.backtest.walk_forward import generate_splits


def test_walk_forward_splits_non_overlapping():
    """IS and OOS periods don't overlap within each split."""
    splits = generate_splits(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        n_splits=3,
        oos_months=12,
        embargo_days=21,
    )
    for split in splits:
        assert split["is_end"] < split["oos_start"]


def test_walk_forward_embargo_gap():
    """embargo_days gap between IS end and OOS start."""
    embargo = 21
    splits = generate_splits(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        n_splits=3,
        oos_months=12,
        embargo_days=embargo,
    )
    for split in splits:
        gap = (split["oos_start"] - split["is_end"]).days
        assert gap >= embargo


def test_walk_forward_expanding_is():
    """IS always starts from start_date (expanding window)."""
    start = date(2020, 1, 1)
    splits = generate_splits(
        start_date=start,
        end_date=date(2024, 12, 31),
        n_splits=3,
        oos_months=12,
        embargo_days=21,
    )
    for split in splits:
        assert split["is_start"] == start
    # IS end should grow across splits
    is_ends = [s["is_end"] for s in splits]
    for i in range(1, len(is_ends)):
        assert is_ends[i] >= is_ends[i - 1]
