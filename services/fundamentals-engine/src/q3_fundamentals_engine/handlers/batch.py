"""FastAPI endpoints for raw source batch management."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from q3_shared_models.entities import RawSourceBatch, RawSourceFile, SourceProvider

from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.raw.registry import create_batch
from q3_fundamentals_engine.tasks.fetch_snapshots import fetch_market_snapshots
from q3_fundamentals_engine.tasks.import_batch import import_cvm_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("/cvm/{year}")
def create_cvm_batch(year: int, doc_types: list[str] | None = None) -> dict[str, Any]:
    """Create a CVM import batch and enqueue the Celery task.

    If doc_types is not provided, defaults to ["DFP", "ITR", "FCA"].
    """
    if doc_types is None:
        doc_types = ["DFP", "ITR", "FCA"]

    session = SessionLocal()
    try:
        # Create one batch per doc_type
        batch_ids: list[str] = []
        for doc_type in doc_types:
            batch = create_batch(session, SourceProvider.cvm, year, doc_type)
            batch_ids.append(str(batch.id))
            # Enqueue Celery task for this batch
            import_cvm_batch.delay(str(batch.id), year, [doc_type])
            logger.info("enqueued import_cvm_batch for batch %s (year=%d, doc_type=%s)", batch.id, year, doc_type)

        session.commit()
        return {
            "year": year,
            "doc_types": doc_types,
            "batch_ids": batch_ids,
            "status": "enqueued",
        }
    except Exception:
        session.rollback()
        logger.exception("failed to create CVM batch for year %d", year)
        raise HTTPException(status_code=500, detail="Failed to create batch")
    finally:
        session.close()


@router.post("/snapshots/refresh")
def refresh_snapshots() -> dict[str, str]:
    """Enqueue a market snapshot refresh using the configured provider (default: yahoo)."""
    fetch_market_snapshots.delay()
    return {"status": "enqueued"}


@router.get("/{batch_id}")
def get_batch(batch_id: str) -> dict[str, Any]:
    """Return batch status and associated files."""
    session = SessionLocal()
    try:
        bid = uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid batch ID")

    try:
        batch = session.get(RawSourceBatch, bid)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")

        files = (
            session.query(RawSourceFile)
            .filter(RawSourceFile.batch_id == bid)
            .all()
        )

        return {
            "id": str(batch.id),
            "source": batch.source.value,
            "year": batch.year,
            "document_type": batch.document_type.value,
            "status": batch.status.value,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "files": [
                {
                    "id": str(f.id),
                    "filename": f.filename,
                    "url": f.url,
                    "sha256_hash": f.sha256_hash,
                    "size_bytes": f.size_bytes,
                    "imported_at": f.imported_at.isoformat() if f.imported_at else None,
                }
                for f in files
            ],
        }
    finally:
        session.close()
