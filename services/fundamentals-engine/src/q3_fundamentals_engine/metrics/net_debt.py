from __future__ import annotations

import logging

from q3_shared_models.entities import MetricCode

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {"short_term_debt", "long_term_debt", "cash_and_equivalents"}


class NetDebtStrategy(IndicatorStrategy):
    """Net Debt = short_term_debt + long_term_debt - cash_and_equivalents."""

    def supports(self, available_keys: set[str]) -> bool:
        return _REQUIRED_KEYS.issubset(available_keys)

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        short = values.get("short_term_debt")
        long_ = values.get("long_term_debt")
        cash = values.get("cash_and_equivalents")

        if short is None or long_ is None or cash is None:
            return None

        result = short + long_ - cash

        inputs = {
            "short_term_debt": short,
            "long_term_debt": long_,
            "cash_and_equivalents": cash,
        }

        return MetricResult(
            metric_code=MetricCode.net_debt,
            value=result,
            formula_version=1,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )
