"""Dividend Yield TTM metric.

DividendYield_TTM = abs(TTM shareholder_distributions) / market_cap

Requires TTM data (4 quarters of shareholder_distributions from DFC)
and market_cap from market_snapshots. See Plan 3A §6.2.

If the issuer has DFC filings covering the TTM window but no
shareholder_distributions lines, DY = 0 (company doesn't pay dividends).
This is distinct from NULL (insufficient data to compute).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select, func, exists
from sqlalchemy.orm import Session

from q3_shared_models.entities import (
    Filing,
    FilingStatus,
    MetricCode,
    StatementLine,
)

from q3_fundamentals_engine.metrics.base import MetricResult
from q3_fundamentals_engine.metrics.ttm import compute_ttm_sum, quarter_end_dates

logger = logging.getLogger(__name__)


def _has_dfc_coverage(
    session: Session,
    issuer_id: uuid.UUID,
    quarter_dates: list[date],
) -> bool:
    """Check if the issuer has DFC filings covering at least 3 of the 4 TTM quarters.

    This is used to distinguish "no distributions (DY=0)" from
    "no data at all (DY=NULL)".
    """
    covered = session.execute(
        select(func.count(func.distinct(Filing.reference_date)))
        .where(
            Filing.issuer_id == issuer_id,
            Filing.status == FilingStatus.completed,
            Filing.reference_date.in_(quarter_dates),
        )
        .where(
            exists(
                select(StatementLine.id)
                .where(
                    StatementLine.filing_id == Filing.id,
                    StatementLine.statement_type.in_(["DFC_MD", "DFC_MI"]),
                )
            )
        )
    ).scalar()
    return covered is not None and covered >= 3


def compute_dividend_yield(
    session: Session,
    issuer_id: uuid.UUID,
    as_of: date,
    market_cap: float | None,
    *,
    knowledge_date: date | None = None,
) -> MetricResult | None:
    """Compute Dividend Yield TTM for an issuer.

    Returns None if market_cap is unavailable or DFC data is insufficient.
    Returns DY=0 if the issuer has DFC filings but no shareholder distributions
    (company genuinely doesn't pay dividends).
    """
    if market_cap is None or market_cap <= 0:
        logger.debug("No valid market_cap for issuer=%s; skipping dividend_yield", issuer_id)
        return None

    ttm_result = compute_ttm_sum(
        session, issuer_id, "shareholder_distributions", as_of,
        knowledge_date=knowledge_date,
    )

    if ttm_result is not None:
        ttm_sum, filing_ids, inputs = ttm_result
        dy = abs(ttm_sum) / market_cap
        inputs["market_cap"] = market_cap
        inputs["dividend_yield"] = dy
        return MetricResult(
            metric_code=MetricCode.dividend_yield,
            value=dy,
            formula_version=2,
            inputs_snapshot=inputs,
            source_filing_ids=filing_ids,
        )

    # TTM returned None — check if this is "no distributions" vs "no data"
    try:
        qdates = quarter_end_dates(as_of)
    except (KeyError, ValueError):
        return None

    if _has_dfc_coverage(session, issuer_id, qdates):
        # Issuer has DFC filings but no distribution lines → DY = 0
        logger.debug(
            "issuer=%s has DFC coverage but no distributions; DY=0", issuer_id
        )
        return MetricResult(
            metric_code=MetricCode.dividend_yield,
            value=0.0,
            formula_version=2,
            inputs_snapshot={
                "shareholder_distributions_ttm": 0.0,
                "market_cap": market_cap,
                "dividend_yield": 0.0,
                "zero_reason": "no_distribution_lines_in_dfc",
            },
            source_filing_ids=[],
        )

    return None
