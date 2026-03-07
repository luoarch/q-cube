"""Test fixtures — in-memory SQLite session for unit tests."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB

from q3_shared_models.base import Base
from q3_shared_models.entities import (
    ComputedMetric,
    Filing,
    FilingStatus,
    FilingType,
    Issuer,
    MarketSnapshot,
    PeriodType,
    Security,
    SourceProvider,
    StatementLine,
    StatementType,
    ScopeType,
)


# Map PostgreSQL JSONB to plain JSON for SQLite compatibility
JSONB._default_dialect_inspections = set()  # type: ignore[attr-defined]


@pytest.fixture
def session():
    """Create an in-memory SQLite session with all tables."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    # Compile JSONB as JSON for SQLite
    from sqlalchemy.ext.compiler import compiles
    compiles(JSONB, "sqlite")(lambda element, compiler, **kw: "JSON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess
    sess.close()


def make_issuer(
    session: Session,
    *,
    cvm_code: str = "12345",
    legal_name: str = "Test Corp",
    sector: str | None = "Tecnologia",
    cnpj: str | None = None,
) -> Issuer:
    issuer = Issuer(
        id=uuid.uuid4(),
        cvm_code=cvm_code,
        legal_name=legal_name,
        sector=sector,
        cnpj=cnpj or f"{uuid.uuid4().hex[:14]}",
    )
    session.add(issuer)
    session.flush()
    return issuer


def make_security(
    session: Session,
    issuer: Issuer,
    *,
    ticker: str = "TEST3",
    is_primary: bool = True,
    valid_from: date = date(2020, 1, 1),
    valid_to: date | None = None,
) -> Security:
    sec = Security(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        ticker=ticker,
        is_primary=is_primary,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    session.add(sec)
    session.flush()
    return sec


def make_filing(
    session: Session,
    issuer: Issuer,
    *,
    reference_date: date = date(2024, 12, 31),
    available_at: datetime | None = None,
    is_restatement: bool = False,
    status: FilingStatus = FilingStatus.completed,
) -> Filing:
    if available_at is None:
        available_at = datetime(2025, 3, 1, tzinfo=timezone.utc)
    filing = Filing(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        source=SourceProvider.cvm,
        filing_type=FilingType.DFP,
        reference_date=reference_date,
        is_restatement=is_restatement,
        status=status,
        available_at=available_at,
    )
    session.add(filing)
    session.flush()
    return filing


def make_computed_metric(
    session: Session,
    issuer: Issuer,
    *,
    metric_code: str,
    value: float,
    reference_date: date = date(2024, 12, 31),
) -> ComputedMetric:
    metric = ComputedMetric(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        metric_code=metric_code,
        period_type=PeriodType.annual,
        reference_date=reference_date,
        value=value,
        inputs_snapshot_json={},
        source_filing_ids_json=[],
    )
    session.add(metric)
    session.flush()
    return metric


def make_statement_line(
    session: Session,
    filing: Filing,
    *,
    canonical_key: str,
    value: float,
) -> StatementLine:
    line = StatementLine(
        id=uuid.uuid4(),
        filing_id=filing.id,
        statement_type=StatementType.DRE,
        scope=ScopeType.con,
        period_type=PeriodType.annual,
        reference_date=filing.reference_date,
        canonical_key=canonical_key,
        as_reported_label=canonical_key,
        as_reported_code="0",
        normalized_value=value,
    )
    session.add(line)
    session.flush()
    return line


def make_market_snapshot(
    session: Session,
    security: Security,
    *,
    price: float = 25.0,
    market_cap: float = 1_000_000_000.0,
    volume: float = 5_000_000.0,
    fetched_at: datetime | None = None,
) -> MarketSnapshot:
    if fetched_at is None:
        fetched_at = datetime(2025, 3, 1, tzinfo=timezone.utc)
    snap = MarketSnapshot(
        id=uuid.uuid4(),
        security_id=security.id,
        source=SourceProvider.brapi,
        price=price,
        market_cap=market_cap,
        volume=volume,
        fetched_at=fetched_at,
    )
    session.add(snap)
    session.flush()
    return snap
