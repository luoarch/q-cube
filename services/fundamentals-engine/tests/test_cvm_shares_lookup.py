"""Spec tests for CVM shares lookup (Plan 5 S2).

Tests exact quarter-end match, PIT filtering, DFP>ITR precedence.
Written before implementation.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from q3_fundamentals_engine.shares.lookup import find_cvm_shares


def _make_share_count(
    *,
    reference_date: date = date(2024, 12, 31),
    document_type: str = "DFP",
    net_shares: float = 1_000_000,
    publication_date_estimated: date = date(2025, 3, 31),
) -> MagicMock:
    m = MagicMock()
    m.reference_date = reference_date
    m.document_type = document_type
    m.net_shares = net_shares
    m.publication_date_estimated = publication_date_estimated
    return m


_ISSUER = uuid.uuid4()


class TestFindCvmShares:
    """Core lookup contract: exact match, no nearest-neighbor."""

    def test_exact_match_returns_row(self) -> None:
        row = _make_share_count(reference_date=date(2024, 12, 31))
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [row]

        result = find_cvm_shares(session, _ISSUER, date(2024, 12, 31))
        assert result is row

    def test_no_match_returns_none(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = find_cvm_shares(session, _ISSUER, date(2024, 12, 31))
        assert result is None

    def test_mismatch_date_returns_none(self) -> None:
        """reference_date 2024-11-30 does NOT match target 2024-12-31."""
        # The query itself filters by exact date, so an empty result is returned
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = find_cvm_shares(session, _ISSUER, date(2024, 12, 31))
        assert result is None


class TestDfpPrecedence:
    """DFP > ITR for same reference_date (Plan 5 §6.5)."""

    def test_dfp_preferred_over_itr(self) -> None:
        dfp = _make_share_count(document_type="DFP", net_shares=1_000_000)
        itr = _make_share_count(document_type="ITR", net_shares=999_000)
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [itr, dfp]

        result = find_cvm_shares(session, _ISSUER, date(2024, 12, 31))
        assert result is dfp

    def test_itr_only_when_no_dfp(self) -> None:
        itr = _make_share_count(document_type="ITR", net_shares=999_000)
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [itr]

        result = find_cvm_shares(session, _ISSUER, date(2024, 12, 31))
        assert result is itr

    def test_dfp_wins_regardless_of_list_order(self) -> None:
        dfp = _make_share_count(document_type="DFP", net_shares=1_000_000)
        itr = _make_share_count(document_type="ITR", net_shares=999_000)
        session = MagicMock()
        # DFP first in list
        session.execute.return_value.scalars.return_value.all.return_value = [dfp, itr]

        result = find_cvm_shares(session, _ISSUER, date(2024, 12, 31))
        assert result is dfp


class TestPitFiltering:
    """knowledge_date filtering via publication_date_estimated."""

    def test_no_knowledge_date_returns_row(self) -> None:
        """Relaxed mode: no PIT filter."""
        row = _make_share_count(publication_date_estimated=date(2025, 3, 31))
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [row]

        result = find_cvm_shares(session, _ISSUER, date(2024, 12, 31))
        assert result is row

    def test_knowledge_date_before_publication_returns_none(self) -> None:
        """Strict PIT: knowledge_date < publication_date → not available yet."""
        row = _make_share_count(publication_date_estimated=date(2025, 3, 31))
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [row]

        result = find_cvm_shares(
            session, _ISSUER, date(2024, 12, 31),
            knowledge_date=date(2025, 2, 1),
        )
        assert result is None

    def test_knowledge_date_equal_to_publication_returns_row(self) -> None:
        """Boundary: knowledge_date == publication_date → available."""
        row = _make_share_count(publication_date_estimated=date(2025, 3, 31))
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [row]

        result = find_cvm_shares(
            session, _ISSUER, date(2024, 12, 31),
            knowledge_date=date(2025, 3, 31),
        )
        assert result is row

    def test_knowledge_date_after_publication_returns_row(self) -> None:
        row = _make_share_count(publication_date_estimated=date(2025, 3, 31))
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [row]

        result = find_cvm_shares(
            session, _ISSUER, date(2024, 12, 31),
            knowledge_date=date(2025, 6, 1),
        )
        assert result is row

    def test_pit_filters_before_dfp_precedence(self) -> None:
        """If DFP exists but is not PIT-available, ITR that IS available wins."""
        dfp = _make_share_count(document_type="DFP", publication_date_estimated=date(2025, 3, 31))
        itr = _make_share_count(document_type="ITR", publication_date_estimated=date(2025, 2, 14))
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [dfp, itr]

        # knowledge_date is after ITR pub but before DFP pub
        result = find_cvm_shares(
            session, _ISSUER, date(2024, 12, 31),
            knowledge_date=date(2025, 2, 28),
        )
        assert result is itr


class TestNoNearestNeighbor:
    """Explicit confirmation: lookup does NOT approximate."""

    def test_no_window_approximation(self) -> None:
        """A row with reference_date 2024-11-30 must NOT match target 2024-12-31.
        The SQL query filters by exact date, so we get empty results."""
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = find_cvm_shares(session, _ISSUER, date(2024, 12, 31))
        assert result is None
