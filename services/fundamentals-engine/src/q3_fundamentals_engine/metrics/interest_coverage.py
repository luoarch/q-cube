from __future__ import annotations

import logging

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {"ebit", "financial_result"}


class InterestCoverageStrategy(IndicatorStrategy):
    """Interest Coverage = ebit / abs(financial_result).

    financial_result in CVM filings is typically negative (interest expense).
    A higher ratio means the company can more easily service its debt.
    """

    def supports(self, available_keys: set[str]) -> bool:
        return _REQUIRED_KEYS.issubset(available_keys)

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        ebit = values.get("ebit")
        fin_result = values.get("financial_result")

        if ebit is None or fin_result is None:
            return None

        interest_expense = abs(fin_result)
        if interest_expense == 0:
            logger.warning("Financial result is zero; interest coverage undefined")
            return None

        result = ebit / interest_expense

        return MetricResult(
            metric_code="interest_coverage",
            value=result,
            formula_version=1,
            inputs_snapshot={
                "ebit": ebit,
                "financial_result": fin_result,
                "interest_expense_abs": interest_expense,
            },
            source_filing_ids=filing_ids,
        )
