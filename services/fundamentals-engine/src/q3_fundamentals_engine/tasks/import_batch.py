"""Celery task for CVM batch import — download, parse, normalize, resolve, compute."""

from __future__ import annotations

import asyncio
import logging
import uuid

from q3_shared_models.entities import BatchStatus, RawSourceBatch

from q3_fundamentals_engine.celery_app import celery_app
from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.pipeline_steps import (
    step_compute_filing_metrics,
    step_detect_restatements,
    step_download_cadastro,
    step_download_fca,
    step_normalize,
    step_parse,
    step_refresh_compat_view,
    step_resolve_issuers,
    step_smoke_tests,
    step_validate_filings,
)
from q3_fundamentals_engine.providers.cvm.adapter import CvmProviderAdapter
from q3_fundamentals_engine.raw.registry import (
    complete_batch,
    fail_batch,
    register_file,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="q3_fundamentals_engine.tasks.import_batch.import_cvm_batch")
def import_cvm_batch(batch_id: str, year: int, doc_types: list[str]) -> dict:
    """Full CVM import pipeline for a single batch.

    Steps:
        1. Download ZIPs from CVM and register in raw layer
        2. Parse CSVs into ParsedRows
        3. Normalize into filings + statement_lines
        4. Resolve issuers + tickers (FCA + cadastro)
        5. Compute derived metrics
    """
    bid = uuid.UUID(batch_id)
    session = SessionLocal()
    try:
        batch = session.get(RawSourceBatch, bid)
        if batch is None:
            logger.error("batch %s not found, aborting", batch_id)
            return {"error": "batch not found"}

        batch.status = BatchStatus.downloading
        session.commit()

        # --- Step 1: Download ---
        adapter = CvmProviderAdapter()
        loop = asyncio.new_event_loop()
        try:
            downloaded_files = loop.run_until_complete(
                adapter.download_filings(year, doc_types)
            )
        finally:
            loop.close()

        registered_count = 0
        skipped_count = 0
        for dl_file in downloaded_files:
            result = register_file(session, bid, dl_file)
            if result is not None:
                registered_count += 1
            else:
                skipped_count += 1
        session.commit()

        # FCA-only batches stop here (no filings to parse)
        if doc_types == ["FCA"]:
            complete_batch(session, bid)
            session.commit()
            summary = {
                "batch_id": batch_id, "year": year, "doc_types": doc_types,
                "downloaded": len(downloaded_files),
                "registered": registered_count, "skipped": skipped_count,
            }
            logger.info("batch %s completed (FCA only): %s", batch_id, summary)
            return summary

        # --- Step 2: Parse ---
        all_parsed = step_parse(downloaded_files, doc_types)

        if not all_parsed:
            complete_batch(session, bid)
            session.commit()
            return {
                "batch_id": batch_id, "year": year, "doc_types": doc_types,
                "downloaded": len(downloaded_files),
                "registered": registered_count, "skipped": skipped_count,
                "parsed_rows": 0, "filings_created": 0,
            }

        # --- Step 3: Normalize ---
        filing_ids = step_normalize(session, all_parsed)
        session.commit()

        # --- Step 3a: Restatement detection ---
        restatement_stats = step_detect_restatements(session, filing_ids)
        session.commit()

        # --- Step 3b: Validation ---
        validation_stats = step_validate_filings(session, filing_ids)
        session.commit()

        # --- Step 4: Issuer/ticker resolution ---
        loop2 = asyncio.new_event_loop()
        try:
            fca_mapping = loop2.run_until_complete(step_download_fca(adapter, year))
            cadastro_data = loop2.run_until_complete(step_download_cadastro())
        finally:
            loop2.close()

        issuer_stats = step_resolve_issuers(session, all_parsed, fca_mapping, cadastro_data)
        session.commit()

        # --- Step 5: Compute metrics ---
        metrics_computed = step_compute_filing_metrics(session, filing_ids)
        session.commit()

        # --- Step 5b: Smoke tests ---
        smoke_ok = step_smoke_tests(session)
        if not smoke_ok:
            logger.error("Smoke tests failed for batch %s — compat view will still refresh but data may be suspect", batch_id)

        # Refresh materialized compat view
        step_refresh_compat_view(session)

        # Mark batch as completed
        complete_batch(session, bid)
        session.commit()

        summary = {
            "batch_id": batch_id,
            "year": year,
            "doc_types": doc_types,
            "downloaded": len(downloaded_files),
            "registered": registered_count,
            "skipped": skipped_count,
            "parsed_rows": len(all_parsed),
            "filings_created": len(filing_ids),
            **restatement_stats,
            **validation_stats,
            **issuer_stats,
            "metrics_computed": metrics_computed,
        }
        logger.info("batch %s completed: %s", batch_id, summary)
        return summary

    except Exception:
        session.rollback()
        logger.exception("batch %s failed", batch_id)
        try:
            fail_batch(session, bid, "task execution error")
            session.commit()
        except Exception:
            logger.exception("failed to mark batch %s as failed", batch_id)
            session.rollback()
        raise
    finally:
        session.close()
