"""Recompute DY/NBY/NPY metrics for all CORE_ELIGIBLE issuers.

Runs the full MetricsEngine for each issuer at their latest reference date,
passing market_cap from the latest snapshot. This recovers Bucket 5b (DY)
and Bucket B (NBY) gaps where data exists but the engine wasn't run.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/recompute_npy_metrics.py
"""
from __future__ import annotations

import logging
import uuid
from collections import Counter

from sqlalchemy import select, text, func

from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.metrics.engine import MetricsEngine
from q3_shared_models.entities import (
    ComputedMetric,
    Filing,
    FilingStatus,
    Issuer,
    MarketSnapshot,
    Security,
    UniverseClassification,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("recompute_npy")

_QUARTER_ENDS = {3: 31, 6: 30, 9: 30, 12: 31}


def _snap_to_quarter_end(d) -> "date":
    """Snap a date to the nearest preceding quarter-end."""
    from datetime import date as _date
    month = d.month
    if month <= 3:
        return _date(d.year, 3, 31)
    elif month <= 6:
        return _date(d.year, 6, 30)
    elif month <= 9:
        return _date(d.year, 9, 30)
    else:
        return _date(d.year, 12, 31)


def main() -> None:
    with SessionLocal() as session:
        # Get all CORE_ELIGIBLE issuers with primary securities
        rows = session.execute(
            select(
                Issuer.id,
                Issuer.cvm_code,
                Issuer.legal_name,
                Security.id.label("security_id"),
            )
            .join(UniverseClassification, UniverseClassification.issuer_id == Issuer.id)
            .join(Security, Security.issuer_id == Issuer.id)
            .where(
                UniverseClassification.universe_class == "CORE_ELIGIBLE",
                UniverseClassification.superseded_at.is_(None),
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).all()

        logger.info("CORE_ELIGIBLE issuers with primary security: %d", len(rows))

        engine = MetricsEngine(session)
        stats = Counter()

        for issuer_id, cvm_code, legal_name, security_id in rows:
            # Get latest reference date from completed filings
            latest_ref = session.execute(
                select(Filing.reference_date)
                .where(Filing.issuer_id == issuer_id, Filing.status == FilingStatus.completed)
                .order_by(Filing.reference_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            if latest_ref is None:
                stats["no_filings"] += 1
                continue

            # Snap to quarter-end (TTM requires quarter-end dates)
            latest_ref = _snap_to_quarter_end(latest_ref)

            # Get latest market_cap from snapshots
            market_cap_row = session.execute(
                select(MarketSnapshot.market_cap)
                .where(
                    MarketSnapshot.security_id == security_id,
                    MarketSnapshot.market_cap.isnot(None),
                )
                .order_by(MarketSnapshot.fetched_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            market_cap = float(market_cap_row) if market_cap_row is not None else None

            metrics = engine.compute_for_issuer(
                issuer_id, latest_ref, market_cap=market_cap,
            )
            stats["computed"] += 1
            stats["metrics"] += len(metrics)

        session.commit()
        logger.info("Done: %s", dict(stats))

        # Refresh compat view
        logger.info("Refreshing compat view...")
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY v_financial_statements_compat"))
        except Exception:
            session.execute(text("REFRESH MATERIALIZED VIEW v_financial_statements_compat"))
        session.commit()
        logger.info("Compat view refreshed.")

        # Report new coverage
        denom = session.execute(text("""
            SELECT count(DISTINCT uc.issuer_id)
            FROM universe_classifications uc
            JOIN securities s ON s.issuer_id = uc.issuer_id AND s.is_primary = true AND s.valid_to IS NULL
            WHERE uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
        """)).scalar()

        for metric in ["dividend_yield", "net_buyback_yield", "net_payout_yield"]:
            count = session.execute(text(f"""
                SELECT count(DISTINCT cm.issuer_id)
                FROM computed_metrics cm
                JOIN universe_classifications uc ON uc.issuer_id = cm.issuer_id
                    AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
                JOIN securities s ON s.issuer_id = cm.issuer_id AND s.is_primary = true AND s.valid_to IS NULL
                WHERE cm.metric_code = '{metric}'
            """)).scalar()
            pct = count / denom * 100 if denom else 0
            print(f"  {metric:25s}: {count}/{denom} = {pct:.1f}%")


if __name__ == "__main__":
    main()
