from __future__ import annotations

import logging
import uuid
from datetime import date

from q3_shared_models.entities import Filing, FilingStatus, RestatementEvent
from sqlalchemy import select, update
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RestatementDetector:
    """Detects when a new filing version supersedes an existing one."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def detect(
        self,
        issuer_id: uuid.UUID,
        reference_date: date,
        new_version: int,
    ) -> RestatementEvent | None:
        """Check if a filing with a lower version exists for this issuer + reference_date.

        If found:
        1. Marks the old filing as superseded.
        2. Creates and returns a RestatementEvent.

        Returns None if no prior version exists.
        """
        # Find the most recent completed filing with a lower version number.
        stmt = (
            select(Filing)
            .where(
                Filing.issuer_id == issuer_id,
                Filing.reference_date == reference_date,
                Filing.version_number < new_version,
                Filing.status == FilingStatus.completed,
            )
            .order_by(Filing.version_number.desc())
            .limit(1)
        )
        original_filing = self._session.scalar(stmt)

        if original_filing is None:
            return None

        logger.info(
            "Restatement detected: issuer=%s date=%s old_version=%d new_version=%d",
            issuer_id,
            reference_date,
            original_filing.version_number,
            new_version,
        )

        # Find the new filing (should already be inserted by the caller).
        new_filing_stmt = (
            select(Filing)
            .where(
                Filing.issuer_id == issuer_id,
                Filing.reference_date == reference_date,
                Filing.version_number == new_version,
            )
            .limit(1)
        )
        new_filing = self._session.scalar(new_filing_stmt)

        if new_filing is None:
            logger.error(
                "New filing v%d not found for issuer=%s date=%s",
                new_version,
                issuer_id,
                reference_date,
            )
            return None

        # Mark the original as superseded.
        self._session.execute(
            update(Filing)
            .where(Filing.id == original_filing.id)
            .values(status=FilingStatus.superseded)
        )

        # Link the new filing to the original.
        self._session.execute(
            update(Filing)
            .where(Filing.id == new_filing.id)
            .values(
                is_restatement=True,
                supersedes_filing_id=original_filing.id,
            )
        )

        event = RestatementEvent(
            id=uuid.uuid4(),
            original_filing_id=original_filing.id,
            new_filing_id=new_filing.id,
            affected_metrics={},  # Populated by MetricsInvalidator
        )
        self._session.add(event)
        self._session.flush()

        return event
