from __future__ import annotations

import logging

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

# Magic Formula ranking requires earnings_yield and roic to be computable.
# The actual score is a cross-issuer ranking done at query time, not here.
_REQUIRED_KEYS = {"ebit", "current_assets", "current_liabilities", "fixed_assets"}


class MagicFormulaScoreStrategy(IndicatorStrategy):
    """Validates that Magic Formula inputs are available.

    The actual Magic Formula score is a ranking across all issuers, computed at
    query time (not per-issuer). This strategy only validates that the required
    inputs exist and returns a placeholder result.
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

        inputs = {
            "ebit": ebit,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "fixed_assets": fixed,
            "market_cap": market_cap,
        }

        logger.debug("Magic Formula inputs validated; ranking computed at query time")

        return MetricResult(
            metric_code="magic_formula_eligible",
            value=None,  # Placeholder -- ranking is cross-issuer
            formula_version=1,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )
