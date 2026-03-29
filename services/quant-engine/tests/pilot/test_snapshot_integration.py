"""Integration tests for SnapshotService (MF-RUNTIME-01A S2).

Uses real DB. Tests persistence + idempotency via unique constraints.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from q3_quant_engine.pilot.services import SnapshotService

# These tests require a running Postgres with migrations applied.
# Skip if DB not available.
try:
    from q3_quant_engine.db.session import SessionLocal
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _DB_AVAILABLE, reason="DB not available")

_SNAPSHOT_DATE = date(2099, 1, 2)  # Far future — won't collide with real data


def _ranking_item(
    ticker: str = "TEST3",
    model: str = "NPY_ROC",
    rank: int = 1,
    score: float = 0.15,
    status: str = "fully_evaluated",
    ey: float = 0.12,
    roc: float = 0.35,
    npy: float | None = 0.08,
) -> dict:
    return {
        "ticker": ticker,
        "modelFamily": model,
        "rankWithinModel": rank,
        "compositeScore": score,
        "investabilityStatus": status,
        "earningsYield": ey,
        "returnOnCapital": roc,
        "netPayoutYield": npy,
    }


class TestSnapshotServiceIntegration:
    def setup_method(self) -> None:
        self.svc = SnapshotService()

    def _cleanup(self, session) -> None:  # type: ignore[no-untyped-def]
        session.execute(text(f"DELETE FROM ranking_snapshots WHERE snapshot_date = '{_SNAPSHOT_DATE}'"))
        session.commit()

    def test_create_persists_rows(self) -> None:
        items = [
            _ranking_item(ticker="TSTA3", rank=1),
            _ranking_item(ticker="TSTB3", rank=2, model="EY_ROC", status="partially_evaluated", npy=None),
        ]
        with SessionLocal() as session:
            try:
                result = self.svc.create_daily_snapshot(session, _SNAPSHOT_DATE, items)
                session.commit()

                assert result.inserted == 2
                assert result.updated == 0
                assert result.total == 2

                # Verify in DB
                count = session.execute(text(
                    f"SELECT count(*) FROM ranking_snapshots WHERE snapshot_date = '{_SNAPSHOT_DATE}'"
                )).scalar()
                assert count == 2

                # Verify fields
                row = session.execute(text(
                    f"SELECT model_family, rank_within_model, earnings_yield, net_payout_yield "
                    f"FROM ranking_snapshots WHERE snapshot_date = '{_SNAPSHOT_DATE}' AND ticker = 'TSTA3'"
                )).fetchone()
                assert row[0] == "NPY_ROC"
                assert row[1] == 1
                assert float(row[2]) == pytest.approx(0.12)
                assert float(row[3]) == pytest.approx(0.08)
            finally:
                self._cleanup(session)

    def test_rerun_is_idempotent(self) -> None:
        items = [_ranking_item(ticker="TSTA3")]
        with SessionLocal() as session:
            try:
                r1 = self.svc.create_daily_snapshot(session, _SNAPSHOT_DATE, items)
                session.commit()
                assert r1.inserted == 1

                r2 = self.svc.create_daily_snapshot(session, _SNAPSHOT_DATE, items)
                session.commit()
                assert r2.inserted == 0
                assert r2.updated == 1

                # Still only 1 row
                count = session.execute(text(
                    f"SELECT count(*) FROM ranking_snapshots WHERE snapshot_date = '{_SNAPSHOT_DATE}'"
                )).scalar()
                assert count == 1
            finally:
                self._cleanup(session)

    def test_empty_input(self) -> None:
        with SessionLocal() as session:
            result = self.svc.create_daily_snapshot(session, _SNAPSHOT_DATE, [])
            assert result.inserted == 0
            assert result.total == 0
