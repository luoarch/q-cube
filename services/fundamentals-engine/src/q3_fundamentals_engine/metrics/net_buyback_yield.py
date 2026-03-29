"""Net Buyback Yield metric — v2 (CVM primary, Yahoo fallback).

NBY = (Shares(t-4) - Shares(t)) / Shares(t-4)

Positive = net buyback (good for shareholders).
Negative = net dilution (share issuance).

v2 (Plan 5): CVM composicao_capital as primary source via find_cvm_shares().
Yahoo market_snapshots as fallback via find_anchored_snapshot().
Split detection: ratio > 5x or < 0.2x → None.

See Plan 3A §6.3, Plan 5 §6.1/6.4.
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
# Lookup only — metric does NOT import parser or loader (Plan 5 §6.3)
from q3_fundamentals_engine.shares.lookup import find_cvm_shares

logger = logging.getLogger(__name__)

SPLIT_RATIO_THRESHOLD = 5.0  # skip if shares ratio > 5x or < 0.2x


def _quarter_4_ago(as_of: date) -> date:
    """Return the quarter-end date 4 quarters before as_of."""
    d = as_of
    for _ in range(4):
        d = _subtract_quarter(d)
    return d


def _resolve_shares(
    session: Session,
    issuer_id: uuid.UUID,
    target_date: date,
    *,
    knowledge_date: date | None = None,
) -> tuple[float, str, dict] | None:
    """Resolve shares_outstanding for a quarter-end date.

    Returns (shares, source, provenance_dict) or None.
    Tries CVM first (exact match), then Yahoo fallback.
    """
    # 1. CVM primary — exact match by quarter-end (Plan 5 §6.4)
    cvm = find_cvm_shares(session, issuer_id, target_date, knowledge_date=knowledge_date)
    if cvm is not None and cvm.net_shares is not None:
        net = float(cvm.net_shares)
        if net > 0:
            return net, "cvm", {
                "net_shares": net,
                "total_shares": float(cvm.total_shares),
                "treasury_shares": float(cvm.treasury_shares),
                "document_type": cvm.document_type,
                "reference_date": str(cvm.reference_date),
                "publication_date_estimated": str(cvm.publication_date_estimated),
            }

    # 2. Yahoo fallback — anchored snapshot (+/- 30 days)
    snap = find_anchored_snapshot(session, issuer_id, target_date, knowledge_date=knowledge_date)
    if snap is not None and snap.shares_outstanding is not None:
        shares = float(snap.shares_outstanding)
        if shares > 0:
            return shares, "yahoo", {
                "shares_outstanding": shares,
                "fetched_at": str(snap.fetched_at),
            }

    return None


def compute_net_buyback_yield(
    session: Session,
    issuer_id: uuid.UUID,
    as_of: date,
    *,
    knowledge_date: date | None = None,
) -> MetricResult | None:
    """Compute Net Buyback Yield v2 for an issuer.

    CVM composicao_capital as primary source, Yahoo as fallback.
    Returns None if shares unavailable at t or t-4, or if split detected.
    """
    # Shares at t (current quarter)
    t_result = _resolve_shares(session, issuer_id, as_of, knowledge_date=knowledge_date)
    if t_result is None:
        logger.debug("No shares at t=%s for issuer=%s", as_of, issuer_id)
        return None

    shares_t, source_t, prov_t = t_result

    # Shares at t-4 (4 quarters ago)
    t4_date = _quarter_4_ago(as_of)
    t4_result = _resolve_shares(session, issuer_id, t4_date, knowledge_date=knowledge_date)
    if t4_result is None:
        logger.debug("No shares at t-4=%s for issuer=%s", t4_date, issuer_id)
        return None

    shares_t4, source_t4, prov_t4 = t4_result

    # Split detection (Plan 5 §R4)
    ratio = shares_t / shares_t4
    if ratio > SPLIT_RATIO_THRESHOLD or ratio < (1 / SPLIT_RATIO_THRESHOLD):
        logger.warning(
            "Possible split for issuer=%s: ratio=%.2f (t=%s t4=%s), skipping",
            issuer_id, ratio, as_of, t4_date,
        )
        return None

    nby = (shares_t4 - shares_t) / shares_t4

    inputs = {
        "shares_t": shares_t,
        "shares_t4": shares_t4,
        "source_t": source_t,
        "source_t4": source_t4,
        "t_date": str(as_of),
        "t4_date": str(t4_date),
        "t_provenance": prov_t,
        "t4_provenance": prov_t4,
        "share_ratio_t_over_t4": round(ratio, 6),
        "net_buyback_yield": nby,
    }

    return MetricResult(
        metric_code=MetricCode.net_buyback_yield,
        value=nby,
        formula_version=2,
        inputs_snapshot=inputs,  # type: ignore[arg-type]  # v2 has nested dicts for provenance
        source_filing_ids=[],
    )
