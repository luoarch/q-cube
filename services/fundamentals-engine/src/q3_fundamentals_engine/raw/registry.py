"""Raw source batch and file registration — tracks downloaded files with dedup by SHA-256."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from q3_shared_models.entities import (
    BatchStatus,
    FilingType,
    RawSourceBatch,
    RawSourceFile,
    SourceProvider,
)
from sqlalchemy.orm import Session

from q3_fundamentals_engine.providers.base import DownloadedFile

logger = logging.getLogger(__name__)


def create_batch(
    session: Session,
    source: SourceProvider,
    year: int,
    doc_type: str,
) -> RawSourceBatch:
    """Create a new pending raw source batch."""
    batch = RawSourceBatch(
        id=uuid.uuid4(),
        source=source,
        year=year,
        document_type=FilingType(doc_type),
        status=BatchStatus.pending,
        started_at=datetime.now(timezone.utc),
    )
    session.add(batch)
    session.flush()
    logger.info("created batch %s source=%s year=%d doc_type=%s", batch.id, source.value, year, doc_type)
    return batch


def register_file(
    session: Session,
    batch_id: uuid.UUID,
    downloaded_file: DownloadedFile,
) -> RawSourceFile | None:
    """Register a downloaded file, skipping if the SHA-256 hash already exists.

    Returns the RawSourceFile if created, or None if a duplicate was found.
    """
    existing = (
        session.query(RawSourceFile)
        .filter(RawSourceFile.sha256_hash == downloaded_file.sha256_hash)
        .first()
    )
    if existing is not None:
        logger.info(
            "skipping duplicate file %s (sha256=%s already in file %s)",
            downloaded_file.filename,
            downloaded_file.sha256_hash,
            existing.id,
        )
        return None

    raw_file = RawSourceFile(
        id=uuid.uuid4(),
        batch_id=batch_id,
        filename=downloaded_file.filename,
        url=downloaded_file.url,
        sha256_hash=downloaded_file.sha256_hash,
        size_bytes=downloaded_file.size_bytes,
    )
    session.add(raw_file)
    session.flush()
    logger.info(
        "registered file %s (sha256=%s, %d bytes) in batch %s",
        raw_file.filename,
        raw_file.sha256_hash,
        raw_file.size_bytes,
        batch_id,
    )
    return raw_file


def complete_batch(session: Session, batch_id: uuid.UUID) -> None:
    """Mark a batch as completed."""
    batch = session.get(RawSourceBatch, batch_id)
    if batch is None:
        logger.error("batch %s not found", batch_id)
        return
    batch.status = BatchStatus.completed
    batch.completed_at = datetime.now(timezone.utc)
    session.flush()
    logger.info("batch %s marked as completed", batch_id)


def fail_batch(session: Session, batch_id: uuid.UUID, error: str) -> None:
    """Mark a batch as failed with an error message."""
    batch = session.get(RawSourceBatch, batch_id)
    if batch is None:
        logger.error("batch %s not found", batch_id)
        return
    batch.status = BatchStatus.failed
    batch.completed_at = datetime.now(timezone.utc)
    session.flush()
    logger.warning("batch %s marked as failed: %s", batch_id, error)
