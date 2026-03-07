from __future__ import annotations

import logging

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

# net_debt may come from the values dict (pre-computed canonical key) or we can
# compute it inline if the raw components are available.
_REQUIRED_KEYS = {"short_term_debt", "long_term_debt", "cash_and_equivalents"}


class EvStrategy(IndicatorStrategy):
    """Enterprise Value = market_cap + net_debt.

    Requires market_cap to be passed explicitly (it comes from market data, not filings).
    net_debt is derived from short_term_debt + long_term_debt - cash_and_equivalents,
    or taken directly from the values dict if a pre-computed canonical key exists.
    """

    def supports(self, available_keys: set[str]) -> bool:
        has_net_debt = "net_debt" in available_keys or _REQUIRED_KEYS.issubset(available_keys)
        return has_net_debt

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        if market_cap is None:
            logger.debug("market_cap not provided; skipping EV computation")
            return None

        # Prefer pre-computed net_debt, fall back to component calculation.
        net_debt = values.get("net_debt")
        if net_debt is None:
            short = values.get("short_term_debt")
            long_ = values.get("long_term_debt")
            cash = values.get("cash_and_equivalents")
            if short is None or long_ is None or cash is None:
                return None
            net_debt = short + long_ - cash

        result = market_cap + net_debt

        inputs = {
            "market_cap": market_cap,
            "net_debt": net_debt,
        }

        return MetricResult(
            metric_code="enterprise_value",
            value=result,
            formula_version=1,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )
