"""E2E tests for pilot runtime pipeline (MF-RUNTIME-01A S3).

Full chain: ranking fixture → snapshot → market prices → forward returns.
Uses real DB + FakeScheduler. No HTTP, no cron.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from q3_quant_engine.pilot.scheduler import FakeScheduler
from q3_quant_engine.pilot.services import SnapshotService, ForwardReturnService

try:
    from q3_quant_engine.db.session import SessionLocal
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _DB_AVAILABLE, reason="DB not available")

_SNAPSHOT_DATE = date(2098, 6, 1)  # Monday, far future
_TICKERS = ["E2EA3", "E2EB3", "E2EC3"]


def _ranking_items() -> list[dict]:
    return [
        {
            "ticker": "E2EA3", "modelFamily": "NPY_ROC", "rankWithinModel": 1,
            "compositeScore": 0.10, "investabilityStatus": "fully_evaluated",
            "earningsYield": 0.15, "returnOnCapital": 0.40, "netPayoutYield": 0.09,
        },
        {
            "ticker": "E2EB3", "modelFamily": "NPY_ROC", "rankWithinModel": 2,
            "compositeScore": 0.20, "investabilityStatus": "fully_evaluated",
            "earningsYield": 0.10, "returnOnCapital": 0.25, "netPayoutYield": 0.05,
        },
        {
            "ticker": "E2EC3", "modelFamily": "EY_ROC", "rankWithinModel": 1,
            "compositeScore": 0.30, "investabilityStatus": "partially_evaluated",
            "earningsYield": 0.08, "returnOnCapital": 0.20, "netPayoutYield": None,
        },
    ]


class TestE2ERuntime:
    """Full pipeline E2E: snapshot → prices → returns."""

    def setup_method(self) -> None:
        self.snap_svc = SnapshotService()
        self.ret_svc = ForwardReturnService()

    def _setup_securities(self, session) -> dict[str, uuid.UUID]:  # type: ignore[no-untyped-def]
        """Create test issuers + securities. Return ticker → security_id."""
        sec_map = {}
        for i, ticker in enumerate(_TICKERS):
            iid = uuid.uuid4()
            sid = uuid.uuid4()
            session.execute(text(
                f"INSERT INTO issuers (id, cvm_code, legal_name, cnpj, status) "
                f"VALUES ('{iid}', '99900{i}', 'E2E Issuer {i}', '9999999900{i:04d}', 'active')"
            ))
            session.execute(text(
                f"INSERT INTO securities (id, issuer_id, ticker, is_primary, valid_from) "
                f"VALUES ('{sid}', '{iid}', '{ticker}', true, '2020-01-01')"
            ))
            sec_map[ticker] = sid
        session.flush()
        return sec_map

    def _insert_prices(self, session, sec_map: dict[str, uuid.UUID]) -> None:  # type: ignore[no-untyped-def]
        """Insert market prices at t0 (snapshot_date) and t+1d (next weekday)."""
        t0 = datetime(2098, 6, 1, 18, 0, 0, tzinfo=timezone.utc)
        t1 = datetime(2098, 6, 2, 18, 0, 0, tzinfo=timezone.utc)  # Tuesday

        prices = {
            "E2EA3": (100.0, 112.0),   # +12%
            "E2EB3": (50.0, 45.0),     # -10%
            "E2EC3": (200.0, 210.0),   # +5%
        }
        for ticker, (p0, p1) in prices.items():
            sid = sec_map[ticker]
            session.execute(text(
                f"INSERT INTO market_snapshots (id, security_id, source, price, market_cap, fetched_at) "
                f"VALUES ('{uuid.uuid4()}', '{sid}', 'yahoo', {p0}, {p0 * 1000000}, '{t0.isoformat()}')"
            ))
            session.execute(text(
                f"INSERT INTO market_snapshots (id, security_id, source, price, market_cap, fetched_at) "
                f"VALUES ('{uuid.uuid4()}', '{sid}', 'yahoo', {p1}, {p1 * 1000000}, '{t1.isoformat()}')"
            ))
        session.flush()

    def _cleanup(self, session) -> None:  # type: ignore[no-untyped-def]
        session.execute(text(f"DELETE FROM forward_returns WHERE snapshot_date = '{_SNAPSHOT_DATE}'"))
        session.execute(text(f"DELETE FROM ranking_snapshots WHERE snapshot_date = '{_SNAPSHOT_DATE}'"))
        for t in _TICKERS:
            session.execute(text(f"DELETE FROM market_snapshots WHERE security_id IN (SELECT id FROM securities WHERE ticker = '{t}')"))
            session.execute(text(f"DELETE FROM securities WHERE ticker = '{t}'"))
        session.execute(text("DELETE FROM issuers WHERE cvm_code LIKE '99900%'"))
        session.commit()

    def test_e2e_snapshot_creation(self) -> None:
        """E2E-1: Create snapshot from ranking fixture → verify rows in DB."""
        with SessionLocal() as session:
            try:
                result = self.snap_svc.create_daily_snapshot(
                    session, _SNAPSHOT_DATE, _ranking_items(),
                )
                session.commit()

                assert result.inserted == 3
                assert result.total == 3

                rows = session.execute(text(
                    f"SELECT ticker, model_family, investability_status "
                    f"FROM ranking_snapshots WHERE snapshot_date = '{_SNAPSHOT_DATE}' "
                    f"ORDER BY ticker"
                )).fetchall()
                assert len(rows) == 3
                assert rows[0][1] == "NPY_ROC"  # E2EA3
                assert rows[2][1] == "EY_ROC"   # E2EC3
                assert rows[2][2] == "partially_evaluated"
            finally:
                self._cleanup(session)

    def test_e2e_forward_returns(self) -> None:
        """E2E-2: Snapshot exists + prices inserted → compute returns → verify."""
        with SessionLocal() as session:
            try:
                sec_map = self._setup_securities(session)
                self._insert_prices(session, sec_map)
                self.snap_svc.create_daily_snapshot(
                    session, _SNAPSHOT_DATE, _ranking_items(),
                )
                session.commit()

                result = self.ret_svc.compute_forward_returns(
                    session, _SNAPSHOT_DATE, "1d",
                )
                session.commit()

                assert result.inserted == 3
                assert result.skipped == 0

                # Verify return values
                ret_rows = session.execute(text(
                    f"SELECT ticker, return_value FROM forward_returns "
                    f"WHERE snapshot_date = '{_SNAPSHOT_DATE}' ORDER BY ticker"
                )).fetchall()
                assert len(ret_rows) == 3
                assert float(ret_rows[0][1]) == pytest.approx(0.12)   # E2EA3: (112-100)/100
                assert float(ret_rows[1][1]) == pytest.approx(-0.10)  # E2EB3: (45-50)/50
                assert float(ret_rows[2][1]) == pytest.approx(0.05)   # E2EC3: (210-200)/200
            finally:
                self._cleanup(session)

    def test_e2e_full_chain_with_scheduler(self, caplog) -> None:
        """E2E-3: Full chain via FakeScheduler — ranking → snapshot → prices → returns."""
        with SessionLocal() as session:
            try:
                sec_map = self._setup_securities(session)
                self._insert_prices(session, sec_map)
                session.commit()

                # Wire up scheduler
                scheduler = FakeScheduler()
                ranking = _ranking_items()

                scheduler.register(
                    "daily_snapshot",
                    "0 18 * * 1-5",
                    lambda: self.snap_svc.create_daily_snapshot(
                        session, _SNAPSHOT_DATE, ranking,
                    ),
                )
                scheduler.register(
                    "compute_returns_1d",
                    "0 19 * * 1-5",
                    lambda: self.ret_svc.compute_forward_returns(
                        session, _SNAPSHOT_DATE, "1d",
                    ),
                )

                # Fire snapshot job
                with caplog.at_level(logging.INFO):
                    scheduler.fire("daily_snapshot")
                session.commit()

                assert scheduler.fire_count("daily_snapshot") == 1

                # Verify snapshot persisted
                snap_count = session.execute(text(
                    f"SELECT count(*) FROM ranking_snapshots "
                    f"WHERE snapshot_date = '{_SNAPSHOT_DATE}'"
                )).scalar()
                assert snap_count == 3

                # Fire returns job
                with caplog.at_level(logging.INFO):
                    scheduler.fire("compute_returns_1d")
                session.commit()

                assert scheduler.fire_count("compute_returns_1d") == 1

                # Verify returns persisted
                ret_count = session.execute(text(
                    f"SELECT count(*) FROM forward_returns "
                    f"WHERE snapshot_date = '{_SNAPSHOT_DATE}'"
                )).scalar()
                assert ret_count == 3

                # Verify final state: 3 snapshots + 3 returns
                final = session.execute(text(f"""
                    SELECT rs.ticker, rs.model_family, fr.horizon, fr.return_value
                    FROM ranking_snapshots rs
                    JOIN forward_returns fr ON rs.snapshot_date = fr.snapshot_date AND rs.ticker = fr.ticker
                    WHERE rs.snapshot_date = '{_SNAPSHOT_DATE}'
                    ORDER BY rs.ticker
                """)).fetchall()
                assert len(final) == 3
                # E2EA3: NPY_ROC, 1d, +12%
                assert final[0][1] == "NPY_ROC"
                assert float(final[0][3]) == pytest.approx(0.12)

                # Verify logs emitted
                assert any("Snapshot" in r.message for r in caplog.records)
                assert any("Forward returns" in r.message for r in caplog.records)
            finally:
                self._cleanup(session)
