"""Retention tasks — archive old chat sessions, expire stale council opinions."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from q3_ai_assistant.celery_app import celery_app
from q3_ai_assistant.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Sessions older than 90 days are archived
SESSION_ARCHIVE_DAYS = 90

# Council opinions older than 180 days are marked expired
COUNCIL_EXPIRE_DAYS = 180


@celery_app.task(name="q3_ai_assistant.tasks.retention.archive_old_sessions")
def archive_old_sessions() -> dict:
    """Archive chat sessions older than SESSION_ARCHIVE_DAYS."""
    from q3_shared_models.entities import ChatSession

    cutoff = datetime.now(timezone.utc) - timedelta(days=SESSION_ARCHIVE_DAYS)

    with SessionLocal() as session:
        result = session.execute(
            update(ChatSession)
            .where(
                ChatSession.created_at < cutoff,
                ChatSession.archived_at.is_(None),
            )
            .values(archived_at=datetime.now(timezone.utc))
        )
        count = result.rowcount
        session.commit()

    if count:
        logger.info("Archived %d chat sessions older than %d days", count, SESSION_ARCHIVE_DAYS)
    return {"status": "ok", "archived": count}


@celery_app.task(name="q3_ai_assistant.tasks.retention.expire_old_council_sessions")
def expire_old_council_sessions() -> dict:
    """Mark council sessions older than COUNCIL_EXPIRE_DAYS as expired."""
    from q3_shared_models.entities import CouncilSession

    cutoff = datetime.now(timezone.utc) - timedelta(days=COUNCIL_EXPIRE_DAYS)

    with SessionLocal() as session:
        result = session.execute(
            update(CouncilSession)
            .where(
                CouncilSession.created_at < cutoff,
                CouncilSession.status != "expired",
            )
            .values(status="expired")
        )
        count = result.rowcount
        session.commit()

    if count:
        logger.info("Expired %d council sessions older than %d days", count, COUNCIL_EXPIRE_DAYS)
    return {"status": "ok", "expired": count}
