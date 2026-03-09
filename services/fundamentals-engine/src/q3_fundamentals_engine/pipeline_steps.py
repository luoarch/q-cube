"""Shared pipeline step functions used by both facade and import_batch task."""

from __future__ import annotations

import logging
import uuid

from q3_shared_models.entities import (
    Filing,
    FilingStatus,
    StatementLine,
)
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from q3_fundamentals_engine.issuers.registry import IssuerRegistry
from q3_fundamentals_engine.issuers.security_manager import SecurityManager
from q3_fundamentals_engine.issuers.ticker_resolver import build_ticker_resolver_chain
from q3_fundamentals_engine.metrics.engine import MetricsEngine
from q3_fundamentals_engine.normalization.pipeline import NormalizationPipeline
from q3_fundamentals_engine.parsers.factory import FilingParserFactory
from q3_fundamentals_engine.parsers.fca import FcaParser
from q3_fundamentals_engine.parsers.models import ParsedRow
from q3_fundamentals_engine.providers.base import DownloadedFile
from q3_fundamentals_engine.providers.cvm.adapter import CvmProviderAdapter
from q3_fundamentals_engine.providers.cvm.downloader import download_cadastro as _download_cadastro
from q3_fundamentals_engine.restatements.detector import RestatementDetector
from q3_fundamentals_engine.restatements.invalidator import MetricsInvalidator
from q3_fundamentals_engine.validation.accounting import AccountingValidator
from q3_fundamentals_engine.validation.anomaly import AnomalyDetector

logger = logging.getLogger(__name__)

_accounting_validator = AccountingValidator()
_anomaly_detector = AnomalyDetector()


def step_parse(downloaded_files: list[DownloadedFile], doc_types: list[str]) -> list[ParsedRow]:
    """Parse downloaded files, filtering by doc_type in filename to avoid empty parses."""
    all_parsed: list[ParsedRow] = []
    for doc_type in doc_types:
        try:
            parser = FilingParserFactory.create(doc_type)
        except ValueError:
            logger.warning("no parser for doc_type=%s, skipping parse", doc_type)
            continue
        matching = [f for f in downloaded_files if doc_type.lower() in f.filename.lower()]
        for dl_file in matching:
            parsed = parser.run(dl_file.content)
            all_parsed.extend(parsed)
            logger.info("parsed %d rows from %s", len(parsed), dl_file.filename)
    logger.info("total parsed rows: %d", len(all_parsed))
    return all_parsed


def step_normalize(session: Session, parsed_rows: list[ParsedRow]) -> list[uuid.UUID]:
    """Normalize parsed rows into filings + statement_lines."""
    pipeline = NormalizationPipeline(session)
    filing_ids = pipeline.normalize(parsed_rows)
    logger.info("normalized %d filings", len(filing_ids))
    return filing_ids


def step_detect_restatements(session: Session, filing_ids: list[uuid.UUID]) -> dict[str, int]:
    """Detect restatements for newly created filings and invalidate stale metrics."""
    detector = RestatementDetector(session)
    invalidator = MetricsInvalidator(session)
    restatements_detected = 0
    metrics_invalidated = 0

    for fid in filing_ids:
        filing = session.get(Filing, fid)
        if filing is None or filing.version_number <= 1:
            continue
        evt = detector.detect(filing.issuer_id, filing.reference_date, filing.version_number)
        if evt is not None:
            restatements_detected += 1
            codes = invalidator.invalidate(evt)
            metrics_invalidated += len(codes)

    logger.info(
        "restatement detection: %d detected, %d metrics invalidated",
        restatements_detected, metrics_invalidated,
    )
    return {"restatements_detected": restatements_detected, "metrics_invalidated": metrics_invalidated}


def step_validate_filings(session: Session, filing_ids: list[uuid.UUID]) -> dict[str, int]:
    """Run accounting + anomaly validation on completed filings."""
    filings_validated = 0
    validation_failures = 0

    for fid in filing_ids:
        filing = session.get(Filing, fid)
        if filing is None or filing.status != FilingStatus.completed:
            continue

        lines = session.execute(
            select(StatementLine)
            .where(StatementLine.filing_id == fid, StatementLine.canonical_key.isnot(None))
        ).scalars().all()

        values: dict[str, float | None] = {}
        for line in lines:
            if line.canonical_key and line.canonical_key not in values:
                values[line.canonical_key] = float(line.normalized_value) if line.normalized_value is not None else None

        if "equity" in values and "total_equity" not in values:
            values["total_equity"] = values["equity"]

        accounting = _accounting_validator.validate(values)
        anomalies = _anomaly_detector.detect(filing.issuer_id, values, {})
        result = {"accounting_checks": accounting, "anomalies": anomalies}

        session.execute(
            update(Filing).where(Filing.id == fid).values(validation_result=result)
        )
        filings_validated += 1
        if any(c.get("passed") is False for c in accounting.values()):
            validation_failures += 1

    logger.info("validated %d filings (%d with failures)", filings_validated, validation_failures)
    return {"filings_validated": filings_validated, "validation_failures": validation_failures}


