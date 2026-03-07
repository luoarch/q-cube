from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class MetricResult:
    """Result of a single metric computation."""

    metric_code: str
    value: float | None
    formula_version: int
    inputs_snapshot: dict[str, float | None]
    source_filing_ids: list[str] = field(default_factory=list)


class IndicatorStrategy(abc.ABC):
    """Abstract base for derived-metric computation strategies."""

    @abc.abstractmethod
    def supports(self, available_keys: set[str]) -> bool:
        """Return True if this strategy can compute given the available canonical keys."""

    @abc.abstractmethod
    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        """Compute the metric from statement values.

        Returns None when inputs are present but a value cannot be determined
        (e.g. division by zero).
        """
