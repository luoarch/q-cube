"""Shared test fixtures — PostgreSQL session with automatic rollback."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from q3_fundamentals_engine.config import DATABASE_URL


@pytest.fixture()
def session():
    """Provide a transactional PostgreSQL session that rolls back after each test."""
    engine = create_engine(DATABASE_URL, future=True)
    with engine.connect() as conn:
        txn = conn.begin()
        with Session(bind=conn, join_transaction_mode="create_savepoint") as s:
            yield s
        txn.rollback()
    engine.dispose()
