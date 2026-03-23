"""TTM (Trailing Twelve Months) quarter extraction and aggregation.

CVM ITR stores YTD accumulated values. This module extracts standalone
quarterly values and computes TTM sums across 4 consecutive quarters.

Rules (from Plan 3A Operational Metric Spec §6.4):
- Q_standalone(q) = YTD(q) - YTD(q-1); Q1 is standalone by itself
- DFP prevails over ITR for Q4 (same ref_date)
- All 4 quarters must use the same scope (con/ind)
- TTM = NULL if any quarter is missing
- Use MAX(version_number) per filing/ref_date (latest restatement)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select, func, case, literal_column
from sqlalchemy.orm import Session

from q3_shared_models.entities import (
    Filing,
    FilingStatus,
    FilingType,
    ScopeType,
    StatementLine,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuarterValue:
    """A single quarter's YTD value from the best available filing."""

    reference_date: date
    scope: ScopeType
    ytd_value: float
    filing_id: uuid.UUID
    filing_type: FilingType


_QUARTER_ENDS = {3: 31, 6: 30, 9: 30, 12: 31}


def snap_to_quarter_end(d: date) -> date:
    """Snap a date to the nearest quarter-end at or after the date's month.

    Non-quarter-end dates are mapped to the quarter-end of the current quarter.
    Already-quarter-end dates are returned unchanged.
    """
    month = d.month
    if month <= 3:
        return date(d.year, 3, 31)
    elif month <= 6:
        return date(d.year, 6, 30)
    elif month <= 9:
        return date(d.year, 9, 30)
    else:
        return date(d.year, 12, 31)


def _subtract_quarter(d: date) -> date:
    """Subtract one quarter from a quarter-end date.

    If d is not a quarter-end, it is snapped first.
    """
    d = snap_to_quarter_end(d)
    if d.month <= 3:
        return date(d.year - 1, 12, 31)
    new_month = d.month - 3
    return date(d.year, new_month, _QUARTER_ENDS[new_month])


def quarter_end_dates(as_of: date) -> list[date]:
    """Return the 4 quarter-end dates ending at as_of (inclusive).

    If as_of is not a quarter-end, it is snapped to the nearest quarter-end first.
    Returns [t-3, t-2, t-1, t] in chronological order.
    """
    as_of = snap_to_quarter_end(as_of)
    dates: list[date] = []
    d = as_of
    for _ in range(4):
        dates.append(d)
        d = _subtract_quarter(d)
    dates.reverse()
    return dates


def _previous_quarter_end(ref: date) -> date | None:
    """Return the quarter-end date immediately before ref, or None if ref is Q1."""
    if ref.month == 3:
        return None  # Q1 — standalone by itself
    return _subtract_quarter(ref)


def load_quarterly_ytd_values(
    session: Session,
    issuer_id: uuid.UUID,
    canonical_key: str,
    quarter_dates: list[date],
    *,
    knowledge_date: date | None = None,
) -> dict[date, list[QuarterValue]]:
    """Load YTD values for the given canonical key across quarter dates.

    Returns a dict mapping reference_date -> list of QuarterValue
    (one per scope, best version per filing_type).
    """
    if not quarter_dates:
        return {}

    # We need YTD values for each quarter date AND the prior quarter dates
    # (for deaccumulation). Build the full set of dates needed.
    all_dates_needed: set[date] = set()
    for qd in quarter_dates:
        all_dates_needed.add(qd)
        prev = _previous_quarter_end(qd)
        if prev is not None:
            all_dates_needed.add(prev)

    # Expand date range to catch non-standard fiscal year-ends.
    # E.g., CAML3 has November FYE (filings at 2024-11-30 instead of 2024-12-31).
    # We query a continuous range covering all needed dates ±35 days.
    min_date = min(all_dates_needed) - timedelta(days=35)
    max_date = max(all_dates_needed) + timedelta(days=35)

    # Query: for each (ref_date, scope, filing_type), get the value
    # from the latest version filing.
    # DFP filing_type sorts before ITR (alphabetically), so we use
    # a priority column to ensure DFP prevails for same ref_date.
    filing_type_priority = case(
        (Filing.filing_type == FilingType.DFP, literal_column("1")),
        else_=literal_column("2"),
    )

    # Subquery: rank by (ref_date, scope) with DFP first, then latest version.
    # Uses date range instead of exact match to catch non-standard FYE dates.
    subq_query = (
        select(
            StatementLine.reference_date,
            StatementLine.scope,
            StatementLine.normalized_value,
            Filing.id.label("filing_id"),
            Filing.filing_type,
            Filing.version_number,
            func.row_number()
            .over(
                partition_by=[StatementLine.reference_date, StatementLine.scope],
                order_by=[filing_type_priority, Filing.version_number.desc()],
            )
            .label("rn"),
        )
        .join(Filing, StatementLine.filing_id == Filing.id)
        .where(
            Filing.issuer_id == issuer_id,
            Filing.status == FilingStatus.completed,
            StatementLine.canonical_key == canonical_key,
            StatementLine.reference_date >= min_date,
            StatementLine.reference_date <= max_date,
        )
    )

    # PIT enforcement: only use filings published by the knowledge_date
    if knowledge_date is not None:
        subq_query = subq_query.where(Filing.publication_date <= knowledge_date)

    subq = subq_query.subquery(
    )

    rows = session.execute(
        select(
            subq.c.reference_date,
            subq.c.scope,
            subq.c.normalized_value,
            subq.c.filing_id,
            subq.c.filing_type,
        ).where(subq.c.rn == 1)
    ).all()

    # Map each filing's reference_date to the nearest needed quarter-end.
    # This handles non-standard FYE (e.g., 2024-11-30 maps to 2024-12-31).
    sorted_needed = sorted(all_dates_needed)

    def _nearest_quarter(ref: date) -> date | None:
        """Find the nearest date in all_dates_needed within 35 days."""
        best = None
        best_dist = 36  # beyond threshold
        for qd in sorted_needed:
            dist = abs((ref - qd).days)
            if dist < best_dist:
                best = qd
                best_dist = dist
        return best

    result: dict[date, list[QuarterValue]] = {}
    for ref_date, scope, value, fid, ftype in rows:
        if value is None:
            continue
        # Map to nearest quarter-end
        mapped_date = _nearest_quarter(ref_date)
        if mapped_date is None:
            continue
        qv = QuarterValue(
            reference_date=mapped_date,
            scope=ScopeType(scope),
            ytd_value=float(value),
            filing_id=fid,
            filing_type=FilingType(ftype),
        )
        # Only keep the first (best) value per mapped_date+scope
        existing = result.get(mapped_date, [])
        if not any(e.scope == qv.scope for e in existing):
            result.setdefault(mapped_date, []).append(qv)

    return result