async def step_download_fca(adapter: CvmProviderAdapter, year: int) -> dict[str, list[str]]:
    """Download FCA for ticker mapping (best effort)."""
    fca_mapping: dict[str, list[str]] = {}
    try:
        fca_files = await adapter.download_filings(year, ["FCA"])
        if fca_files:
            fca_parser = FcaParser()
            fca_infos = fca_parser.run(fca_files[0].content)
            for info in fca_infos:
                if info.cvm_code and info.tickers:
                    fca_mapping[info.cvm_code] = info.tickers
            logger.info("FCA ticker mapping: %d entries", len(fca_mapping))
    except Exception:
        logger.warning("FCA download/parse failed for year=%d", year, exc_info=True)
    return fca_mapping


async def step_download_cadastro() -> list[dict[str, str]]:
    """Download cadastro data (best effort)."""
    try:
        data = await _download_cadastro()
        logger.info("cadastro: %d entries", len(data))
        return data
    except Exception:
        logger.warning("cadastro download failed", exc_info=True)
        return []


def step_build_sector_map(cadastro_data: list[dict[str, str]]) -> dict[str, dict[str, str | None]]:
    """Build CD_CVM -> {sector, subsector, segment} map from cadastro."""
    sectors: dict[str, dict[str, str | None]] = {}
    for entry in cadastro_data:
        code = entry.get("CD_CVM", "").strip()
        if code:
            sectors[code] = {
                "sector": entry.get("SETOR_ATIV", "").strip() or None,
                "subsector": entry.get("SUBSETOR_ATIV", "").strip() or None,
                "segment": entry.get("SEGMENTO_ATIV", "").strip() or None,
            }
    return sectors


def step_resolve_issuers(
    session: Session,
    parsed_rows: list[ParsedRow],
    fca_mapping: dict[str, list[str]],
    cadastro_data: list[dict[str, str]],
) -> dict[str, int]:
    """Resolve issuers, create securities from FCA/cadastro data."""
    cadastro_sectors = step_build_sector_map(cadastro_data)
    registry = IssuerRegistry(session)
    sec_manager = SecurityManager(session)
    resolver = build_ticker_resolver_chain(fca_mapping, cadastro_data)

    issuers_upserted = 0
    securities_created = 0
    seen_cvm_codes: set[str] = set()

    for row in parsed_rows:
        if row.cd_cvm in seen_cvm_codes:
            continue
        seen_cvm_codes.add(row.cd_cvm)

        cnpj_digits = "".join(c for c in row.cnpj if c.isdigit())
        sector_info = cadastro_sectors.get(row.cd_cvm, {})
        issuer = registry.upsert_issuer(
            cvm_code=row.cd_cvm,
            legal_name=row.company_name,
            cnpj=cnpj_digits,
            sector=sector_info.get("sector"),
            subsector=sector_info.get("subsector"),
            segment=sector_info.get("segment"),
        )
        issuers_upserted += 1

        tickers = resolver.resolve(cnpj_digits, row.cd_cvm)
        if tickers:
            securities = sec_manager.upsert_securities(issuer.id, tickers)
            securities_created += len(securities)

    logger.info("issuers upserted: %d, securities: %d", issuers_upserted, securities_created)
    return {"issuers_upserted": issuers_upserted, "securities_created": securities_created}


def step_compute_filing_metrics(session: Session, filing_ids: list[uuid.UUID]) -> int:
    """Compute derived metrics for completed filings."""
    engine = MetricsEngine(session)
    metrics_computed = 0

    completed = session.execute(
        select(Filing.issuer_id, Filing.reference_date)
        .where(Filing.id.in_(filing_ids), Filing.status == FilingStatus.completed)
        .distinct()
    ).all()

    for issuer_id, ref_date in completed:
        metrics = engine.compute_for_issuer(issuer_id, ref_date)
        metrics_computed += len(metrics)

    logger.info("metrics computed: %d", metrics_computed)
    return metrics_computed


def step_smoke_tests(session: Session) -> bool:
    """Run post-ingestion smoke tests. Returns True if all passed."""
    from q3_fundamentals_engine.validation.smoke_tests import run_smoke_tests

    results = run_smoke_tests(session)
    all_passed = all(r.passed for r in results)
    passed_count = sum(1 for r in results if r.passed)

    if all_passed:
        logger.info("All %d smoke tests passed", len(results))
    else:
        failed = [r for r in results if not r.passed]
        logger.error(
            "SMOKE TESTS FAILED: %d/%d passed. Failures: %s",
            passed_count, len(results),
            ", ".join(f.name for f in failed),
        )

    return all_passed


def step_refresh_compat_view(session: Session) -> None:
    """Refresh the v_financial_statements_compat materialized view."""
    try:
        session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY v_financial_statements_compat"))
        session.commit()
        logger.info("compat view refreshed (CONCURRENTLY)")
    except Exception:
        session.rollback()
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW v_financial_statements_compat"))
            session.commit()
            logger.info("compat view refreshed (non-concurrent fallback)")
        except Exception:
            logger.warning("compat view refresh failed — view may not exist yet", exc_info=True)
            session.rollback()
