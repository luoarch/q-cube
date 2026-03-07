from __future__ import annotations

import logging

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)


class GrossMarginStrategy(IndicatorStrategy):
    """Gross Margin = gross_profit / revenue."""

    def supports(self, available_keys: set[str]) -> bool:
        return {"gross_profit", "revenue"}.issubset(available_keys)

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        gross_profit = values.get("gross_profit")
        revenue = values.get("revenue")

        if gross_profit is None or revenue is None:
            return None
        if revenue == 0:
            logger.warning("Revenue is zero; cannot compute gross margin")
            return None

        result = gross_profit / revenue

        return MetricResult(
            metric_code="gross_margin",
            value=result,
            formula_version=1,
            inputs_snapshot={"gross_profit": gross_profit, "revenue": revenue},
            source_filing_ids=filing_ids,
        )


class EbitMarginStrategy(IndicatorStrategy):
    """EBIT Margin = ebit / revenue."""

    def supports(self, available_keys: set[str]) -> bool:
        return {"ebit", "revenue"}.issubset(available_keys)

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        ebit = values.get("ebit")
        revenue = values.get("revenue")

        if ebit is None or revenue is None:
            return None
        if revenue == 0:
            logger.warning("Revenue is zero; cannot compute EBIT margin")
            return None

        result = ebit / revenue

        return MetricResult(
            metric_code="ebit_margin",
            value=result,
            formula_version=1,
            inputs_snapshot={"ebit": ebit, "revenue": revenue},
            source_filing_ids=filing_ids,
        )


class NetMarginStrategy(IndicatorStrategy):
    """Net Margin = net_income / revenue."""

    def supports(self, available_keys: set[str]) -> bool:
        return {"net_income", "revenue"}.issubset(available_keys)

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        net_income = values.get("net_income")
        revenue = values.get("revenue")

        if net_income is None or revenue is None:
            return None
        if revenue == 0:
            logger.warning("Revenue is zero; cannot compute net margin")
            return None

        result = net_income / revenue

        return MetricResult(
            metric_code="net_margin",
            value=result,
            formula_version=1,
            inputs_snapshot={"net_income": net_income, "revenue": revenue},
            source_filing_ids=filing_ids,
        )
