from __future__ import annotations

import logging

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {"ebit", "current_assets", "current_liabilities", "fixed_assets"}


class RoicStrategy(IndicatorStrategy):
    """ROIC = EBIT / (net_working_capital + fixed_assets).

    Where net_working_capital = current_assets - current_liabilities.
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
        current_assets = values.get("current_assets")
        current_liabilities = values.get("current_liabilities")
        fixed = values.get("fixed_assets")

        if ebit is None or current_assets is None or current_liabilities is None or fixed is None:
            return None

        nwc = current_assets - current_liabilities
        invested_capital = nwc + fixed

        if invested_capital == 0:
            logger.warning("Invested capital is zero; cannot compute ROIC")
            return None

        result = ebit / invested_capital

        inputs = {
            "ebit": ebit,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "fixed_assets": fixed,
            "net_working_capital": nwc,
            "invested_capital": invested_capital,
        }

        return MetricResult(
            metric_code="roic",
            value=result,
            formula_version=1,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )
