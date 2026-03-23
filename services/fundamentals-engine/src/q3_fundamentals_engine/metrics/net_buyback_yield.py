"""Net Buyback Yield metric.

NetBuybackYield = (Shares(t-4) - Shares(t)) / Shares(t-4)

Positive = net buyback (good for shareholders).
Negative = net dilution (share issuance).

See Plan 3A §6.3.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy.orm import Session

from q3_shared_models.entities import MetricCode

from q3_fundamentals_engine.metrics.base import MetricResult
from q3_fundamentals_engine.metrics.snapshot_anchor import find_anchored_snapshot
from q3_fundamentals_engine.metrics.ttm import _subtract_quarter

logger = logging.getLogger(__name__)


def _quarter_4_ago(as_of: date) -> date:
    """Return the quarter-end date 4 quarters before as_of."""
    d = as_of
    for _ in range(4):
        d = _subtract_quarter(d)
    return d


def compute_net_buyback_yield(
    session: Session,
    issuer_id: uuid.UUID,
    as_of: date,
    *,
    knowledge_date: date | None = None,
) -> MetricResult | None:
    """Compute Net Buyback Yield for an issuer.

    Returns None if shares_outstanding is unavailable at t or t-4.
    """
    # Shares at t (current quarter)
    snap_t = find_anchored_snapshot(session, issuer_id, as_of, knowledge_date=knowledge_date)
    if snap_t is None or snap_t.shares_outstanding is None:
        logger.debug("No shares_outstanding at t=%s for issuer=%s", as_of, issuer_id)
        return None

    shares_t = float(snap_t.shares_outstanding)
    if shares_t <= 0:
        logger.debug("shares_outstanding <= 0 at t=%s for issuer=%s", as_of, issuer_id)
        return None

    # Shares at t-4 (4 quarters ago)
    t4_date = _quarter_4_ago(as_of)
    snap_t4 = find_anchored_snapshot(session, issuer_id, t4_date, knowledge_date=knowledge_date)
    if snap_t4 is None or snap_t4.shares_outstanding is None:
        logger.debug("No shares_outstanding at t-4=%s for issuer=%s", t4_date, issuer_id)
        return None

    shares_t4 = float(snap_t4.shares_outstanding)
    if shares_t4 <= 0:
        logger.debug("shares_outstanding <= 0 at t-4=%s for issuer=%s", t4_date, issuer_id)
        return None

    nby = (shares_t4 - shares_t) / shares_t4

    inputs = {
        "shares_t": shares_t,
        "shares_t4": shares_t4,
        "t_date": str(as_of),
        "t4_date": str(t4_date),
        "t_snapshot_fetched_at": str(snap_t.fetched_at),
        "t4_snapshot_fetched_at": str(snap_t4.fetched_at),
        "net_buyback_yield": nby,
    }

    return MetricResult(
        metric_code=MetricCode.net_buyback_yield,
        value=nby,
        formula_version=1,
        inputs_snapshot=inputs,
        source_filing_ids=[],  # No CVM filings involved — market data only
    )
