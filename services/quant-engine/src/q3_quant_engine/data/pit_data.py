"""Point-in-time data layer for survivorship-bias-free backtesting.

All queries filter by availability date so that only data the market could
have seen at `as_of_date` is returned.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from q3_shared_models.entities import (
    ComputedMetric,
    Filing,
    FilingStatus,
    Issuer,
    MarketSnapshot,
    Security,
    StatementLine,
)

logger = logging.getLogger(__name__)


@dataclass
class PITAsset:
    """Lightweight asset representation for PIT queries."""

    ticker: str
    name: str
    sector: str | None
    issuer_id: str
    is_active: bool = True


@dataclass
class PITFinancials:
    """Financial data at a point in time."""

    ebit: Decimal | None = None
    enterprise_value: Decimal | None = None
    net_working_capital: Decimal | None = None
    fixed_assets: Decimal | None = None
    roic: Decimal | None = None
    roe: Decimal | None = None
    net_debt: Decimal | None = None
    ebitda: Decimal | None = None
    net_margin: Decimal | None = None
    gross_margin: Decimal | None = None
    earnings_yield: Decimal | None = None
    debt_to_ebitda: Decimal | None = None
    cash_conversion: Decimal | None = None
    market_cap: Decimal | None = None
    avg_daily_volume: Decimal | None = None


@dataclass
class MarketPriceData:
    """Market price snapshot at a point in time."""

    price: float | None
    market_cap: float | None
    volume: float | None
    fetched_at: datetime


def _as_of_datetime(as_of_date: date) -> datetime:
    """Convert date to end-of-day datetime for comparison with timestamptz."""
    return datetime.combine(as_of_date, datetime.max.time(), tzinfo=timezone.utc)


def fetch_fundamentals_pit(
    session: Session,
    as_of_date: date,
) -> list[tuple[PITAsset, PITFinancials]]:
    """Fetch fundamentals using only data available at as_of_date.

    Rules:
    - Filing.available_at <= as_of_date (when market could see it)
    - For each issuer, latest filing by available_at
    - Restatements only visible from their own available_at forward
    - Ranking happens at security level (primary ticker per issuer)
    """
    cutoff = _as_of_datetime(as_of_date)
    cutoff_date = as_of_date

    # Subquery: latest filing per issuer where the filing was publicly available.
    # Uses publication_date (estimated CVM deadline, from Plan 3C.3) when available,
    # falling back to available_at (import timestamp) for filings without publication_date.
    # This gives correct PIT semantics for historical backtesting.
    pit_date_expr = func.coalesce(Filing.publication_date, Filing.available_at)

    latest_filing = (
        select(
            Filing.issuer_id,
            func.max(Filing.id).label("max_filing_id"),
        )
        .where(
            or_(
                Filing.publication_date <= cutoff_date,
                (Filing.publication_date.is_(None)) & (Filing.available_at <= cutoff),
            ),
            Filing.status == FilingStatus.completed,
        )
        .group_by(Filing.issuer_id)
        .subquery()
    )

    # Get the filings themselves — pick the one with latest reference_date per issuer
    # from among those that are PIT-visible.
    pit_visible_filings = (
        select(Filing)
        .where(
            or_(
                Filing.publication_date <= cutoff_date,
                (Filing.publication_date.is_(None)) & (Filing.available_at <= cutoff),
            ),
            Filing.status == FilingStatus.completed,
        )
        .subquery()
    )

    # For each issuer, pick the filing with the latest reference_date,
    # then latest version, among those that are PIT-visible.
    # publication_date is the preferred PIT gate; available_at is fallback.
    pit_filter = or_(
        Filing.publication_date <= cutoff_date,
        (Filing.publication_date.is_(None)) & (Filing.available_at <= cutoff),
    )
    all_visible = session.execute(
        select(Filing)
        .where(pit_filter, Filing.status == FilingStatus.completed)
        .order_by(Filing.reference_date.desc(), Filing.version_number.desc())
    ).scalars().all()

    # Deduplicate: keep only the best filing per issuer
    # (latest reference_date, then latest version_number)
    seen_issuers: set = set()
    filing_rows: list = []
    for f in all_visible:
        if f.issuer_id not in seen_issuers:
            seen_issuers.add(f.issuer_id)
            filing_rows.append(f)

    filing_by_issuer: dict[str, Filing] = {}
    for f in filing_rows:
        filing_by_issuer[str(f.issuer_id)] = f

    if not filing_by_issuer:
        return []

    # Get primary securities eligible at this date
    eligible_securities = session.execute(
        select(Security, Issuer)
        .join(Issuer, Security.issuer_id == Issuer.id)
        .where(
            Security.is_primary.is_(True),
            Security.valid_from <= as_of_date,
            or_(Security.valid_to.is_(None), Security.valid_to > as_of_date),
            Issuer.id.in_([f.issuer_id for f in filing_by_issuer.values()]),
        )
    ).all()

    results: list[tuple[PITAsset, PITFinancials]] = []

    for security, issuer in eligible_securities:
        issuer_id_str = str(issuer.id)
        filing = filing_by_issuer.get(issuer_id_str)
        if filing is None:
            continue

        asset = PITAsset(
            ticker=security.ticker,
            name=issuer.legal_name or "",
            sector=issuer.sector,
            issuer_id=issuer_id_str,
        )

        # Fetch computed metrics for this issuer at the filing's reference_date
        metrics = session.execute(
            select(ComputedMetric)
            .where(
                ComputedMetric.issuer_id == issuer.id,
                ComputedMetric.reference_date == filing.reference_date,
            )
        ).scalars().all()

        metric_map: dict[str, Decimal | None] = {}
        for m in metrics:
            metric_map[m.metric_code] = Decimal(str(m.value)) if m.value is not None else None

        # Fetch statement lines for EBIT, NWC, fixed_assets
        stmt_lines = session.execute(
            select(StatementLine)
            .where(
                StatementLine.filing_id == filing.id,
                StatementLine.canonical_key.in_(["ebit", "current_assets", "current_liabilities", "fixed_assets"]),
            )
        ).scalars().all()

        line_map: dict[str, Decimal | None] = {}
        for sl in stmt_lines:
            if sl.canonical_key:
                line_map[sl.canonical_key] = Decimal(str(sl.normalized_value)) if sl.normalized_value is not None else None

        nwc = None
        ca = line_map.get("current_assets")
        cl = line_map.get("current_liabilities")
        if ca is not None and cl is not None:
            nwc = ca - cl

        fs = PITFinancials(
            ebit=line_map.get("ebit"),
            enterprise_value=metric_map.get("enterprise_value"),
            net_working_capital=nwc,
            fixed_assets=line_map.get("fixed_assets"),
            roic=metric_map.get("roic"),
            roe=metric_map.get("roe"),
            net_debt=metric_map.get("net_debt"),
            ebitda=metric_map.get("ebitda"),
            net_margin=metric_map.get("net_margin"),
            gross_margin=metric_map.get("gross_margin"),
            earnings_yield=metric_map.get("earnings_yield"),
            debt_to_ebitda=metric_map.get("debt_to_ebitda"),
            cash_conversion=metric_map.get("cash_conversion"),
        )

        results.append((asset, fs))

    logger.info("PIT fundamentals as_of=%s returned %d issuers", as_of_date, len(results))
    return results


def fetch_market_pit(
    session: Session,
    as_of_date: date,
    max_staleness_days: int = 7,
) -> dict[str, MarketPriceData]:
    """Fetch market prices using only snapshots available at as_of_date.

    Rules:
    - fetched_at <= as_of_date
    - fetched_at >= as_of_date - max_staleness_days (exclude stale)
    - For each security, latest snapshot within window
    """
    cutoff = _as_of_datetime(as_of_date)
    stale_cutoff = cutoff - timedelta(days=max_staleness_days)

    # Latest snapshot per security within staleness window
    latest_snap = (
        select(
            MarketSnapshot.security_id,
            func.max(MarketSnapshot.fetched_at).label("max_fetched"),
        )
        .where(
            MarketSnapshot.fetched_at <= cutoff,
            MarketSnapshot.fetched_at >= stale_cutoff,
        )
        .group_by(MarketSnapshot.security_id)
        .subquery()
    )

    rows = session.execute(
        select(MarketSnapshot, Security.ticker)
        .join(Security, MarketSnapshot.security_id == Security.id)
        .join(
            latest_snap,
            (MarketSnapshot.security_id == latest_snap.c.security_id)
            & (MarketSnapshot.fetched_at == latest_snap.c.max_fetched),
        )
        .where(Security.is_primary.is_(True))
    ).all()

    price_map: dict[str, MarketPriceData] = {}
    for snap, ticker in rows:
        price_map[ticker] = MarketPriceData(
            price=float(snap.price) if snap.price is not None else None,
            market_cap=float(snap.market_cap) if snap.market_cap is not None else None,
            volume=float(snap.volume) if snap.volume is not None else None,
            fetched_at=snap.fetched_at,
        )

    logger.info("PIT market as_of=%s returned %d tickers", as_of_date, len(price_map))
    return price_map


def fetch_eligible_universe_pit(
    session: Session,
    as_of_date: date,
) -> set[str]:
    """Return set of tickers that were eligible (listed) at as_of_date.

    Handles survivorship bias: only include securities where
    valid_from <= as_of_date AND (valid_to IS NULL OR valid_to > as_of_date).
    """
    rows = session.execute(
        select(Security.ticker).where(
            Security.is_primary.is_(True),
            Security.valid_from <= as_of_date,
            or_(Security.valid_to.is_(None), Security.valid_to > as_of_date),
        )
    ).all()
    return {r.ticker for r in rows}
