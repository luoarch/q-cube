"""Multi-period data loader for refiner scoring.

Queries computed_metrics + statement_lines for N consecutive reference_dates.
"""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import select, distinct
from sqlalchemy.orm import Session

from q3_shared_models.entities import (
    ComputedMetric,
    Filing,
    Issuer,
    PeriodType,
    Security,
    StatementLine,
)
from q3_quant_engine.refiner.types import PeriodValue

logger = logging.getLogger(__name__)

# Canonical keys used by refiner (from statement_lines)
STATEMENT_KEYS = {
    "revenue", "cost_of_goods_sold", "gross_profit", "operating_expenses",
    "ebit", "financial_result", "ebt", "income_tax", "net_income",
    "total_assets", "current_assets", "cash_and_equivalents",
    "non_current_assets", "fixed_assets", "intangible_assets",
    "total_liabilities", "current_liabilities", "short_term_debt",
    "non_current_liabilities", "long_term_debt", "equity",
    "cash_from_operations", "cash_from_investing", "cash_from_financing",
}

# Computed metric codes used by refiner
COMPUTED_METRIC_CODES = {
    "ebitda", "net_debt", "roic", "roe", "earnings_yield",
    "gross_margin", "ebit_margin", "net_margin", "enterprise_value",
    "cash_conversion", "debt_to_ebitda",
}


def _get_reference_dates(
    session: Session,
    issuer_id: UUID,
    n_periods: int,
    period_type: str,
) -> list[date]:
    """Get N most recent distinct reference_dates for an issuer from computed_metrics."""
    stmt = (
        select(distinct(ComputedMetric.reference_date))
        .where(
            ComputedMetric.issuer_id == issuer_id,
            ComputedMetric.period_type == PeriodType(period_type),
        )
        .order_by(ComputedMetric.reference_date.desc())
        .limit(n_periods)
    )
    rows = session.execute(stmt).scalars().all()
    return sorted(rows)  # chronological order: oldest first


def _load_statement_values(
    session: Session,
    issuer_id: UUID,
    reference_dates: list[date],
    period_type: str,
) -> dict[str, list[PeriodValue]]:
    """Load statement_lines for given reference dates, keyed by canonical_key."""
    if not reference_dates:
        return {}

    stmt = (
        select(
            StatementLine.canonical_key,
            StatementLine.reference_date,
            StatementLine.normalized_value,
            Filing.version_number,
        )
        .join(Filing, Filing.id == StatementLine.filing_id)
        .where(
            Filing.issuer_id == issuer_id,
            StatementLine.reference_date.in_(reference_dates),
            StatementLine.period_type == PeriodType(period_type),
            StatementLine.canonical_key.isnot(None),
            StatementLine.canonical_key.in_(STATEMENT_KEYS),
            StatementLine.scope == "con",  # prefer consolidated
        )
        .order_by(
            StatementLine.canonical_key,
            StatementLine.reference_date,
            Filing.version_number.desc(),
        )
    )

    rows = session.execute(stmt).all()

    result: dict[str, list[PeriodValue]] = {}
    seen: set[tuple[str, date]] = set()

    for canonical_key, ref_date, value, _version in rows:
        key = (canonical_key, ref_date)
        if key in seen:
            continue
        seen.add(key)

        if canonical_key not in result:
            result[canonical_key] = []
        result[canonical_key].append(PeriodValue(
            reference_date=ref_date,
            value=float(value) if value is not None else None,
        ))

    return result


def _load_computed_metrics(
    session: Session,
    issuer_id: UUID,
    reference_dates: list[date],
    period_type: str,
) -> dict[str, list[PeriodValue]]:
    """Load computed_metrics for given reference dates, keyed by metric_code."""
    if not reference_dates:
        return {}

    stmt = (
        select(
            ComputedMetric.metric_code,
            ComputedMetric.reference_date,
            ComputedMetric.value,
        )
        .where(
            ComputedMetric.issuer_id == issuer_id,
            ComputedMetric.reference_date.in_(reference_dates),
            ComputedMetric.period_type == PeriodType(period_type),
            ComputedMetric.metric_code.in_(COMPUTED_METRIC_CODES),
        )
        .order_by(ComputedMetric.metric_code, ComputedMetric.reference_date)
    )

    rows = session.execute(stmt).all()
    result: dict[str, list[PeriodValue]] = {}

    for metric_code, ref_date, value in rows:
        if metric_code not in result:
            result[metric_code] = []
        result[metric_code].append(PeriodValue(
            reference_date=ref_date,
            value=float(value) if value is not None else None,
        ))

    return result


def load_multi_period_data(
    session: Session,
    issuer_id: UUID,
    n_periods: int = 3,
    period_type: str = "annual",
) -> tuple[dict[str, list[PeriodValue]], int]:
    """Load all multi-period data for an issuer.

    Returns (merged_data, periods_available).
    """
    reference_dates = _get_reference_dates(session, issuer_id, n_periods, period_type)
    if not reference_dates:
        return {}, 0

    statement_data = _load_statement_values(session, issuer_id, reference_dates, period_type)
    computed_data = _load_computed_metrics(session, issuer_id, reference_dates, period_type)

    merged = {**statement_data, **computed_data}
    return merged, len(reference_dates)


def get_issuer_for_ticker(session: Session, ticker: str) -> tuple[UUID, str | None, str | None] | None:
    """Resolve ticker to (issuer_id, sector, subsector) via securities table."""
    stmt = (
        select(Issuer.id, Issuer.sector, Issuer.subsector)
        .join(Security, Security.issuer_id == Issuer.id)
        .where(Security.ticker == ticker, Security.valid_to.is_(None))
        .limit(1)
    )
    row = session.execute(stmt).one_or_none()
    if row is None:
        return None
    return row[0], row[1], row[2]


def get_primary_ticker(session: Session, issuer_id: UUID) -> str | None:
    """Get the primary ticker for an issuer."""
    stmt = (
        select(Security.ticker)
        .where(
            Security.issuer_id == issuer_id,
            Security.is_primary.is_(True),
            Security.valid_to.is_(None),
        )
        .limit(1)
    )
    result = session.execute(stmt).scalar_one_or_none()
    if result:
        return result

    # Fallback: any active ticker
    stmt = (
        select(Security.ticker)
        .where(Security.issuer_id == issuer_id, Security.valid_to.is_(None))
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()
