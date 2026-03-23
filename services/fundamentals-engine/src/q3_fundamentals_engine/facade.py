"""Fundamentals Ingestion Facade — high-level orchestration."""

from __future__ import annotations

import logging
import uuid

from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.metrics.engine import MetricsEngine
from q3_fundamentals_engine.pipeline_steps import (
    step_compute_filing_metrics,
    step_detect_restatements,
    step_download_cadastro,
    step_download_fca,
    step_normalize,
    step_parse,
    step_resolve_issuers,
    step_validate_filings,
)
from q3_fundamentals_engine.providers.cvm.adapter import CvmProviderAdapter
from q3_fundamentals_engine.providers.source_policy import SourceSelectionPolicy
from q3_fundamentals_engine.raw.registry import (
    complete_batch,
    create_batch,
    fail_batch,
    register_file,
)

logger = logging.getLogger(__name__)


class FundamentalsIngestionFacade:
    """High-level facade for fundamentals ingestion pipeline.

    Orchestrates: download -> parse -> normalize -> issuer mapping -> metrics.
    """

    def __init__(self) -> None:
        self._source_policy = SourceSelectionPolicy()

    async def import_batch(self, year: int, doc_types: list[str] | None = None) -> dict:
        """Full import pipeline for a year."""
        if doc_types is None:
            doc_types = ["DFP"]

        adapter = self._source_policy.get_statements_adapter()
        results: dict[str, int] = {
            "files_downloaded": 0,
            "files_skipped": 0,
            "filings_created": 0,
            "restatements_detected": 0,
            "metrics_invalidated": 0,
            "filings_validated": 0,
            "validation_failures": 0,
            "issuers_upserted": 0,
            "securities_created": 0,
            "metrics_computed": 0,
        }

        with SessionLocal() as session:
            for doc_type in doc_types:
                from q3_shared_models.entities import SourceProvider
                batch = create_batch(session, SourceProvider.cvm, year, doc_type)
                session.commit()

                try:
                    downloaded = await adapter.download_filings(year, [doc_type])

                    for dl_file in downloaded:
                        raw_file = register_file(session, batch.id, dl_file)
                        if raw_file is None:
                            results["files_skipped"] += 1
                        else:
                            results["files_downloaded"] += 1
                    session.commit()

                    # Parse
                    all_parsed = step_parse(downloaded, [doc_type])

                    # Download FCA + cadastro for issuer resolution
                    fca_mapping: dict[str, list[str]] = {}
                    if isinstance(adapter, CvmProviderAdapter):
                        fca_mapping = await step_download_fca(adapter, year)
                    cadastro_data = await step_download_cadastro()

                    # Normalize
                    filing_ids = step_normalize(session, all_parsed)
                    results["filings_created"] += len(filing_ids)
                    session.commit()

                    # Restatement detection
                    restatement_stats = step_detect_restatements(session, filing_ids)
                    results["restatements_detected"] += restatement_stats["restatements_detected"]
                    results["metrics_invalidated"] += restatement_stats["metrics_invalidated"]
                    session.commit()

                    # Validation
                    validation_stats = step_validate_filings(session, filing_ids)
                    results["filings_validated"] += validation_stats["filings_validated"]
                    results["validation_failures"] += validation_stats["validation_failures"]
                    session.commit()

                    # Issuer/ticker resolution
                    issuer_stats = step_resolve_issuers(session, all_parsed, fca_mapping, cadastro_data)
                    results["issuers_upserted"] += issuer_stats["issuers_upserted"]
                    results["securities_created"] += issuer_stats["securities_created"]
                    session.commit()

                    # Compute metrics
                    results["metrics_computed"] += step_compute_filing_metrics(session, filing_ids)
                    session.commit()

                    complete_batch(session, batch.id)
                    session.commit()

                except Exception:
                    logger.exception("batch import failed year=%d doc_type=%s", year, doc_type)
                    fail_batch(session, batch.id, "import failed")
                    session.commit()
                    raise

        return results

    def reprocess_issuer(self, issuer_id: uuid.UUID) -> dict:
        """Reprocess all filings for an issuer — re-normalize and recompute metrics."""
        with SessionLocal() as session:
            from q3_shared_models.entities import Filing
            from sqlalchemy import select

            filings = session.execute(
                select(Filing).where(Filing.issuer_id == issuer_id)
            ).scalars().all()

            engine = MetricsEngine(session)
            recomputed = 0
            for filing in filings:
                metrics = engine.compute_for_issuer(issuer_id, filing.reference_date)
                recomputed += len(metrics)

            session.commit()

        return {"issuer_id": str(issuer_id), "metrics_recomputed": recomputed}

    def recalculate_metrics(self, issuer_id: uuid.UUID) -> dict:
        """Recalculate all metrics for an issuer without re-parsing."""
        return self.reprocess_issuer(issuer_id)
