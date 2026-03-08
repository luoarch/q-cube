"""ComparisonEngine — deterministic comparison of 2-3 assets."""

from __future__ import annotations

import logging
import statistics
from uuid import UUID

from sqlalchemy.orm import Session

from q3_quant_engine.comparison.rules import COMPARISON_RULES, RULES_VERSION, ComparisonRule
from q3_quant_engine.comparison.types import (
    ComparisonMatrix,
    MetricComparison,
    WinnerSummary,
)
from q3_quant_engine.refiner.completeness import assess_completeness
from q3_quant_engine.refiner.data_loader import (
    get_issuer_for_ticker,
    load_multi_period_data,
)
from q3_quant_engine.refiner.types import PeriodValue

logger = logging.getLogger(__name__)


class ComparisonEngine:
    def __init__(self, session: Session) -> None:
        self._session = session

    def compare(self, tickers: list[str]) -> ComparisonMatrix:
        """Compare 2-3 assets across all comparison metrics.

        Args:
            tickers: List of 2-3 tickers to compare.

        Returns:
            ComparisonMatrix with per-metric outcomes and winner summaries.
        """
        if len(tickers) < 2 or len(tickers) > 3:
            raise ValueError("Compare requires 2-3 tickers")

        # Load multi-period data for each ticker
        issuer_data: dict[str, dict[str, list[PeriodValue]]] = {}
        issuer_ids: list[str] = []
        ticker_map: dict[str, str] = {}  # issuer_id -> ticker
        reliability: dict[str, str] = {}

        for ticker in tickers:
            info = get_issuer_for_ticker(self._session, ticker)
            if info is None:
                logger.warning("Ticker %s not found, skipping", ticker)
                continue

            issuer_id, sector, subsector = info
            iid = str(issuer_id)
            data, periods = load_multi_period_data(self._session, issuer_id, n_periods=3)

            issuer_ids.append(iid)
            ticker_map[iid] = ticker
            issuer_data[iid] = data

            # Assess reliability
            flat = {k: [pv.value for pv in pvs] for k, pvs in data.items()}
            from q3_quant_engine.refiner.classification import classify_issuer
            classification = classify_issuer(sector, subsector)
            _, rel = assess_completeness(flat, periods, classification)
            reliability[iid] = rel

        if len(issuer_ids) < 2:
            raise ValueError("Need at least 2 valid tickers for comparison")

        # Run comparisons
        metric_results: list[MetricComparison] = []
        for rule in COMPARISON_RULES:
            result = self._compare_metric(rule, issuer_ids, issuer_data)
            metric_results.append(result)

        # Build summaries
        summaries = self._build_summaries(issuer_ids, ticker_map, metric_results)

        return ComparisonMatrix(
            issuer_ids=issuer_ids,
            tickers=[ticker_map[iid] for iid in issuer_ids],
            metrics=metric_results,
            summaries=summaries,
            rules_version=RULES_VERSION,
            data_reliability=reliability,
        )

    def _compare_metric(
        self,
        rule: ComparisonRule,
        issuer_ids: list[str],
        issuer_data: dict[str, dict[str, list[PeriodValue]]],
    ) -> MetricComparison:
        """Compare a single metric across issuers."""
        values: dict[str, float | None] = {}

        for iid in issuer_ids:
            data = issuer_data.get(iid, {})
            series = data.get(rule.metric, [])

            if rule.comparison_mode == "latest":
                values[iid] = _latest_value(series)
            elif rule.comparison_mode == "avg_3p":
                values[iid] = _avg_value(series)
            elif rule.comparison_mode == "stdev_3p":
                values[iid] = _stdev_value(series)
            else:
                values[iid] = _latest_value(series)

        # Determine winner
        winner, outcome, margin = _determine_winner(values, rule)

        return MetricComparison(
            metric=rule.metric,
            direction=rule.direction,
            comparison_mode=rule.comparison_mode,
            tolerance=rule.tolerance,
            values=values,
            winner=winner,
            outcome=outcome,
            margin=margin,
        )

    def _build_summaries(
        self,
        issuer_ids: list[str],
        ticker_map: dict[str, str],
        metrics: list[MetricComparison],
    ) -> list[WinnerSummary]:
        summaries: list[WinnerSummary] = []
        for iid in issuer_ids:
            wins = sum(1 for m in metrics if m.winner == iid and m.outcome == "win")
            ties = sum(1 for m in metrics if m.outcome == "tie")
            losses = sum(
                1 for m in metrics
                if m.outcome == "win" and m.winner != iid and m.winner is not None
            )
            inconclusive = sum(1 for m in metrics if m.outcome == "inconclusive")
            summaries.append(WinnerSummary(
                issuer_id=iid,
                ticker=ticker_map[iid],
                wins=wins,
                ties=ties,
                losses=losses,
                inconclusive=inconclusive,
            ))
        return summaries


def _latest_value(series: list[PeriodValue]) -> float | None:
    if not series:
        return None
    # Last entry (most recent) with a non-None value
    for pv in reversed(series):
        if pv.value is not None:
            return pv.value
    return None


def _avg_value(series: list[PeriodValue]) -> float | None:
    vals = [pv.value for pv in series if pv.value is not None]
    if not vals:
        return None
    return statistics.mean(vals)


def _stdev_value(series: list[PeriodValue]) -> float | None:
    vals = [pv.value for pv in series if pv.value is not None]
    if len(vals) < 2:
        return None
    return statistics.stdev(vals)


def _determine_winner(
    values: dict[str, float | None],
    rule: ComparisonRule,
) -> tuple[str | None, str, float | None]:
    """Determine winner for a metric comparison.

    Returns (winner_id, outcome, margin).
    """
    valid = {k: v for k, v in values.items() if v is not None}

    if len(valid) == 0:
        return None, "inconclusive", None

    if len(valid) == 1:
        # One has data, others don't -> the one with data wins
        winner_id = next(iter(valid))
        return winner_id, "win", None

    # Sort by value
    if rule.direction == "higher_better":
        sorted_items = sorted(valid.items(), key=lambda x: x[1], reverse=True)  # type: ignore[arg-type]
    elif rule.direction == "lower_better" or rule.direction == "lower_stdev_better":
        sorted_items = sorted(valid.items(), key=lambda x: x[1])  # type: ignore[arg-type]
    else:
        sorted_items = sorted(valid.items(), key=lambda x: x[1], reverse=True)  # type: ignore[arg-type]

    best_id, best_val = sorted_items[0]
    second_val = sorted_items[1][1]
    margin = abs(best_val - second_val)  # type: ignore[operator]

    if margin < rule.tolerance:
        return None, "tie", margin

    return best_id, "win", margin
