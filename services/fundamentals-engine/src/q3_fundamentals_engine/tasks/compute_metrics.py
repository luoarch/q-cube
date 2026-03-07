from __future__ import annotations

import logging
import uuid

from q3_shared_models.entities import Filing, FilingStatus
from sqlalchemy import select, text

from q3_fundamentals_engine.celery_app import celery_app
from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.metrics.engine import MetricsEngine

logger = logging.getLogger(__name__)


@celery_app.task(name="q3_fundamentals_engine.tasks.compute_metrics.compute_metrics_for_issuer")
def compute_metrics_for_issuer(issuer_id: str) -> dict:
    """Compute all derived metrics for an issuer across all available reference dates.

    Args:
        issuer_id: UUID string of the issuer.

    Returns:
        Summary dict with counts per reference date.
    """
    uid = uuid.UUID(issuer_id)
    logger.info("Starting metric computation for issuer=%s", issuer_id)

    with SessionLocal() as session:
        # Find all distinct reference dates with completed filings for this issuer.
        stmt = (
            select(Filing.reference_date)
            .where(
                Filing.issuer_id == uid,
                Filing.status == FilingStatus.completed,
            )
            .distinct()
            .order_by(Filing.reference_date)
        )
        ref_dates = [row[0] for row in session.execute(stmt).all()]

        engine = MetricsEngine(session)
        summary: dict[str, int] = {}

        for ref_date in ref_dates:
            metrics = engine.compute_for_issuer(uid, ref_date)
            summary[str(ref_date)] = len(metrics)

        session.commit()

    logger.info("Completed metric computation for issuer=%s: %s", issuer_id, summary)
    return {"issuer_id": issuer_id, "dates_processed": len(ref_dates), "metrics_per_date": summary}


@celery_app.task(name="q3_fundamentals_engine.tasks.compute_metrics.refresh_compat_view")
def refresh_compat_view() -> dict:
    """Refresh the v_financial_statements_compat materialized view.

    Tries CONCURRENTLY first (requires unique index), falls back to blocking refresh.
    """
    with SessionLocal() as session:
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY v_financial_statements_compat"))
            session.commit()
            logger.info("compat view refreshed (CONCURRENTLY)")
            return {"status": "refreshed", "mode": "concurrent"}
        except Exception:
            session.rollback()
            session.execute(text("REFRESH MATERIALIZED VIEW v_financial_statements_compat"))
            session.commit()
            logger.info("compat view refreshed (non-concurrent fallback)")
            return {"status": "refreshed", "mode": "blocking"}
