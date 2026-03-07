"""Purged temporal cross-validation tests."""

from __future__ import annotations

from datetime import date, timedelta

from q3_quant_engine.backtest.purged_validation import (
    generate_purged_folds,
    _coefficient_of_variation,
)


def test_purged_folds_correct_count():
    """Generates n_folds folds."""
    folds = generate_purged_folds(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        n_folds=5,
        purge_days=7,
        embargo_days=21,
    )
    assert len(folds) == 5


def test_purged_folds_cover_full_period():
    """Test folds cover the full date range without gaps."""
    folds = generate_purged_folds(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        n_folds=5,
        purge_days=7,
        embargo_days=21,
    )
    # First fold starts at start_date
    assert folds[0]["test_start"] == date(2020, 1, 1)
    # Last fold ends at end_date
    assert folds[-1]["test_end"] == date(2024, 12, 31)


def test_purged_folds_no_test_overlap():
    """Test folds don't overlap with each other."""
    folds = generate_purged_folds(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        n_folds=5,
        purge_days=7,
        embargo_days=21,
    )
    for i in range(1, len(folds)):
        assert folds[i]["test_start"] >= folds[i - 1]["test_end"]


def test_purge_window_excludes_data_before_test():
    """Purge window removes data just before test start."""
    folds = generate_purged_folds(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        n_folds=3,
        purge_days=14,
        embargo_days=21,
    )
    for fold in folds:
        expected_purge = fold["test_start"] - timedelta(days=14)
        assert fold["purge_start"] == expected_purge


def test_embargo_window_after_test():
    """Embargo window extends after test end."""
    folds = generate_purged_folds(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        n_folds=3,
        purge_days=7,
        embargo_days=30,
    )
    for fold in folds:
        expected_embargo = fold["test_end"] + timedelta(days=30)
        assert fold["embargo_end"] == expected_embargo


def test_train_periods_exclude_contaminated_data():
    """Train periods don't overlap with purge or embargo windows."""
    folds = generate_purged_folds(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        n_folds=3,
        purge_days=7,
        embargo_days=21,
    )
    for fold in folds:
        for tp in fold["train_periods"]:
            # Train must end before purge starts or start after embargo ends
            assert tp["end"] <= fold["purge_start"] or tp["start"] >= fold["embargo_end"]


def test_coefficient_of_variation_stable():
    """Low CV for stable values."""
    cv = _coefficient_of_variation([1.0, 1.1, 0.9, 1.05, 0.95])
    assert cv < 0.1


def test_coefficient_of_variation_unstable():
    """High CV for unstable values."""
    cv = _coefficient_of_variation([0.5, 2.0, -0.5, 3.0, 0.1])
    assert cv > 1.0
