"""Tests for restatement detection and invalidation against PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from q3_shared_models.entities import (
    ComputedMetric,
    Filing,
    FilingStatus,
    FilingType,
    Issuer,
    PeriodType,
    ScopeType,
    SourceProvider,
    StatementLine,
    StatementType,
)
from q3_fundamentals_engine.pipeline_steps import step_detect_restatements, step_validate_filings
from q3_fundamentals_engine.restatements.detector import RestatementDetector
from q3_fundamentals_engine.restatements.invalidator import MetricsInvalidator


def _make_issuer(session: Session) -> Issuer:
    issuer = Issuer(
        id=uuid.uuid4(),
        cvm_code=f"TEST{uuid.uuid4().hex[:6]}",
        legal_name="Test Corp S.A.",
        cnpj=f"{uuid.uuid4().int % 10**14:014d}",
    )
    session.add(issuer)
    session.flush()
    return issuer


def _make_filing(
    session: Session,
    issuer: Issuer,
    ref_date: date,
    version: int,
    status: FilingStatus = FilingStatus.completed,
) -> Filing:
    filing = Filing(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        source=SourceProvider.cvm,
        filing_type=FilingType.DFP,
        reference_date=ref_date,
        version_number=version,
        is_restatement=version > 1,
        status=status,
    )
    session.add(filing)
    session.flush()
    return filing


def _make_metric(
    session: Session,
    issuer: Issuer,
    ref_date: date,
    code: str,
    source_filing_ids: list[str],
) -> ComputedMetric:
    metric = ComputedMetric(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        metric_code=code,
        period_type=PeriodType.annual,
        reference_date=ref_date,
        value=0.15,
        inputs_snapshot_json={"test": True},
        source_filing_ids_json=source_filing_ids,
    )
    session.add(metric)
    session.flush()
    return metric


# ---- RestatementDetector tests ----


def test_detect_restatement_marks_original_superseded(session: Session) -> None:
    """When v2 arrives, v1 should be marked superseded and a RestatementEvent created."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)

    v1 = _make_filing(session, issuer, ref, version=1)
    _make_filing(session, issuer, ref, version=2)

    detector = RestatementDetector(session)
    evt = detector.detect(issuer.id, ref, new_version=2)

    assert evt is not None
    assert evt.original_filing_id == v1.id

    # v1 should now be superseded
    session.refresh(v1)
    assert v1.status == FilingStatus.superseded


def test_detect_no_prior_version_returns_none(session: Session) -> None:
    """First version for an issuer+date should return None (no restatement)."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)
    _make_filing(session, issuer, ref, version=1)

    detector = RestatementDetector(session)
    evt = detector.detect(issuer.id, ref, new_version=1)

    assert evt is None


# ---- MetricsInvalidator tests ----


def test_invalidator_deletes_affected_metrics(session: Session) -> None:
    """Metrics referencing the superseded filing should be deleted."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)

    v1 = _make_filing(session, issuer, ref, version=1)
    _make_filing(session, issuer, ref, version=2)

    m1 = _make_metric(session, issuer, ref, "roic", [str(v1.id)])
    m2 = _make_metric(session, issuer, ref, "ebit_margin", [str(v1.id)])
    # This metric references a different filing — should survive
    other_fid = str(uuid.uuid4())
    m3 = _make_metric(session, issuer, ref, "net_debt", [other_fid])

    detector = RestatementDetector(session)
    evt = detector.detect(issuer.id, ref, new_version=2)
    assert evt is not None

    invalidator = MetricsInvalidator(session)
    codes = invalidator.invalidate(evt)

    assert set(codes) == {"roic", "ebit_margin"}

    # m1, m2 should be deleted
    assert session.get(ComputedMetric, m1.id) is None
    assert session.get(ComputedMetric, m2.id) is None
    # m3 should still exist
    assert session.get(ComputedMetric, m3.id) is not None


