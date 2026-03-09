from __future__ import annotations

import logging

from q3_shared_models.entities import MetricCode

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {"net_income", "equity"}


class RoeStrategy(IndicatorStrategy):
    """ROE = net_income / equity."""

    def supports(self, available_keys: set[str]) -> bool:
        return _REQUIRED_KEYS.issubset(available_keys)

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        net_income = values.get("net_income")
        equity = values.get("equity")

        if net_income is None or equity is None:
            return None

        if equity == 0:
            logger.warning("Equity is zero; cannot compute ROE")
            return None

        result = net_income / equity

        inputs = {
            "net_income": net_income,
            "equity": equity,
        }

        return MetricResult(
            metric_code=MetricCode.roe,
            value=result,
            formula_version=1,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )
