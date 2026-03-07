from __future__ import annotations

import logging

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

# We need EBIT and either a pre-computed enterprise_value or the raw components
# (market_cap + net_debt ingredients).
_REQUIRED_KEYS = {"ebit"}


class EarningsYieldStrategy(IndicatorStrategy):
    """Earnings Yield = EBIT / Enterprise Value.

    Enterprise Value = market_cap + net_debt.
    Requires market_cap to be passed as a kwarg.
    """

    def supports(self, available_keys: set[str]) -> bool:
        has_ev = "enterprise_value" in available_keys or (
            {"short_term_debt", "long_term_debt", "cash_and_equivalents"}.issubset(available_keys)
        )
        return _REQUIRED_KEYS.issubset(available_keys) and has_ev

    def compute(
        self,
        values: dict[str, float | None],
        filing_ids: list[str],
        *,
        market_cap: float | None = None,
    ) -> MetricResult | None:
        ebit = values.get("ebit")
        if ebit is None:
            return None

        # Resolve enterprise value
        ev = values.get("enterprise_value")
        if ev is None:
            if market_cap is None:
                logger.debug("market_cap not provided; cannot compute EV for earnings yield")
                return None
            net_debt = values.get("net_debt")
            if net_debt is None:
                short = values.get("short_term_debt")
                long_ = values.get("long_term_debt")
                cash = values.get("cash_and_equivalents")
                if short is None or long_ is None or cash is None:
                    return None
                net_debt = short + long_ - cash
            ev = market_cap + net_debt

        if ev == 0:
            logger.warning("Enterprise value is zero; cannot compute earnings yield")
            return None

        result = ebit / ev

        inputs = {
            "ebit": ebit,
            "enterprise_value": ev,
        }

        return MetricResult(
            metric_code="earnings_yield",
            value=result,
            formula_version=1,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )
