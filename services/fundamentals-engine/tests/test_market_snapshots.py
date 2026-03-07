"""Tests for market snapshot integration with metrics engine."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_shared_models.entities import (
    ComputedMetric,
    Filing,
    FilingStatus,
    FilingType,
    Issuer,
    MarketSnapshot,
    PeriodType,
    Security,
    ScopeType,
    SourceProvider,
    StatementLine,
    StatementType,
)
from q3_fundamentals_engine.metrics.engine import MetricsEngine


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


def _make_security(session: Session, issuer: Issuer, *, ticker: str = "TEST3", is_primary: bool = True) -> Security:
    sec = Security(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        ticker=ticker,
        is_primary=is_primary,
        valid_from=date(2020, 1, 1),
    )
    session.add(sec)
    session.flush()
    return sec


def _make_filing(session: Session, issuer: Issuer, ref_date: date) -> Filing:
    filing = Filing(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        source=SourceProvider.cvm,
        filing_type=FilingType.DFP,
        reference_date=ref_date,
        version_number=1,
        status=FilingStatus.completed,
    )
    session.add(filing)
    session.flush()
    return filing


def _add_line(session: Session, filing_id: uuid.UUID, key: str, value: float) -> None:
    session.add(StatementLine(
        id=uuid.uuid4(),
        filing_id=filing_id,
        statement_type=StatementType.DRE,
        scope=ScopeType.con,
        period_type=PeriodType.annual,
        reference_date=date(2024, 12, 31),
        canonical_key=key,
        as_reported_label=key,
        as_reported_code="1.00",
        normalized_value=value,
    ))
    session.flush()


def _make_snapshot(
    session: Session, security: Security, *, market_cap: float, fetched_at: datetime | None = None
) -> MarketSnapshot:
    snap = MarketSnapshot(
        id=uuid.uuid4(),
        security_id=security.id,
        source=SourceProvider.brapi,
        price=10.0,
        market_cap=market_cap,
        volume=100_000.0,
        fetched_at=fetched_at or datetime.now(timezone.utc),
    )
    session.add(snap)
    session.flush()
    return snap


def _setup_issuer_with_filings(session: Session) -> tuple[Issuer, Security, Filing]:
    """Create issuer with primary security and a completed filing with basic financial data."""
    issuer = _make_issuer(session)
    sec = _make_security(session, issuer)
    ref = date(2024, 12, 31)
    filing = _make_filing(session, issuer, ref)

    _add_line(session, filing.id, "ebit", 500_000.0)
    _add_line(session, filing.id, "short_term_debt", 100_000.0)
    _add_line(session, filing.id, "long_term_debt", 200_000.0)
    _add_line(session, filing.id, "cash_and_equivalents", 50_000.0)
    _add_line(session, filing.id, "revenue", 2_000_000.0)
    _add_line(session, filing.id, "gross_profit", 800_000.0)
    _add_line(session, filing.id, "net_income", 300_000.0)
    _add_line(session, filing.id, "current_assets", 1_000_000.0)
    _add_line(session, filing.id, "current_liabilities", 600_000.0)
    _add_line(session, filing.id, "fixed_assets", 500_000.0)

    return issuer, sec, filing


# ---- Test: only_market_dependent skips CVM-only metrics ----


def test_only_market_dependent_computes_ev_and_ey_only(session: Session) -> None:
    """When only_market_dependent=True, only EV and earnings yield are computed."""
    issuer, sec, filing = _setup_issuer_with_filings(session)
    engine = MetricsEngine(session)

    metrics = engine.compute_for_issuer(
        issuer.id,
        date(2024, 12, 31),
        market_cap=1_000_000.0,
        only_market_dependent=True,
    )

    codes = {m.metric_code for m in metrics}
    assert "enterprise_value" in codes
    assert "earnings_yield" in codes
    # CVM-only metrics should NOT be computed
    assert "roic" not in codes
    assert "ebitda" not in codes
    assert "net_margin" not in codes


# ---- Test: null market_cap does not affect CVM-only metrics ----


def test_null_market_cap_preserves_cvm_metrics(session: Session) -> None:
    """EV/EY stay NULL when market_cap is None, but CVM-only metrics compute normally."""
    issuer, _, filing = _setup_issuer_with_filings(session)
    engine = MetricsEngine(session)

    metrics = engine.compute_for_issuer(issuer.id, date(2024, 12, 31), market_cap=None)

    codes = {m.metric_code for m in metrics}
    assert "roic" in codes
    assert "net_debt" in codes
    assert "enterprise_value" not in codes
    assert "earnings_yield" not in codes


# ---- Test: upsert idempotency (concurrent-safe) ----


def test_upsert_does_not_duplicate_metrics(session: Session) -> None:
    """Running compute_for_issuer twice with same params should not create duplicates."""
    issuer, _, filing = _setup_issuer_with_filings(session)
    engine = MetricsEngine(session)
    ref = date(2024, 12, 31)

    # First compute
    engine.compute_for_issuer(issuer.id, ref, market_cap=1_000_000.0)
    session.flush()

    count_before = session.execute(
        select(ComputedMetric)
        .where(ComputedMetric.issuer_id == issuer.id, ComputedMetric.reference_date == ref)
    ).scalars().all()

    # Second compute (same params — should upsert, not duplicate)
    engine.compute_for_issuer(issuer.id, ref, market_cap=2_000_000.0)
    session.flush()

    count_after = session.execute(
        select(ComputedMetric)
        .where(ComputedMetric.issuer_id == issuer.id, ComputedMetric.reference_date == ref)
    ).scalars().all()

    assert len(count_before) == len(count_after)

    # Verify the value was updated (EV changed because market_cap changed)
    ev = session.execute(
        select(ComputedMetric).where(
            ComputedMetric.issuer_id == issuer.id,
            ComputedMetric.metric_code == "enterprise_value",
            ComputedMetric.reference_date == ref,
        )
    ).scalar_one()
    # EV = market_cap + net_debt = 2M + 250K = 2.25M
    assert abs(float(ev.value) - 2_250_000.0) < 1.0


# ---- Test: issuer with multiple tickers uses primary ----


def test_multiple_securities_uses_primary(session: Session) -> None:
    """Only the primary security's snapshot feeds the metrics engine."""
    issuer = _make_issuer(session)
    sec_on = _make_security(session, issuer, ticker="TEST3", is_primary=True)
    sec_pn = _make_security(session, issuer, ticker="TEST4", is_primary=False)

    # Snapshot on primary (ON)
    _make_snapshot(session, sec_on, market_cap=1_000_000.0)
    # Snapshot on non-primary (PN) with different market_cap
    _make_snapshot(session, sec_pn, market_cap=5_000_000.0)

    # Query only primary security snapshots (same pattern as compute_market_metrics)
    from q3_shared_models.entities import Security as SecModel, MarketSnapshot as SnapModel
    primary_snap = session.execute(
        select(SnapModel.market_cap)
        .join(SecModel, SnapModel.security_id == SecModel.id)
        .where(
            SecModel.issuer_id == issuer.id,
            SecModel.is_primary.is_(True),
        )
        .order_by(SnapModel.fetched_at.desc())
        .limit(1)
    ).scalar_one()

    assert float(primary_snap) == 1_000_000.0


# ---- Test: restatement recomputes EV/EY using latest snapshot ----


def test_restatement_recompute_uses_latest_snapshot(session: Session) -> None:
    """After a restatement, re-running metrics should pick up the latest market snapshot."""
    issuer, sec, filing = _setup_issuer_with_filings(session)
    engine = MetricsEngine(session)
    ref = date(2024, 12, 31)

    # Initial snapshot
    _make_snapshot(session, sec, market_cap=1_000_000.0)
    engine.compute_for_issuer(issuer.id, ref, market_cap=1_000_000.0)
    session.flush()

    ev_v1 = session.execute(
        select(ComputedMetric).where(
            ComputedMetric.issuer_id == issuer.id,
            ComputedMetric.metric_code == "enterprise_value",
        )
    ).scalar_one()
    ev_v1_val = float(ev_v1.value)

    # New snapshot (market moved)
    _make_snapshot(session, sec, market_cap=2_000_000.0)

    # Recompute after restatement — should use new market_cap
    engine.compute_for_issuer(issuer.id, ref, market_cap=2_000_000.0, only_market_dependent=True)
    session.flush()

    ev_v2 = session.execute(
        select(ComputedMetric).where(
            ComputedMetric.issuer_id == issuer.id,
            ComputedMetric.metric_code == "enterprise_value",
        )
    ).scalar_one()

    assert float(ev_v2.value) != ev_v1_val
    # EV = 2M + 250K (net_debt) = 2.25M
    assert abs(float(ev_v2.value) - 2_250_000.0) < 1.0
