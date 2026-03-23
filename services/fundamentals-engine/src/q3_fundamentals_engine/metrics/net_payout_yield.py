"""Net Payout Yield metric — pure composition.

NPY = DividendYield_TTM + NetBuybackYield

Does NOT recompute DY or NBY. Takes already-computed results and composes.
NULL if either component is NULL. See Plan 3A §6.1.
"""

from __future__ import annotations

import logging

from q3_shared_models.entities import MetricCode

from q3_fundamentals_engine.metrics.base import MetricResult

logger = logging.getLogger(__name__)


def compute_net_payout_yield(
    dy_result: MetricResult | None,
    nby_result: MetricResult | None,
) -> MetricResult | None:
    """Compose NPY from pre-computed DY and NBY results.

    Returns None if either component is None (hard NULL propagation).
    """
    if dy_result is None or nby_result is None:
        return None

    dy_value = dy_result.value
    nby_value = nby_result.value

    if dy_value is None or nby_value is None:
        return None

    npy = dy_value + nby_value

    inputs: dict[str, float | None] = {
        "dividend_yield": dy_value,
        "net_buyback_yield": nby_value,
        "net_payout_yield": npy,
    }

    # Merge source filing IDs from DY (NBY has none — market data only)
    source_filing_ids = list(dy_result.source_filing_ids)

    return MetricResult(
        metric_code=MetricCode.net_payout_yield,
        value=npy,
        formula_version=1,
        inputs_snapshot=inputs,
        source_filing_ids=source_filing_ids,
    )
