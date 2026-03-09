from __future__ import annotations

import logging

from q3_shared_models.entities import MetricCode

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult

logger = logging.getLogger(__name__)

# We use EBIT as proxy when D&A is unavailable.
_REQUIRED_KEYS = {"ebit"}
_OPTIONAL_KEYS = {"depreciation_amortization"}


class EbitdaStrategy(IndicatorStrategy):
    """EBITDA = EBIT + Depreciation & Amortization (proxy: EBIT when D&A missing)."""

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
        da = values.get("depreciation_amortization")

        if ebit is None:
            return None

        # D&A is usually reported as negative; we add its absolute value.
        if da is not None:
            result = ebit + abs(da)
        else:
            logger.debug("D&A not available; using EBIT as EBITDA proxy")
            result = ebit

        inputs = {"ebit": ebit, "depreciation_amortization": da}

        return MetricResult(
            metric_code=MetricCode.ebitda,
            value=result,
            formula_version=1,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )
