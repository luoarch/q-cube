"""Spec tests for CVM shares loader (Plan 5 S1).

Tests idempotent upsert and CNPJ-to-issuer matching.
Uses in-memory SQLite for isolation (no real DB needed).
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from q3_fundamentals_engine.shares.parser import ShareCountRow
from q3_fundamentals_engine.shares.loader import persist_share_counts, LoadResult


_ISSUER_ID = uuid.uuid4()
_CNPJ = "33000167000101"


def _make_share_row(
    cnpj: str = _CNPJ,
    ref_date: date = date(2024, 12, 31),
    doc_type: str = "DFP",
    total: int = 1_000_000,
    treasury: int = 50_000,
) -> ShareCountRow:
    return ShareCountRow(
        cnpj=cnpj,
        reference_date=ref_date,
        document_type=doc_type,
        total_shares=total,
        treasury_shares=treasury,
        net_shares=total - treasury,
        publication_date_estimated=date(2025, 3, 31),
        source_file="test_source",
    )


class TestPersistShareCounts:
    """Unit tests using mock session — no real DB."""

    def test_insert_new_row(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        issuer_map = {_CNPJ: _ISSUER_ID}
        rows = [_make_share_row()]

        result = persist_share_counts(session, rows, issuer_map=issuer_map)

        assert result.inserted == 1
        assert result.updated == 0
        assert result.skipped_no_issuer == 0
        session.add.assert_called_once()

    def test_update_existing_row(self) -> None:
        existing = MagicMock()
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = existing

        issuer_map = {_CNPJ: _ISSUER_ID}
        rows = [_make_share_row(total=2_000_000, treasury=100_000)]

        result = persist_share_counts(session, rows, issuer_map=issuer_map)

        assert result.inserted == 0
        assert result.updated == 1
        assert existing.total_shares == 2_000_000
        assert existing.treasury_shares == 100_000
        assert existing.net_shares == 1_900_000

    def test_idempotent_double_insert(self) -> None:
        """Running persist twice with same data = same result."""
        session = MagicMock()
        # First call: no existing row
        session.execute.return_value.scalar_one_or_none.return_value = None

        issuer_map = {_CNPJ: _ISSUER_ID}
        rows = [_make_share_row()]

        r1 = persist_share_counts(session, rows, issuer_map=issuer_map)
        assert r1.inserted == 1

        # Second call: existing row returned
        existing = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = existing

        r2 = persist_share_counts(session, rows, issuer_map=issuer_map)
        assert r2.updated == 1
        assert r2.inserted == 0

    def test_skip_unknown_cnpj(self) -> None:
        session = MagicMock()
        issuer_map = {_CNPJ: _ISSUER_ID}
        rows = [_make_share_row(cnpj="99999999000199")]

        result = persist_share_counts(session, rows, issuer_map=issuer_map)

        assert result.skipped_no_issuer == 1
        assert result.inserted == 0
        session.add.assert_not_called()

    def test_empty_input(self) -> None:
        session = MagicMock()
        result = persist_share_counts(session, [], issuer_map={})

        assert result.total_rows == 0
        assert result.inserted == 0

    def test_mixed_known_and_unknown(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        issuer_map = {_CNPJ: _ISSUER_ID}
        rows = [
            _make_share_row(cnpj=_CNPJ),
            _make_share_row(cnpj="00000000000000"),
        ]

        result = persist_share_counts(session, rows, issuer_map=issuer_map)

        assert result.inserted == 1
        assert result.skipped_no_issuer == 1
        assert result.total_rows == 2

    def test_load_result_fields(self) -> None:
        r = LoadResult(inserted=5, updated=3, skipped_no_issuer=2, total_rows=10)
        assert r.inserted == 5
        assert r.updated == 3
        assert r.skipped_no_issuer == 2
        assert r.total_rows == 10
