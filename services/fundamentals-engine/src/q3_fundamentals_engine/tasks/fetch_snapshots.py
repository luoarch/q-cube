"""Celery tasks for market snapshot fetching and market-dependent metric computation."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from q3_shared_models.entities import (
    Filing,
    FilingStatus,
    Issuer,
    MarketSnapshot,
    Security,
    SourceProvider,
)
from sqlalchemy import select

from q3_fundamentals_engine.celery_app import celery_app
from q3_fundamentals_engine.config import ENABLE_BRAPI
from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.metrics.engine import MetricsEngine
from q3_fundamentals_engine.pipeline_steps import step_refresh_compat_view
from q3_fundamentals_engine.providers.brapi.adapter import BrapiProviderAdapter

logger = logging.getLogger(__name__)

# Snapshots older than this are considered stale and won't feed metrics
SNAPSHOT_STALENESS = timedelta(days=7)


@celery_app.task(name="q3_fundamentals_engine.tasks.fetch_snapshots.fetch_market_snapshots")
def fetch_market_snapshots() -> dict:
    """Fetch market snapshots from brapi for all active primary securities.

    After fetching, chains compute_market_metrics to recompute EV/earnings yield.
    """
    if not ENABLE_BRAPI:
        return {"skipped": True, "reason": "ENABLE_BRAPI=false"}

    session = SessionLocal()
    try:
        adapter = BrapiProviderAdapter()

        securities = session.execute(
            select(Security).where(
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).scalars().all()

        loop = asyncio.new_event_loop()
        snapshots_created = 0
        try:
            for sec in securities:
                try:
                    quote = loop.run_until_complete(adapter.get_quote(sec.ticker))
                except Exception:
                    logger.warning("brapi quote failed for %s", sec.ticker, exc_info=True)
                    continue

                if quote:
                    snapshot = MarketSnapshot(
                        id=uuid.uuid4(),
                        security_id=sec.id,
                        source=SourceProvider.brapi,
                        price=quote.get("regularMarketPrice"),
                        market_cap=quote.get("marketCap"),
                        volume=quote.get("regularMarketVolume"),
                        raw_json=quote,
                    )
                    session.add(snapshot)
                    snapshots_created += 1

                time.sleep(0.2)  # rate limiting brapi free tier
        finally:
            loop.close()

        session.commit()
        logger.info("created %d market snapshots", snapshots_created)

        # Chain: recompute market-dependent metrics
        compute_market_metrics.delay()

        return {"snapshots_created": snapshots_created}

    except Exception:
        session.rollback()
        logger.exception("fetch_market_snapshots failed")
        raise
    finally:
        session.close()


@celery_app.task(name="q3_fundamentals_engine.tasks.fetch_snapshots.compute_market_metrics")
def compute_market_metrics() -> dict:
    """Recompute market-dependent metrics (EV, earnings yield) using latest snapshots."""
    session = SessionLocal()
    try:
        engine = MetricsEngine(session)
        metrics_computed = 0

        # For each issuer with a primary security that has a fresh snapshot,
        # get the latest market_cap and recompute market-dependent metrics.
        # Stale snapshots (> SNAPSHOT_STALENESS) are skipped.
        staleness_cutoff = datetime.now(timezone.utc) - SNAPSHOT_STALENESS
        rows = session.execute(
            select(
                Issuer.id.label("issuer_id"),
                MarketSnapshot.market_cap,
            )
            .join(Security, Security.issuer_id == Issuer.id)
            .join(MarketSnapshot, MarketSnapshot.security_id == Security.id)
            .where(
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
                MarketSnapshot.market_cap.isnot(None),
                MarketSnapshot.fetched_at >= staleness_cutoff,
            )
            .order_by(MarketSnapshot.fetched_at.desc())
            .distinct(Issuer.id)
        ).all()

        for issuer_id, market_cap in rows:
            # Get latest completed filing reference date for this issuer
            latest_filing = session.execute(
                select(Filing.reference_date)
                .where(
                    Filing.issuer_id == issuer_id,
                    Filing.status == FilingStatus.completed,
                )
                .order_by(Filing.reference_date.desc())
                .limit(1)
            ).scalar_one_or_none()

            if latest_filing is None:
                continue

            metrics = engine.compute_for_issuer(
                issuer_id,
                latest_filing,
                market_cap=float(market_cap),
                only_market_dependent=True,
            )
            metrics_computed += len(metrics)

        session.commit()
        logger.info("computed %d market-dependent metrics", metrics_computed)

        step_refresh_compat_view(session)

        return {"metrics_computed": metrics_computed}

    except Exception:
        session.rollback()
        logger.exception("compute_market_metrics failed")
        raise
    finally:
        session.close()
