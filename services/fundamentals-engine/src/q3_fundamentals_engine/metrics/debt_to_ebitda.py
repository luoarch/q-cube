from __future__ import annotations

import logging

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {"short_term_debt", "long_term_debt", "cash_and_equivalents", "ebit"}


class DebtToEbitdaStrategy(IndicatorStrategy):
    """Debt/EBITDA = net_debt / ebitda.

    Uses net_debt = (short_term_debt + long_term_debt) - cash_and_equivalents
    and EBITDA proxy from ebit (depreciation not available in canonical keys).
    Falls back to ebit when proper EBITDA can't be computed.
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
        short_debt = values.get("short_term_debt")
        long_debt = values.get("long_term_debt")
        cash = values.get("cash_and_equivalents")
        ebit = values.get("ebit")

        if any(v is None for v in [short_debt, long_debt, cash, ebit]):
            return None

        net_debt = (short_debt + long_debt) - cash  # type: ignore[operator]

        # Use ebit as EBITDA proxy (depreciation not in canonical keys)
        ebitda = ebit  # type: ignore[assignment]

        if ebitda is None or ebitda <= 0:
            logger.warning("EBITDA <= 0; debt/EBITDA not meaningful")
            return None

        result = net_debt / ebitda

        return MetricResult(
            metric_code="debt_to_ebitda",
            value=result,
            formula_version=1,
            inputs_snapshot={
                "short_term_debt": short_debt,
                "long_term_debt": long_debt,
                "cash_and_equivalents": cash,
                "ebit_as_ebitda_proxy": ebitda,
                "net_debt": net_debt,
            },
            source_filing_ids=filing_ids,
        )
