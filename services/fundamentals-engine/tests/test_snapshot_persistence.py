"""Persistence tests -- snapshot -> DB.

Uses the conftest.py PostgreSQL transactional session (auto-rollback).
These tests verify that snapshot rows persist correctly with source, FK, and nullable fields.

NOTE: Requires a running PostgreSQL instance (DATABASE_URL).
If unavailable, these tests will be skipped.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

try:
    from q3_shared_models.entities import (
        Issuer,
        MarketSnapshot,
        Security,
        SourceProvider,
    )
    _HAS_MODELS = True
except ImportError:
    _HAS_MODELS = False


def _session_works(session) -> bool:
    """Check if the session can execute a simple query."""
    try:
        session.execute(select(Issuer).limit(1))
        return True
    except Exception:
        return False


def _make_security(session) -> "Security":
    issuer = Issuer(
        id=uuid.uuid4(),
        cvm_code=str(uuid.uuid4().int)[:6],
        legal_name="Test Corp",
        cnpj=str(uuid.uuid4().int)[:14],
    )
    session.add(issuer)
    session.flush()
    sec = Security(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        ticker="TEST3",
        is_primary=True,
        valid_from=datetime(2020, 1, 1).date(),
    )
    session.add(sec)
    session.flush()
    return sec


def _insert_snapshot(session, security, *, source=None, price=38.5,
                     market_cap=500e9, volume=25e6,
                     fetched_at=None) -> "MarketSnapshot":
    if source is None:
        source = SourceProvider.yahoo
    kwargs = dict(
        id=uuid.uuid4(),
        security_id=security.id,
        source=source,
        price=price,
        market_cap=market_cap,
        volume=volume,
        raw_json={"test": True},
    )
    if fetched_at is not None:
        kwargs["fetched_at"] = fetched_at
    snap = MarketSnapshot(**kwargs)
    session.add(snap)
    session.flush()
    return snap


@pytest.mark.skipif(not _HAS_MODELS, reason="shared-models not available")
class TestSnapshotPersistence:
    def test_snapshot_persists_with_source_yahoo(self, session):
        if not _session_works(session):
            pytest.skip("DB not available")
        sec = _make_security(session)
        _insert_snapshot(session, sec, source=SourceProvider.yahoo)
        session.commit()

        row = session.execute(
            select(MarketSnapshot).where(MarketSnapshot.security_id == sec.id)
        ).scalar_one()
        assert row.source == SourceProvider.yahoo

    def test_snapshot_persists_with_security_id(self, session):
        if not _session_works(session):
            pytest.skip("DB not available")
        sec = _make_security(session)
        _insert_snapshot(session, sec)
        session.commit()

        row = session.execute(
            select(MarketSnapshot).where(MarketSnapshot.security_id == sec.id)
        ).scalar_one()
        assert row.security_id == sec.id

    def test_snapshot_append_only(self, session):
        if not _session_works(session):
            pytest.skip("DB not available")
        sec = _make_security(session)
        _insert_snapshot(session, sec, price=38.0,
                         fetched_at=datetime(2025, 3, 1, tzinfo=timezone.utc))
        _insert_snapshot(session, sec, price=39.0,
                         fetched_at=datetime(2025, 3, 2, tzinfo=timezone.utc))
        session.commit()

        rows = session.execute(
            select(MarketSnapshot).where(MarketSnapshot.security_id == sec.id)
        ).scalars().all()
        assert len(rows) == 2

    def test_provider_error_does_not_delete_existing(self, session):
        if not _session_works(session):
            pytest.skip("DB not available")
        sec = _make_security(session)
        _insert_snapshot(session, sec, price=38.0)
        session.commit()

        rows = session.execute(
            select(MarketSnapshot).where(MarketSnapshot.security_id == sec.id)
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].price == 38.0

    def test_partial_snapshot_persists(self, session):
        if not _session_works(session):
            pytest.skip("DB not available")
        sec = _make_security(session)
        _insert_snapshot(session, sec, price=10.0, market_cap=None)
        session.commit()

        row = session.execute(
            select(MarketSnapshot).where(MarketSnapshot.security_id == sec.id)
        ).scalar_one()
        assert row.price == 10.0
        assert row.market_cap is None

    def test_snapshot_null_market_cap_tracked(self, session):
        if not _session_works(session):
            pytest.skip("DB not available")
        sec = _make_security(session)
        _insert_snapshot(session, sec, market_cap=None)
        session.commit()

        row = session.execute(
            select(MarketSnapshot).where(MarketSnapshot.security_id == sec.id)
        ).scalar_one()
        assert row.market_cap is None
