"""Point-in-time data integrity tests."""

from __future__ import annotations

from datetime import date, datetime, timezone

from q3_quant_engine.data.pit_data import (
    fetch_eligible_universe_pit,
    fetch_fundamentals_pit,
    fetch_market_pit,
)
from tests.conftest import (
    make_computed_metric,
    make_filing,
    make_issuer,
    make_market_snapshot,
    make_security,
    make_statement_line,
)


def test_pit_excludes_future_filings(session):
    """Filing with available_at > as_of_date must NOT appear."""
    issuer = make_issuer(session, cvm_code="001", cnpj="00000000000001")
    make_security(session, issuer, ticker="FUTR3")
    # Filing available in the future (March 2025)
    filing = make_filing(
        session, issuer,
        reference_date=date(2024, 12, 31),
        available_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
    )
    make_statement_line(session, filing, canonical_key="ebit", value=100_000)
    make_computed_metric(session, issuer, metric_code="enterprise_value", value=1_000_000)
    session.commit()

    # Query as of Feb 2025 — filing not yet available
    result = fetch_fundamentals_pit(session, date(2025, 2, 28))
    assert len(result) == 0


def test_pit_uses_latest_available_filing(session):
    """Among filings with available_at <= as_of_date, use the most recent."""
    issuer = make_issuer(session, cvm_code="002", cnpj="00000000000002")
    make_security(session, issuer, ticker="LTST3")

    # Older filing (Jan 2025)
    f1 = make_filing(
        session, issuer,
        reference_date=date(2024, 6, 30),
        available_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
    )
    make_statement_line(session, f1, canonical_key="ebit", value=50_000)
    make_computed_metric(
        session, issuer,
        metric_code="enterprise_value", value=500_000,
        reference_date=date(2024, 6, 30),
    )

    # Newer filing (Feb 2025)
    f2 = make_filing(
        session, issuer,
        reference_date=date(2024, 12, 31),
        available_at=datetime(2025, 2, 20, tzinfo=timezone.utc),
    )
    make_statement_line(session, f2, canonical_key="ebit", value=100_000)
    make_computed_metric(
        session, issuer,
        metric_code="enterprise_value", value=1_000_000,
        reference_date=date(2024, 12, 31),
    )
    session.commit()

    # As of March 2025 — both available, should use the newer one
    result = fetch_fundamentals_pit(session, date(2025, 3, 1))
    assert len(result) == 1
    asset, fs = result[0]
    assert asset.ticker == "LTST3"
    assert fs.ebit is not None
    assert float(fs.ebit) == 100_000.0


def test_pit_restatement_not_visible_before_release(session):
    """Restatement filed later (available_at = T2) doesn't affect ranking at T1 < T2."""
    issuer = make_issuer(session, cvm_code="003", cnpj="00000000000003")
    make_security(session, issuer, ticker="REST3")

    # Original filing available Jan 2025
    f1 = make_filing(
        session, issuer,
        reference_date=date(2024, 12, 31),
        available_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
    )
    make_statement_line(session, f1, canonical_key="ebit", value=80_000)
    make_computed_metric(session, issuer, metric_code="enterprise_value", value=800_000)

    # Restatement available Jun 2025
    f2 = make_filing(
        session, issuer,
        reference_date=date(2024, 12, 31),
        available_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        is_restatement=True,
    )
    make_statement_line(session, f2, canonical_key="ebit", value=120_000)
    session.commit()

    # At March 2025, restatement not yet visible — should use original
    result = fetch_fundamentals_pit(session, date(2025, 3, 1))
    assert len(result) == 1
    _, fs = result[0]
    assert float(fs.ebit) == 80_000.0


def test_pit_stale_market_data_excluded(session):
    """Market snapshot older than staleness window is excluded."""
    issuer = make_issuer(session, cvm_code="004", cnpj="00000000000004")
    sec = make_security(session, issuer, ticker="STAL3")

    # Snapshot from 30 days ago (stale with default 7-day window)
    make_market_snapshot(
        session, sec,
        price=10.0,
        fetched_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    session.commit()

    prices = fetch_market_pit(session, date(2025, 3, 1), max_staleness_days=7)
    assert "STAL3" not in prices


def test_delisted_asset_participates_when_historically_valid(session):
    """Security with valid_to = 2024-06 should appear in universe at 2024-03."""
    issuer = make_issuer(session, cvm_code="005", cnpj="00000000000005")
    make_security(
        session, issuer, ticker="DLST3",
        valid_from=date(2020, 1, 1),
        valid_to=date(2024, 6, 30),
    )
    session.commit()

    universe = fetch_eligible_universe_pit(session, date(2024, 3, 15))
    assert "DLST3" in universe


def test_delisted_asset_excluded_after_valid_to(session):
    """Security with valid_to = 2024-06 should NOT appear at 2024-09."""
    issuer = make_issuer(session, cvm_code="006", cnpj="00000000000006")
    make_security(
        session, issuer, ticker="DLST4",
        valid_from=date(2020, 1, 1),
        valid_to=date(2024, 6, 30),
    )
    session.commit()

    universe = fetch_eligible_universe_pit(session, date(2024, 9, 1))
    assert "DLST4" not in universe
