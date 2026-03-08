"""Comparison data types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricComparison:
    metric: str
    direction: str  # "higher_better" | "lower_better" | "lower_stdev_better"
    comparison_mode: str  # "latest" | "avg_3p" | "stdev_3p"
    tolerance: float
    values: dict[str, float | None]  # issuer_id -> value
    winner: str | None  # issuer_id or None if tie
    outcome: str  # "win" | "tie" | "inconclusive"
    margin: float | None  # difference between best and second


@dataclass
class WinnerSummary:
    issuer_id: str
    ticker: str
    wins: int
    ties: int
    losses: int
    inconclusive: int


@dataclass
class ComparisonMatrix:
    issuer_ids: list[str]
    tickers: list[str]
    metrics: list[MetricComparison]
    summaries: list[WinnerSummary]
    rules_version: int
    data_reliability: dict[str, str]  # issuer_id -> reliability level
