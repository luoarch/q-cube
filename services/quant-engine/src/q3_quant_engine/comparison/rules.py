"""Comparison rules — direction, tolerance, and comparison mode per metric.

Versioned configuration for deterministic metric comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

RULES_VERSION = 1


@dataclass(frozen=True)
class ComparisonRule:
    metric: str
    direction: str  # "higher_better" | "lower_better" | "lower_stdev_better"
    comparison_mode: str  # "latest" | "avg_3p" | "stdev_3p"
    tolerance: float


COMPARISON_RULES: list[ComparisonRule] = [
    ComparisonRule("earnings_yield", "higher_better", "latest", 0.005),
    ComparisonRule("roic", "higher_better", "latest", 0.01),
    ComparisonRule("roe", "higher_better", "latest", 0.01),
    ComparisonRule("gross_margin", "higher_better", "avg_3p", 0.01),
    ComparisonRule("ebit_margin", "higher_better", "avg_3p", 0.01),
    ComparisonRule("net_margin", "higher_better", "avg_3p", 0.005),
    ComparisonRule("cash_conversion", "higher_better", "avg_3p", 0.05),
    ComparisonRule("debt_to_ebitda", "lower_better", "latest", 0.3),
    ComparisonRule("interest_coverage", "higher_better", "latest", 1.0),
    ComparisonRule("margin_stability", "lower_stdev_better", "stdev_3p", 0.005),
    ComparisonRule("refinement_score", "higher_better", "latest", 0.02),
]

RULES_BY_METRIC = {r.metric: r for r in COMPARISON_RULES}
