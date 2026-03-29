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


@celery_app.task(name="q3_quant_engine.tasks.pilot_tasks.fetch_b3_daily")
def fetch_b3_daily() -> dict:
    """Fetch today's B3 COTAHIST and persist as market_snapshots.

    Derives market_cap = close × CVM net_shares.
    Runs at 20:00 BRT (after B3 publishes COTAHIST ~19:00).
    """
    import uuid as _uuid
    from datetime import datetime, timezone
    from sqlalchemy import select
    from q3_shared_models.entities import MarketSnapshot, Security, SourceProvider

    today = date.today()
    logger.info("Fetching B3 daily COTAHIST for %s", today)

    try:
        # Import here to avoid circular deps
        import sys, os
        fe_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'fundamentals-engine', 'src')
        if fe_path not in sys.path:
            sys.path.insert(0, os.path.abspath(fe_path))

        from q3_fundamentals_engine.providers.b3.adapter import parse_daily
        from q3_fundamentals_engine.shares.lookup import find_cvm_shares
    except ImportError:
        logger.error("Cannot import fundamentals-engine modules")
        return {"status": "error", "reason": "import_failed"}

    records = parse_daily(today)
    if records is None:
        logger.info("B3 COTAHIST not available yet for %s", today)
        return {"status": "skip", "reason": "not_available_yet"}

    with SessionLocal() as session:
        # Build ticker → security map
        sec_rows = session.execute(
            select(Security.ticker, Security.id, Security.issuer_id).where(
                Security.is_primary.is_(True), Security.valid_to.is_(None),
            )
        ).all()
        ticker_map = {r[0]: (r[1], r[2]) for r in sec_rows}

        inserted = 0
        fetched_at = datetime(today.year, today.month, today.day, 23, 59, 0, tzinfo=timezone.utc)

        for rec in records:
            sec_info = ticker_map.get(rec.ticker)
            if sec_info is None:
                continue
            sec_id, issuer_id = sec_info

            # Derive mcap
            from q3_fundamentals_engine.shares.lookup import find_cvm_shares as _find_cvm
            cvm = _find_cvm(session, issuer_id, date(today.year, ((today.month - 1) // 3) * 3 + 3, {3: 31, 6: 30, 9: 30, 12: 31}.get(((today.month - 1) // 3) * 3 + 3, 31)))
            net_shares = float(cvm.net_shares) if cvm else None
            derived_mcap = rec.close * net_shares if net_shares else None

            session.add(MarketSnapshot(
                id=_uuid.uuid4(), security_id=sec_id, source=SourceProvider.b3,
                price=rec.close, market_cap=derived_mcap, volume=rec.volume,
                currency="BRL", fetched_at=fetched_at,
                raw_json={"source": "b3_cotahist", "close": rec.close, "date": str(rec.date)},
            ))
            inserted += 1

        session.commit()

    logger.info("B3 daily: %d snapshots inserted for %s", inserted, today)
    return {"status": "ok", "date": str(today), "inserted": inserted}


@celery_app.task(name="q3_quant_engine.tasks.pilot_tasks.refresh_compat_view")
def refresh_compat_view() -> dict:
    """Refresh the materialized compat view. ~0.2s typical."""
    logger.info("Refreshing v_financial_statements_compat")
    with SessionLocal() as session:
        session.execute(sa_text("REFRESH MATERIALIZED VIEW v_financial_statements_compat"))
        session.commit()
    logger.info("Compat view refreshed")
    return {"status": "ok"}
