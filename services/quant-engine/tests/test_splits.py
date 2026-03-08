"""Official temporal split tests."""

from __future__ import annotations

import pytest
from datetime import date

from q3_quant_engine.backtest.splits import (
    OFFICIAL_SPLITS,
    TemporalSplit,
    get_split,
    validate_not_tuning_on_oos,
)


def test_official_splits_all_valid():
    """All official splits pass validation."""
    for name, split in OFFICIAL_SPLITS.items():
        split.validate()  # Should not raise


def test_split_is_before_oos():
    """IS period ends before OOS starts in all splits."""
    for name, split in OFFICIAL_SPLITS.items():
        assert split.is_end < split.oos_start, f"Split {name}: IS overlaps OOS"


def test_split_embargo_respected():
    """Embargo gap between IS and OOS is respected."""
    for name, split in OFFICIAL_SPLITS.items():
        gap = (split.oos_start - split.is_end).days
        assert gap >= split.embargo_days, f"Split {name}: gap {gap}d < embargo {split.embargo_days}d"


def test_get_split_valid():
    """get_split returns known splits."""
    split = get_split("full")
    assert split.name == "full"


def test_get_split_invalid():
    """get_split raises KeyError for unknown splits."""
    with pytest.raises(KeyError):
        get_split("nonexistent")


def test_validate_not_tuning_within_is():
    """Config within IS is valid (not tuning on OOS)."""
    split = get_split("full")
    assert validate_not_tuning_on_oos(
        date(2020, 1, 1), date(2023, 6, 30), split
    ) is True


def test_validate_tuning_on_oos_detected():
    """Config extending into OOS is detected."""
    split = get_split("full")
    assert validate_not_tuning_on_oos(
        date(2020, 1, 1), date(2024, 6, 30), split
    ) is False


def test_invalid_split_is_after_oos():
    """Split with IS after OOS raises ValueError."""
    bad_split = TemporalSplit(
        name="bad",
        is_start=date(2024, 1, 1),
        is_end=date(2025, 1, 1),
        oos_start=date(2023, 1, 1),
        oos_end=date(2024, 1, 1),
    )
    with pytest.raises(ValueError):
        bad_split.validate()


def test_split_frozen():
    """TemporalSplit is immutable (frozen dataclass)."""
    split = get_split("full")
    with pytest.raises(AttributeError):
        split.name = "modified"
