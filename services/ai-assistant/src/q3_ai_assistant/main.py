from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import FastAPI
from sqlalchemy import func, select

from q3_ai_assistant.config import settings
from q3_ai_assistant.db.session import SessionLocal
from q3_ai_assistant.models.entities import AIModule, AISuggestion, ReviewStatus

logger = logging.getLogger(__name__)

app = FastAPI(title="Q3 AI Assistant", version="0.1.0")


@app.get("/health")
def health() -> dict:
    result: dict = {"service": "ai-assistant", "status": "ok", "enabled": settings.enabled}

    try:
        with SessionLocal() as session:
            total = session.execute(
                select(func.count(AISuggestion.id))
            ).scalar() or 0

            pending = session.execute(
                select(func.count(AISuggestion.id)).where(
                    AISuggestion.review_status == ReviewStatus.pending
                )
            ).scalar() or 0

            result["total_suggestions"] = total
            result["pending_review"] = pending
    except Exception:
        logger.exception("health check DB query failed")
        result["db"] = "error"

    return result
