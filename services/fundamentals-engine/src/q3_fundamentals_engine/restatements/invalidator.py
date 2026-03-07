from __future__ import annotations

import logging
import uuid

from q3_shared_models.entities import ComputedMetric, RestatementEvent
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from q3_fundamentals_engine.tasks.compute_metrics import compute_metrics_for_issuer

logger = logging.getLogger(__name__)


class MetricsInvalidator:
    """Invalidates computed metrics affected by a restatement and triggers recomputation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def invalidate(self, restatement_event: RestatementEvent) -> list[str]:
        """Find and delete computed_metrics that depended on the original filing.

        Returns list of invalidated metric_codes.
        """
        original_fid = str(restatement_event.original_filing_id)

        # Find all metrics whose source_filing_ids_json contains the original filing.
        # JSONB containment: the array contains the filing ID string.
        stmt = select(ComputedMetric).where(
            ComputedMetric.source_filing_ids_json.contains([original_fid]),
        )
        affected = self._session.scalars(stmt).all()

        if not affected:
            logger.info(
                "No computed metrics to invalidate for original_filing=%s",
                original_fid,
            )
            return []

        metric_codes = [m.metric_code for m in affected]
        metric_ids = [m.id for m in affected]

        logger.info(
            "Invalidating %d metrics for original_filing=%s: %s",
            len(metric_ids),
            original_fid,
            metric_codes,
        )

        self._session.execute(
            delete(ComputedMetric).where(ComputedMetric.id.in_(metric_ids))
        )

        # Update the restatement event with the affected metric codes.
        self._session.execute(
            update(RestatementEvent)
            .where(RestatementEvent.id == restatement_event.id)
            .values(affected_metrics={"invalidated_codes": metric_codes})
        )

        self._session.flush()
        return metric_codes

    def enqueue_recomputation(self, issuer_id: uuid.UUID) -> None:
        """Enqueue a Celery task to recompute all metrics for this issuer."""
        logger.info("Enqueuing metric recomputation for issuer=%s", issuer_id)
        compute_metrics_for_issuer.delay(str(issuer_id))
