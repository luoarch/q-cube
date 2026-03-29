"""Integration tests for ForwardReturnService (MF-RUNTIME-01A S2).

Uses real DB. Tests computation + persistence + idempotency.
Requires ranking_snapshots + market_snapshots with test data.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from q3_quant_engine.pilot.services import ForwardReturnService, SnapshotService

try:
    from q3_quant_engine.db.session import SessionLocal
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _DB_AVAILABLE, reason="DB not available")

_SNAPSHOT_DATE = date(2099, 1, 6)  # Monday in far future
_TICKER = "TSTFR3"


def _ranking_item(ticker: str = _TICKER) -> dict:
    return {
        "ticker": ticker,
        "modelFamily": "NPY_ROC",
        "rankWithinModel": 1,
        "compositeScore": 0.15,
        "investabilityStatus": "fully_evaluated",
        "earningsYield": 0.12,
        "returnOnCapital": 0.35,
        "netPayoutYield": 0.08,
    }


class TestForwardReturnServiceIntegration:
    def setup_method(self) -> None:
        self.snap_svc = SnapshotService()
        self.ret_svc = ForwardReturnService()

    def _cleanup(self, session) -> None:  # type: ignore[no-untyped-def]
        session.execute(text(f"DELETE FROM forward_returns WHERE snapshot_date = '{_SNAPSHOT_DATE}'"))
        session.execute(text(f"DELETE FROM ranking_snapshots WHERE snapshot_date = '{_SNAPSHOT_DATE}'"))
        session.execute(text(f"DELETE FROM market_snapshots WHERE security_id IN (SELECT id FROM securities WHERE ticker = '{_TICKER}')"))
        session.execute(text(f"DELETE FROM securities WHERE ticker = '{_TICKER}'"))
        session.execute(text(f"DELETE FROM issuers WHERE cvm_code = '999999'"))
        session.commit()

    def _setup_test_data(self, session) -> None:  # type: ignore[no-untyped-def]
        """Create issuer, security, snapshots, and market prices for test."""
        # Create issuer + security
        issuer_id = uuid.uuid4()
        sec_id = uuid.uuid4()
        session.execute(text(
            f"INSERT INTO issuers (id, cvm_code, legal_name, cnpj, status) "
            f"VALUES ('{issuer_id}', '999999', 'Test Issuer', '99999999000199', 'active')"
        ))
        session.execute(text(
            f"INSERT INTO securities (id, issuer_id, ticker, is_primary, valid_from) "
            f"VALUES ('{sec_id}', '{issuer_id}', '{_TICKER}', true, '2020-01-01')"
        ))

        # Create market snapshots (prices at t0 and t+1d)
        t0 = datetime(2099, 1, 6, 18, 0, 0, tzinfo=timezone.utc)  # Monday
        t1 = datetime(2099, 1, 7, 18, 0, 0, tzinfo=timezone.utc)  # Tuesday

        session.execute(text(
            f"INSERT INTO market_snapshots (id, security_id, source, price, market_cap, fetched_at) "
            f"VALUES ('{uuid.uuid4()}', '{sec_id}', 'yahoo', 100.0, 1000000, '{t0.isoformat()}')"
        ))
        session.execute(text(
            f"INSERT INTO market_snapshots (id, security_id, source, price, market_cap, fetched_at) "
            f"VALUES ('{uuid.uuid4()}', '{sec_id}', 'yahoo', 110.0, 1100000, '{t1.isoformat()}')"
        ))

        # Create ranking snapshot
        self.snap_svc.create_daily_snapshot(session, _SNAPSHOT_DATE, [_ranking_item()])
        session.commit()

    def test_compute_persists_returns(self) -> None:
        with SessionLocal() as session:
            try:
                self._setup_test_data(session)

                result = self.ret_svc.compute_forward_returns(session, _SNAPSHOT_DATE, "1d")
                session.commit()

                assert result.inserted == 1
                assert result.skipped == 0

                # Verify in DB
                row = session.execute(text(
                    f"SELECT price_t0, price_tn, return_value FROM forward_returns "
                    f"WHERE snapshot_date = '{_SNAPSHOT_DATE}' AND ticker = '{_TICKER}' AND horizon = '1d'"
                )).fetchone()
                assert row is not None
                assert float(row[2]) == pytest.approx(0.10)
            finally:
                self._cleanup(session)

    def test_rerun_is_idempotent(self) -> None:
        with SessionLocal() as session:
            try:
                self._setup_test_data(session)

                r1 = self.ret_svc.compute_forward_returns(session, _SNAPSHOT_DATE, "1d")
                session.commit()
                assert r1.inserted == 1

                r2 = self.ret_svc.compute_forward_returns(session, _SNAPSHOT_DATE, "1d")
                session.commit()
                assert r2.inserted == 0  # upsert — no new inserts
                assert r2.updated == 1   # existing row updated

                # Still only 1 row
                count = session.execute(text(
                    f"SELECT count(*) FROM forward_returns "
                    f"WHERE snapshot_date = '{_SNAPSHOT_DATE}' AND ticker = '{_TICKER}'"
                )).scalar()
                assert count == 1
            finally:
                self._cleanup(session)

    def test_no_snapshot_returns_empty(self) -> None:
        with SessionLocal() as session:
            result = self.ret_svc.compute_forward_returns(session, date(2099, 12, 31), "1d")
            assert result.total == 0

    def test_skip_when_no_price(self) -> None:
        """Ticker in snapshot but no market_snapshots → skipped, not errored."""
        with SessionLocal() as session:
            try:
                # Create issuer + security but NO market_snapshots
                issuer_id = uuid.uuid4()
                sec_id = uuid.uuid4()
                session.execute(text(
                    f"INSERT INTO issuers (id, cvm_code, legal_name, cnpj, status) "
                    f"VALUES ('{issuer_id}', '999998', 'No Price Issuer', '99999999000198', 'active')"
                ))
                session.execute(text(
                    f"INSERT INTO securities (id, issuer_id, ticker, is_primary, valid_from) "
                    f"VALUES ('{sec_id}', '{issuer_id}', 'NOPR3', true, '2020-01-01')"
                ))
                self.snap_svc.create_daily_snapshot(session, _SNAPSHOT_DATE, [
                    {
                        "ticker": "NOPR3", "modelFamily": "NPY_ROC", "rankWithinModel": 1,
                        "compositeScore": 0.1, "investabilityStatus": "fully_evaluated",
                        "earningsYield": 0.1, "returnOnCapital": 0.2, "netPayoutYield": 0.05,
                    }
                ])
                session.commit()

                result = self.ret_svc.compute_forward_returns(session, _SNAPSHOT_DATE, "1d")
                assert result.skipped == 1
                assert result.inserted == 0
            finally:
                session.execute(text(f"DELETE FROM forward_returns WHERE snapshot_date = '{_SNAPSHOT_DATE}'"))
                session.execute(text(f"DELETE FROM ranking_snapshots WHERE snapshot_date = '{_SNAPSHOT_DATE}'"))
                session.execute(text("DELETE FROM securities WHERE ticker = 'NOPR3'"))
                session.execute(text("DELETE FROM issuers WHERE cvm_code = '999998'"))
                session.commit()
