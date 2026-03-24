"""Valuation proxy — EY percentile normalization."""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from q3_quant_engine.decision.types import ValuationBlock, ValuationLabel

logger = logging.getLogger(__name__)

CHEAP_THRESHOLD = 70  # percentile
EXPENSIVE_THRESHOLD = 30
MIN_SECTOR_SIZE = 5


def compute_valuation(
    session: Session,
    issuer_id: str,
    ticker: str,
    sector: str | None,
) -> ValuationBlock:
    """Compute valuation proxy from EY percentile within sector and universe."""
    block = ValuationBlock()

    # Get this issuer's EY
    ey_row = session.execute(text("""
        SELECT value FROM computed_metrics
        WHERE issuer_id = :iid AND metric_code = 'earnings_yield'
        ORDER BY reference_date DESC LIMIT 1
    """), {"iid": issuer_id}).fetchone()

    if not ey_row or ey_row[0] is None:
        return block

    ey = float(ey_row[0])
    block.earnings_yield = ey

    # Get current price + market data
    price_row = session.execute(text("""
        SELECT ms.price, ms.market_cap, ms.shares_outstanding
        FROM market_snapshots ms
        JOIN securities se ON se.id = ms.security_id
        WHERE se.issuer_id = :iid AND se.is_primary = true AND se.valid_to IS NULL
        ORDER BY ms.fetched_at DESC LIMIT 1
    """), {"iid": issuer_id}).fetchone()

    if price_row and price_row[0]:
        block.current_price = float(price_row[0])

    # Get universe EY distribution
    universe_eys = session.execute(text("""
        SELECT cm.value
        FROM computed_metrics cm
        JOIN universe_classifications uc ON uc.issuer_id = cm.issuer_id
            AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
        WHERE cm.metric_code = 'earnings_yield' AND cm.value IS NOT NULL
    """)).fetchall()
    universe_values = sorted(float(r[0]) for r in universe_eys if r[0] is not None)

    if not universe_values:
        return block

    # Universe percentile
    below = sum(1 for v in universe_values if v < ey)
    block.ey_universe_percentile = round(below / len(universe_values) * 100, 1)

    # Sector EY distribution
    sector_fallback = False
    if sector:
        sector_eys = session.execute(text("""
            SELECT cm.value
            FROM computed_metrics cm
            JOIN issuers i ON i.id = cm.issuer_id
            JOIN universe_classifications uc ON uc.issuer_id = cm.issuer_id
                AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
            WHERE cm.metric_code = 'earnings_yield' AND cm.value IS NOT NULL
              AND i.sector = :sector
        """), {"sector": sector}).fetchall()
        sector_values = sorted(float(r[0]) for r in sector_eys if r[0] is not None)
    else:
        sector_values = []

    if len(sector_values) >= MIN_SECTOR_SIZE:
        below_s = sum(1 for v in sector_values if v < ey)
        block.ey_sector_percentile = round(below_s / len(sector_values) * 100, 1)
        block.ey_sector_median = float(sorted(sector_values)[len(sector_values) // 2])
        block.sector_issuers_count = len(sector_values)
    else:
        # Fallback to universe
        sector_fallback = True
        block.ey_sector_percentile = block.ey_universe_percentile
        block.ey_sector_median = float(universe_values[len(universe_values) // 2])
        block.sector_issuers_count = len(sector_values)

    block.sector_fallback = sector_fallback

    # Valuation label
    pctl = block.ey_sector_percentile or 50
    if pctl >= CHEAP_THRESHOLD:
        block.label = ValuationLabel.CHEAP
    elif pctl >= EXPENSIVE_THRESHOLD:
        block.label = ValuationLabel.FAIR
    else:
        block.label = ValuationLabel.EXPENSIVE

    # Implied value range (proxy)
    if block.ey_sector_median and block.ey_sector_median > 0:
        ebit_row = session.execute(text("""
            SELECT sl.normalized_value
            FROM statement_lines sl
            JOIN filings f ON f.id = sl.filing_id
            WHERE f.issuer_id = :iid AND sl.canonical_key = 'ebit'
              AND f.status = 'completed'
            ORDER BY f.reference_date DESC, f.version_number DESC
            LIMIT 1
        """), {"iid": issuer_id}).fetchone()

        net_debt_row = session.execute(text("""
            SELECT value FROM computed_metrics
            WHERE issuer_id = :iid AND metric_code = 'net_debt'
            ORDER BY reference_date DESC LIMIT 1
        """), {"iid": issuer_id}).fetchone()

        shares = float(price_row[2]) if price_row and price_row[2] else None

        if ebit_row and ebit_row[0] and net_debt_row and shares and shares > 0:
            ebit = float(ebit_row[0])
            net_debt = float(net_debt_row[0]) if net_debt_row[0] else 0
            implied_ev = ebit / block.ey_sector_median
            implied_equity = implied_ev - net_debt
            if implied_equity > 0:
                implied_price = implied_equity / shares
                block.implied_price = round(implied_price, 2)
                block.implied_value_range = (
                    round(implied_price * 0.85, 2),
                    round(implied_price * 1.15, 2),
                )
                if block.current_price and block.current_price > 0:
                    block.upside = round((implied_price / block.current_price) - 1, 4)

    return block
