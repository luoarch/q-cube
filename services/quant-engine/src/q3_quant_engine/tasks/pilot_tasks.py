"""Pilot runtime tasks — daily snapshot + forward returns.

Beat-scheduled. Idempotent (proven by MF-RUNTIME-01A).
Consumes ranking from local HTTP endpoint (no direct import of ranking internals).
"""

from __future__ import annotations

import logging
from datetime import date

import httpx

from sqlalchemy import text as sa_text

from q3_quant_engine.celery_app import celery_app
from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.pilot.services import SnapshotService, ForwardReturnService

logger = logging.getLogger(__name__)

RANKING_URL = "http://localhost:8100/ranking"


@celery_app.task(name="q3_quant_engine.tasks.pilot_tasks.take_daily_snapshot")
def take_daily_snapshot() -> dict:
    """Fetch current ranking and persist as daily snapshot.

    Consumes the /ranking HTTP endpoint (public, tested).
    Persists both primaryRanking and secondaryRanking.
    """
    today = date.today()
    logger.info("Taking daily snapshot for %s", today)

    # Fetch ranking from local endpoint (decoupled — no import of ranking internals)
    try:
        resp = httpx.get(RANKING_URL, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to fetch ranking from %s", RANKING_URL)
        return {"status": "error", "reason": "ranking_fetch_failed"}

    data = resp.json()
    all_items = data.get("primaryRanking", []) + data.get("secondaryRanking", [])

    if not all_items:
        logger.warning("Ranking returned 0 items")
        return {"status": "skip", "reason": "empty_ranking"}

    svc = SnapshotService()
    with SessionLocal() as session:
        result = svc.create_daily_snapshot(session, today, all_items)
        session.commit()

    logger.info("Snapshot %s: inserted=%d updated=%d", today, result.inserted, result.updated)
    return {"status": "ok", "date": str(today), "inserted": result.inserted, "updated": result.updated}


@celery_app.task(name="q3_quant_engine.tasks.pilot_tasks.compute_all_forward_returns")
def compute_all_forward_returns() -> dict:
    """Compute forward returns for all past snapshots with missing returns.

    Tries all 3 horizons (1d, 5d, 21d) for each snapshot date.
    Skips when price not available (retries naturally next day).
    """
    from sqlalchemy import select, func
    from q3_shared_models.entities import RankingSnapshot, ForwardReturn

    logger.info("Computing forward returns for all pending snapshots")

    svc = ForwardReturnService()
    total_inserted = 0
    total_skipped = 0

    with SessionLocal() as session:
        # Get all snapshot dates
        snapshot_dates = session.execute(
            select(RankingSnapshot.snapshot_date).distinct().order_by(RankingSnapshot.snapshot_date)
        ).scalars().all()

        for snap_date in snapshot_dates:
            for horizon in ["1d", "5d", "21d"]:
                # Check if already fully computed for this date+horizon
                existing_count = session.execute(
                    select(func.count()).select_from(ForwardReturn).where(
                        ForwardReturn.snapshot_date == snap_date,
                        ForwardReturn.horizon == horizon,
                    )
                ).scalar() or 0

                snap_count = session.execute(
                    select(func.count()).select_from(RankingSnapshot).where(
                        RankingSnapshot.snapshot_date == snap_date,
                    )
                ).scalar() or 0

                if existing_count >= snap_count and snap_count > 0:
                    continue  # Already fully computed

                result = svc.compute_forward_returns(session, snap_date, horizon)
                total_inserted += result.inserted
                total_skipped += result.skipped

        session.commit()

    logger.info("Forward returns: inserted=%d skipped=%d", total_inserted, total_skipped)
    return {"status": "ok", "inserted": total_inserted, "skipped": total_skipped}


@celery_app.task(name="q3_quant_engine.tasks.pilot_tasks.refresh_compat_view")
def refresh_compat_view() -> dict:
    """Refresh the materialized compat view. ~0.2s typical."""
    logger.info("Refreshing v_financial_statements_compat")
    with SessionLocal() as session:
        session.execute(sa_text("REFRESH MATERIALIZED VIEW v_financial_statements_compat"))
        session.commit()
    logger.info("Compat view refreshed")
    return {"status": "ok"}
