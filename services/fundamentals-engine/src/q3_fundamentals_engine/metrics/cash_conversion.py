from __future__ import annotations

import logging

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {"cash_from_operations", "net_income"}


class CashConversionStrategy(IndicatorStrategy):
    """Cash Conversion = cash_from_operations / net_income."""

    def supports(self, available_keys: set[str]) -> bool:
        return _REQUIRED_KEYS.issubset(available_keys)

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        cfo = values.get("cash_from_operations")
        net_income = values.get("net_income")

        if cfo is None or net_income is None:
            return None

        if net_income <= 0:
            logger.warning("Net income <= 0; cash conversion ratio is not meaningful")
            return None

        result = cfo / net_income

        inputs = {
            "cash_from_operations": cfo,
            "net_income": net_income,
        }

        return MetricResult(
            metric_code="cash_conversion",
            value=result,
            formula_version=1,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )
