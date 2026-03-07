"""Purged temporal cross-validation with embargo.

Implements the purged k-fold CV approach from Lopez de Prado (2018)
for financial time series, preventing information leakage between
train and test folds via purging and embargo.

Reference: Lopez de Prado, M. (2018). Advances in Financial Machine
Learning, Lecture 10 — Purged & Embargo Cross-Validation.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from q3_quant_engine.backtest.engine import BacktestConfig, run_backtest
from q3_quant_engine.backtest.metrics import compute_returns
from q3_quant_engine.backtest.statistical import compute_statistical_metrics
from q3_quant_engine.backtest.walk_forward import _add_months


@dataclass
class PurgedCVConfig:
    """Configuration for purged temporal cross-validation."""

    backtest_config: BacktestConfig
    n_folds: int = 5
    embargo_days: int = 21  # gap after each test fold (~1 month)
    purge_days: int = 7  # overlap window to remove before test


@dataclass
class PurgedCVResult:
    """Results from purged temporal cross-validation."""

    folds: list[dict]  # [{fold, train_period, test_period, train_metrics, test_metrics}]
    avg_train_metrics: dict
    avg_test_metrics: dict
    degradation: dict  # (test - train) / |train|
    stability_score: float  # coefficient of variation of test Sharpes
    overfitting_probability: float  # PBO estimate


def generate_purged_folds(
    start_date: date,
    end_date: date,
    n_folds: int,
    purge_days: int,
    embargo_days: int,
) -> list[dict]:
    """Generate purged temporal CV folds.

    Each fold:
    - test = one contiguous block
    - train = all remaining data MINUS purge window around test edges
    - embargo = gap after test fold before training data can resume

    Unlike walk-forward (always expanding IS), purged CV uses all
    non-contaminated data for training in each fold.
    """
    total_days = (end_date - start_date).days
    fold_size_days = total_days // n_folds
    folds = []

    for i in range(n_folds):
        test_start = start_date + timedelta(days=i * fold_size_days)
        test_end = start_date + timedelta(days=(i + 1) * fold_size_days)
        if i == n_folds - 1:
            test_end = end_date

        # Purge window: remove data just before test start
        purge_start = test_start - timedelta(days=purge_days)

        # Embargo window: remove data just after test end
        embargo_end = test_end + timedelta(days=embargo_days)

        # Train periods: before purge_start and after embargo_end
        train_periods = []
        if purge_start > start_date:
            train_periods.append({"start": start_date, "end": purge_start})
        if embargo_end < end_date:
            train_periods.append({"start": embargo_end, "end": end_date})

        folds.append({
            "fold": i,
            "test_start": test_start,
            "test_end": test_end,
            "train_periods": train_periods,
            "purge_start": purge_start,
            "embargo_end": embargo_end,
        })

    return folds


def run_purged_cv(session: Session, config: PurgedCVConfig) -> PurgedCVResult:
    """Run purged temporal cross-validation."""
    folds = generate_purged_folds(
        config.backtest_config.start_date,
        config.backtest_config.end_date,
        config.n_folds,
        config.purge_days,
        config.embargo_days,
    )

    results: list[dict] = []

    for fold in folds:
        # Test backtest
        test_config = copy.copy(config.backtest_config)
        test_config.start_date = fold["test_start"]
        test_config.end_date = fold["test_end"]
        test_result = run_backtest(session, test_config)

        # Train backtest: use longest train period (simplified)
        # Full implementation would combine all train periods
        train_metrics: dict = {}
        if fold["train_periods"]:
            longest = max(fold["train_periods"], key=lambda p: (p["end"] - p["start"]).days)
            train_config = copy.copy(config.backtest_config)
            train_config.start_date = longest["start"]
            train_config.end_date = longest["end"]
            train_result = run_backtest(session, train_config)
            train_metrics = train_result.metrics
        else:
            train_metrics = {}

        results.append({
            "fold": fold["fold"],
            "train_period": {
                "periods": [{"start": str(p["start"]), "end": str(p["end"])} for p in fold["train_periods"]],
            },
            "test_period": {"start": str(fold["test_start"]), "end": str(fold["test_end"])},
            "train_metrics": train_metrics,
            "test_metrics": test_result.metrics,
        })

    # Averages
    avg_train = _avg_metrics([r["train_metrics"] for r in results if r["train_metrics"]])
    avg_test = _avg_metrics([r["test_metrics"] for r in results])

    # Degradation
    degradation = {}
    for key in ("sharpe", "cagr", "sortino"):
        train_val = avg_train.get(key, 0)
        test_val = avg_test.get(key, 0)
        if train_val and train_val != 0:
            degradation[key] = round((test_val - train_val) / abs(train_val), 4)
        else:
            degradation[key] = 0.0

    # Stability: coefficient of variation of test Sharpes
    test_sharpes = [r["test_metrics"].get("sharpe", 0) for r in results]
    stability = _coefficient_of_variation(test_sharpes)

    # PBO estimate (simplified): fraction of folds where test < train
    n_worse = sum(
        1 for r in results
        if r["test_metrics"].get("sharpe", 0) < r["train_metrics"].get("sharpe", 0)
    )
    pbo = n_worse / len(results) if results else 1.0

    return PurgedCVResult(
        folds=results,
        avg_train_metrics=avg_train,
        avg_test_metrics=avg_test,
        degradation=degradation,
        stability_score=round(stability, 4),
        overfitting_probability=round(pbo, 4),
    )


def _avg_metrics(metrics_list: list[dict]) -> dict:
    if not metrics_list:
        return {}
    result = {}
    numeric_keys = set()
    for m in metrics_list:
        for k, v in m.items():
            if isinstance(v, (int, float)):
                numeric_keys.add(k)
    for key in numeric_keys:
        vals = [m.get(key, 0) for m in metrics_list if isinstance(m.get(key), (int, float))]
        result[key] = round(sum(vals) / len(vals), 6) if vals else 0.0
    return result


def _coefficient_of_variation(xs: list[float]) -> float:
    """CV = std / |mean|. Lower = more stable."""
    if not xs:
        return 0.0
    from q3_quant_engine.backtest.metrics import _mean, _std
    m = _mean(xs)
    s = _std(xs)
    if abs(m) < 1e-10:
        return float("inf") if s > 0 else 0.0
    return s / abs(m)
