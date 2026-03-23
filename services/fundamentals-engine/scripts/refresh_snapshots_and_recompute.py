"""Fetch market snapshots for all primary securities + recompute metrics.

Action 2 of the Plan 3A coverage recovery roadmap.
Fetches Yahoo snapshots, then recomputes DY/NBY/NPY for CORE_ELIGIBLE issuers.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/refresh_snapshots_and_recompute.py
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from sqlalchemy import select, text

from q3_fundamentals_engine.config import MARKET_SNAPSHOT_SOURCE
from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.metrics.engine import MetricsEngine
from q3_fundamentals_engine.providers.market_snapshot_factory import MarketSnapshotProviderFactory
from q3_shared_models.entities import (
    Filing,
    FilingStatus,
    Issuer,
    MarketSnapshot,
    Security,
    SourceProvider,
    UniverseClassification,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("refresh_snapshots")

_QUARTER_ENDS = {3: 31, 6: 30, 9: 30, 12: 31}


def _snap_to_quarter_end(d):
    from datetime import date
    month = d.month
    if month <= 3:
        return date(d.year, 3, 31)
    elif month <= 6:
        return date(d.year, 6, 30)
    elif month <= 9:
        return date(d.year, 9, 30)
    else:
        return date(d.year, 12, 31)


def main() -> None:
    source = MARKET_SNAPSHOT_SOURCE
    logger.info("Starting snapshot refresh (source=%s)", source)

    # Phase 1: Fetch snapshots
    with SessionLocal() as session:
        adapter = MarketSnapshotProviderFactory.create(source)
        source_enum = SourceProvider[source]

        securities = session.execute(
            select(Security).where(
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).scalars().all()

        logger.info("Fetching snapshots for %d primary securities", len(securities))

        loop = asyncio.new_event_loop()
        created = 0
        failures = 0
        try:
            for sec in securities:
                try:
                    snap_data = loop.run_until_complete(adapter.get_snapshot(sec.ticker))
                except Exception:
                    logger.warning("Failed: %s", sec.ticker)
                    failures += 1
                    continue

                if snap_data:
                    snapshot = MarketSnapshot(
                        id=uuid.uuid4(),
                        security_id=sec.id,
                        source=source_enum,
                        price=snap_data.price,
                        market_cap=snap_data.market_cap,
                        volume=snap_data.volume,
                        raw_json=snap_data.raw_json,
                        shares_outstanding=snap_data.shares_outstanding,
                    )
                    session.add(snapshot)
                    created += 1
                else:
                    failures += 1

                time.sleep(0.3)
        finally:
            loop.close()

        session.commit()
        logger.info("Snapshots: created=%d, failures=%d, total=%d", created, failures, len(securities))

    # Phase 2: Recompute metrics for CORE_ELIGIBLE
    logger.info("Recomputing metrics for CORE_ELIGIBLE issuers...")
    with SessionLocal() as session:
        rows = session.execute(
            select(Issuer.id, Security.id.label("security_id"))
            .join(UniverseClassification, UniverseClassification.issuer_id == Issuer.id)
            .join(Security, Security.issuer_id == Issuer.id)
            .where(
                UniverseClassification.universe_class == "CORE_ELIGIBLE",
                UniverseClassification.superseded_at.is_(None),
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).all()

        engine = MetricsEngine(session)
        computed = 0

        for issuer_id, security_id in rows:
            latest_ref = session.execute(
                select(Filing.reference_date)
                .where(Filing.issuer_id == issuer_id, Filing.status == FilingStatus.completed)
                .order_by(Filing.reference_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            if latest_ref is None:
                continue

            latest_ref = _snap_to_quarter_end(latest_ref)

            market_cap_row = session.execute(
                select(MarketSnapshot.market_cap)
                .where(MarketSnapshot.security_id == security_id, MarketSnapshot.market_cap.isnot(None))
                .order_by(MarketSnapshot.fetched_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            market_cap = float(market_cap_row) if market_cap_row is not None else None
            engine.compute_for_issuer(issuer_id, latest_ref, market_cap=market_cap)
            computed += 1

        session.commit()
        logger.info("Recomputed metrics for %d issuers", computed)

        # Refresh compat view
        logger.info("Refreshing compat view...")
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY v_financial_statements_compat"))
        except Exception:
            session.execute(text("REFRESH MATERIALIZED VIEW v_financial_statements_compat"))
        session.commit()
        logger.info("Compat view refreshed.")

        # Report coverage
        print("\n" + "=" * 60)
        print("Coverage Report — post Action 2")
        print("=" * 60)
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
            gate = {"dividend_yield": 70, "net_buyback_yield": 80, "net_payout_yield": 60}[metric]
            status = "PASS" if pct >= gate else "FAIL"
            print(f"  {metric:25s}: {count}/{denom} = {pct:.1f}%  (gate >={gate}%)  {status}")
        print("=" * 60)


if __name__ == "__main__":
    main()
