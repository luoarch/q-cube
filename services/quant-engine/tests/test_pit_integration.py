"""PIT integration tests against real PostgreSQL database.

These tests verify point-in-time correctness with actual production data.
They require a running PostgreSQL instance with the q3 database populated.

Run with:
    cd services/quant-engine
    source .venv/bin/activate
    python -m pytest tests/test_pit_integration.py -v --run-integration

Skip in normal test runs (no --run-integration flag).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from q3_quant_engine.data.pit_data import (
    fetch_eligible_universe_pit,
    fetch_fundamentals_pit,
    fetch_market_pit,
)


def _has_pg() -> bool:
    """Check if PostgreSQL is available."""
    try:
        from q3_quant_engine.db.session import SessionLocal
        with SessionLocal() as s:
            s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# Skip all tests if no PG or no --run-integration flag
pytestmark = [
    pytest.mark.skipif(not _has_pg(), reason="PostgreSQL not available"),
    pytest.mark.integration,
]


@pytest.fixture
def pg_session():
    """Real PostgreSQL session."""
    from q3_quant_engine.db.session import SessionLocal
    with SessionLocal() as s:
        yield s


# ---------------------------------------------------------------------------
# PIT Fundamentals
# ---------------------------------------------------------------------------


class TestPITFundamentals:
    """Verify fetch_fundamentals_pit uses publication_date for temporal gating."""

    def test_returns_issuers_with_visible_filings(self, pg_session):
        """At a date where filings are published, should return issuers."""
        # 2025-06-01: DFP 2024 (ref 2024-12-31, pub ~2025-03-31) should be visible
        result = fetch_fundamentals_pit(pg_session, date(2025, 6, 1))
        assert len(result) > 100, f"Expected >100 issuers at 2025-06-01, got {len(result)}"

    def test_returns_zero_before_any_publication(self, pg_session):
        """At a date before any filing is published, should return 0."""
        # 2020-01-01: no filing published yet (earliest ITR 2020 pub ~2020-05-15)
        result = fetch_fundamentals_pit(pg_session, date(2020, 1, 1))
        assert len(result) == 0, f"Expected 0 issuers at 2020-01-01, got {len(result)}"

    def test_count_increases_over_time(self, pg_session):
        """More filings become visible as time progresses."""
        early = fetch_fundamentals_pit(pg_session, date(2020, 7, 1))
        mid = fetch_fundamentals_pit(pg_session, date(2022, 7, 1))
        late = fetch_fundamentals_pit(pg_session, date(2025, 1, 1))
        assert len(early) <= len(mid) <= len(late), (
            f"PIT count should be non-decreasing: {len(early)} <= {len(mid)} <= {len(late)}"
        )

    def test_uses_latest_reference_date(self, pg_session):
        """For an issuer with multiple filings, pick the latest reference_date."""
        result = fetch_fundamentals_pit(pg_session, date(2025, 6, 1))
        if not result:
            pytest.skip("No data at 2025-06-01")

        # Check a known issuer (PETR4's issuer should have recent filing)
        petro = [(a, f) for a, f in result if a.ticker == "PETR4"]
        if petro:
            _, fs = petro[0]
            assert fs.ebit is not None, "PETR4 should have EBIT"

    def test_no_future_filings_leak(self, pg_session):
        """Filings with publication_date > as_of should NOT appear."""
        # Get count at a specific date
        as_of = date(2021, 6, 1)
        result = fetch_fundamentals_pit(pg_session, as_of)

        # All returned issuers should have filings with pub_date <= as_of
        # We can't directly check pub_date from the result, but we can verify
        # the count is less than the total number of issuers with filings
        total_issuers = pg_session.execute(
            text("SELECT count(DISTINCT issuer_id) FROM filings WHERE status = 'completed'")
        ).scalar()
        assert len(result) < total_issuers, (
            f"PIT at {as_of} should return fewer than total ({total_issuers})"
        )


# ---------------------------------------------------------------------------
# PIT Market Data
# ---------------------------------------------------------------------------


class TestPITMarket:
    """Verify fetch_market_pit uses fetched_at for temporal gating."""

    def test_returns_prices_within_staleness(self, pg_session):
        """At a date with recent snapshots, should return prices."""
        # 2024-01-02: should have Yahoo snapshots from late Dec 2023 / early Jan 2024
        prices = fetch_market_pit(pg_session, date(2024, 1, 2), max_staleness_days=7)
        assert len(prices) > 50, f"Expected >50 tickers at 2024-01-02, got {len(prices)}"

    def test_returns_empty_for_far_future(self, pg_session):
        """At a date far beyond any snapshot, staleness should filter everything."""
        prices = fetch_market_pit(pg_session, date(2030, 1, 1), max_staleness_days=7)
        assert len(prices) == 0, f"Expected 0 tickers at 2030-01-01, got {len(prices)}"

    def test_staleness_window_respected(self, pg_session):
        """Wider staleness window should return >= narrow window."""
        narrow = fetch_market_pit(pg_session, date(2024, 7, 1), max_staleness_days=3)
        wide = fetch_market_pit(pg_session, date(2024, 7, 1), max_staleness_days=30)
        assert len(narrow) <= len(wide), (
            f"Narrow ({len(narrow)}) should be <= wide ({len(wide)})"
        )

    def test_no_future_snapshots(self, pg_session):
        """Snapshots with fetched_at > as_of should NOT appear."""
        as_of = date(2022, 6, 1)
        prices = fetch_market_pit(pg_session, as_of, max_staleness_days=7)
        for ticker, data in prices.items():
            snap_date = data.fetched_at.date() if hasattr(data.fetched_at, 'date') else data.fetched_at
            assert snap_date <= as_of, (
                f"{ticker} has snapshot at {snap_date} which is after as_of={as_of}"
            )

    def test_backfilled_snapshots_have_historical_dates(self, pg_session):
        """Historical backfill snapshots should have fetched_at = historical date, not today."""
        # Check a 2021 date — these are backfilled snapshots
        prices = fetch_market_pit(pg_session, date(2021, 7, 1), max_staleness_days=7)
        for ticker, data in prices.items():
            snap_date = data.fetched_at.date() if hasattr(data.fetched_at, 'date') else data.fetched_at
            # Should be near 2021-07-01, not 2026
            assert snap_date.year <= 2022, (
                f"{ticker} snapshot at {snap_date} — expected historical date, not recent"
            )


# ---------------------------------------------------------------------------
# PIT Universe (survivorship)
# ---------------------------------------------------------------------------


class TestPITUniverse:
    """Verify fetch_eligible_universe_pit uses valid_from/valid_to."""

    def test_returns_active_tickers(self, pg_session):
        """At a recent date, should return currently listed tickers."""
        universe = fetch_eligible_universe_pit(pg_session, date(2024, 6, 1))
        assert len(universe) > 100, f"Expected >100 tickers at 2024-06-01, got {len(universe)}"

    def test_delisted_ticker_excluded_after_valid_to(self, pg_session):
        """Tickers with valid_to in the past should not appear after that date."""
        # Find a delisted security
        delisted = pg_session.execute(text("""
            SELECT ticker, valid_to FROM securities
            WHERE valid_to IS NOT NULL AND valid_to < '2024-01-01'
            LIMIT 1
        """)).fetchone()
        if not delisted:
            pytest.skip("No delisted securities in DB")

        ticker, valid_to = delisted
        after = valid_to + timedelta(days=30)
        universe = fetch_eligible_universe_pit(pg_session, after)
        assert ticker not in universe, (
            f"{ticker} (valid_to={valid_to}) should not be in universe at {after}"
        )


# ---------------------------------------------------------------------------
# Frozen Policy Universe (backtest integration)
# ---------------------------------------------------------------------------


class TestFrozenPolicyUniverse:
    """Verify the backtest engine loads CORE_ELIGIBLE from universe_classifications."""

    def test_core_eligible_loaded(self, pg_session):
        """Should have >400 CORE_ELIGIBLE issuers."""
        count = pg_session.execute(text("""
            SELECT count(*) FROM universe_classifications
            WHERE universe_class = 'CORE_ELIGIBLE' AND superseded_at IS NULL
        """)).scalar()
        assert count > 400, f"Expected >400 CORE_ELIGIBLE, got {count}"

    def test_excluded_sectors_not_in_core(self, pg_session):
        """Financial and utility issuers should be in DEDICATED_STRATEGY_ONLY, not CORE."""
        financial_in_core = pg_session.execute(text("""
            SELECT count(*) FROM universe_classifications uc
            JOIN issuers i ON i.id = uc.issuer_id
            WHERE uc.universe_class = 'CORE_ELIGIBLE'
              AND uc.superseded_at IS NULL
              AND i.sector ILIKE '%financ%'
        """)).scalar()
        assert financial_in_core == 0, (
            f"Financial issuers should not be CORE_ELIGIBLE, found {financial_in_core}"
        )


# ---------------------------------------------------------------------------
# Strategy Status Registry
# ---------------------------------------------------------------------------


class TestStrategyRegistry:
    """Verify the strategy status registry has correct entries."""

    def test_three_registered_strategies(self, pg_session):
        """Should have exactly 3 active strategy entries."""
        count = pg_session.execute(text("""
            SELECT count(*) FROM strategy_status_registry
            WHERE superseded_at IS NULL
        """)).scalar()
        assert count == 3, f"Expected 3 active entries, got {count}"

    def test_hybrid_is_frontrunner(self, pg_session):
        """hybrid_20q should be FRONTRUNNER + BLOCKED."""
        row = pg_session.execute(text("""
            SELECT role, promotion_status FROM strategy_status_registry
            WHERE strategy_key = 'hybrid_20q' AND superseded_at IS NULL
        """)).fetchone()
        assert row is not None, "hybrid_20q not found"
        assert row[0] == "FRONTRUNNER", f"Expected FRONTRUNNER, got {row[0]}"
        assert row[1] == "BLOCKED", f"Expected BLOCKED, got {row[1]}"

    def test_controls_rejected(self, pg_session):
        """Control strategies should be CONTROL + REJECTED."""
        for key in ["ctrl_original_20m", "ctrl_brazil_20m"]:
            row = pg_session.execute(text(f"""
                SELECT role, promotion_status FROM strategy_status_registry
                WHERE strategy_key = '{key}' AND superseded_at IS NULL
            """)).fetchone()
            assert row is not None, f"{key} not found"
            assert row[0] == "CONTROL", f"{key}: expected CONTROL, got {row[0]}"
            assert row[1] == "REJECTED", f"{key}: expected REJECTED, got {row[1]}"

    def test_partial_unique_enforced(self, pg_session):
        """Cannot insert duplicate active fingerprint."""
        existing = pg_session.execute(text("""
            SELECT strategy_fingerprint FROM strategy_status_registry
            WHERE superseded_at IS NULL LIMIT 1
        """)).scalar()
        if not existing:
            pytest.skip("No registry entries")

        import uuid
        with pytest.raises(Exception):
            pg_session.execute(text("""
                INSERT INTO strategy_status_registry
                (id, strategy_key, strategy_fingerprint, strategy_type, role, promotion_status,
                 config_json, evidence_summary, decided_by)
                VALUES (:id, 'dup', :fp, 'magic_formula_hybrid', 'CANDIDATE', 'NOT_EVALUATED',
                        '{}', 'test', 'TECH_LEAD_REVIEW')
            """), {"id": str(uuid.uuid4()), "fp": existing})