def extract_standalone_quarters(
    ytd_data: dict[date, list[QuarterValue]],
    quarter_dates: list[date],
    preferred_scope: ScopeType = ScopeType.con,
) -> list[tuple[date, float, uuid.UUID]] | None:
    """Convert YTD values into standalone quarterly values.

    Returns list of (ref_date, standalone_value, filing_id) for all 4 quarters,
    or None if any quarter is incomplete.

    All 4 quarters must use the same scope. Tries preferred_scope first,
    falls back to the other scope.
    """
    for scope in [preferred_scope, _other_scope(preferred_scope)]:
        result = _try_extract_for_scope(ytd_data, quarter_dates, scope)
        if result is not None:
            return result
    return None


def _other_scope(scope: ScopeType) -> ScopeType:
    return ScopeType.ind if scope == ScopeType.con else ScopeType.con


def _get_value_for_scope(
    values: list[QuarterValue], scope: ScopeType
) -> QuarterValue | None:
    for v in values:
        if v.scope == scope:
            return v
    return None


def _try_extract_for_scope(
    ytd_data: dict[date, list[QuarterValue]],
    quarter_dates: list[date],
    scope: ScopeType,
) -> list[tuple[date, float, uuid.UUID]] | None:
    """Try to extract 4 standalone quarters for a given scope."""
    standalones: list[tuple[date, float, uuid.UUID]] = []

    for qd in quarter_dates:
        values_at_qd = ytd_data.get(qd, [])
        qv = _get_value_for_scope(values_at_qd, scope)
        if qv is None:
            return None

        prev_qe = _previous_quarter_end(qd)
        if prev_qe is None:
            # Q1: YTD is standalone
            standalones.append((qd, qv.ytd_value, qv.filing_id))
        else:
            # Q2/Q3/Q4: standalone = YTD(q) - YTD(q-1)
            prev_values = ytd_data.get(prev_qe, [])
            prev_qv = _get_value_for_scope(prev_values, scope)
            if prev_qv is None:
                return None
            standalone = qv.ytd_value - prev_qv.ytd_value
            standalones.append((qd, standalone, qv.filing_id))

    return standalones


def compute_ttm_sum(
    session: Session,
    issuer_id: uuid.UUID,
    canonical_key: str,
    as_of: date,
    *,
    knowledge_date: date | None = None,
) -> tuple[float, list[str], dict] | None:
    """Compute TTM sum for a canonical key.

    Returns (ttm_sum, filing_ids, inputs_snapshot) or None if incomplete.
    The inputs_snapshot records each quarter's standalone value for auditability.
    """
    dates = quarter_end_dates(as_of)
    ytd_data = load_quarterly_ytd_values(
        session, issuer_id, canonical_key, dates,
        knowledge_date=knowledge_date,
    )

    standalones = extract_standalone_quarters(ytd_data, dates)
    if standalones is None:
        logger.debug(
            "Incomplete TTM for issuer=%s key=%s as_of=%s",
            issuer_id, canonical_key, as_of,
        )
        return None

    ttm_sum = sum(val for _, val, _ in standalones)
    filing_ids = sorted({str(fid) for _, _, fid in standalones})
    inputs = {
        f"q{i+1}_{canonical_key}": val
        for i, (_, val, _) in enumerate(standalones)
    }
    inputs[f"{canonical_key}_ttm"] = ttm_sum

    return ttm_sum, filing_ids, inputs