def test_invalidator_updates_event_affected_codes(session: Session) -> None:
    """RestatementEvent.affected_metrics should list invalidated codes."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)

    v1 = _make_filing(session, issuer, ref, version=1)
    _make_filing(session, issuer, ref, version=2)

    _make_metric(session, issuer, ref, "roic", [str(v1.id)])

    detector = RestatementDetector(session)
    evt = detector.detect(issuer.id, ref, new_version=2)
    assert evt is not None

    invalidator = MetricsInvalidator(session)
    invalidator.invalidate(evt)

    session.refresh(evt)
    assert evt.affected_metrics == {"invalidated_codes": ["roic"]}


# ---- Pipeline integration: step_detect_restatements ----


def test_run_restatement_detection_finds_v2(session: Session) -> None:
    """step_detect_restatements should detect and invalidate when v2 filings exist."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)

    v1 = _make_filing(session, issuer, ref, version=1)
    v2 = _make_filing(session, issuer, ref, version=2)
    _make_metric(session, issuer, ref, "roic", [str(v1.id)])

    stats = step_detect_restatements(session, [v1.id, v2.id])

    assert stats["restatements_detected"] == 1
    assert stats["metrics_invalidated"] == 1


def test_run_restatement_detection_skips_v1_only(session: Session) -> None:
    """step_detect_restatements should do nothing when only v1 filings exist."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)

    v1 = _make_filing(session, issuer, ref, version=1)

    stats = step_detect_restatements(session, [v1.id])

    assert stats["restatements_detected"] == 0
    assert stats["metrics_invalidated"] == 0


# ---- Pipeline integration: step_validate_filings ----


def _make_statement_line(
    session: Session,
    filing_id: uuid.UUID,
    canonical_key: str,
    value: float,
) -> StatementLine:
    line = StatementLine(
        id=uuid.uuid4(),
        filing_id=filing_id,
        statement_type=StatementType.BPA,
        scope=ScopeType.con,
        period_type=PeriodType.annual,
        reference_date=date(2024, 12, 31),
        canonical_key=canonical_key,
        as_reported_label=canonical_key,
        as_reported_code="1.00",
        normalized_value=value,
    )
    session.add(line)
    session.flush()
    return line


def test_validate_filing_populates_validation_result(session: Session) -> None:
    """step_validate_filings should write accounting checks + anomalies to Filing.validation_result."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)
    filing = _make_filing(session, issuer, ref, version=1)

    # Add balanced balance sheet lines
    _make_statement_line(session, filing.id, "total_assets", 1000.0)
    _make_statement_line(session, filing.id, "total_liabilities", 600.0)
    _make_statement_line(session, filing.id, "equity", 400.0)

    stats = step_validate_filings(session, [filing.id])

    assert stats["filings_validated"] == 1
    assert stats["validation_failures"] == 0

    # Verify persisted
    session.refresh(filing)
    assert filing.validation_result is not None
    assert filing.validation_result["accounting_checks"]["assets_eq_liabilities_plus_equity"]["passed"] is True


def test_validate_filing_detects_imbalance(session: Session) -> None:
    """step_validate_filings should detect accounting imbalance."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)
    filing = _make_filing(session, issuer, ref, version=1)

    # Imbalanced: 1000 != 600 + 200
    _make_statement_line(session, filing.id, "total_assets", 1000.0)
    _make_statement_line(session, filing.id, "total_liabilities", 600.0)
    _make_statement_line(session, filing.id, "equity", 200.0)

    stats = step_validate_filings(session, [filing.id])

    assert stats["validation_failures"] == 1


def test_validate_filing_detects_negative_equity_anomaly(session: Session) -> None:
    """step_validate_filings should flag negative equity as anomaly."""
    issuer = _make_issuer(session)
    ref = date(2024, 12, 31)
    filing = _make_filing(session, issuer, ref, version=1)

    _make_statement_line(session, filing.id, "equity", -500.0)

    step_validate_filings(session, [filing.id])

    # Verify persisted
    session.refresh(filing)
    anomaly_rules = [a["rule"] for a in filing.validation_result["anomalies"]]
    assert "negative_equity" in anomaly_rules
