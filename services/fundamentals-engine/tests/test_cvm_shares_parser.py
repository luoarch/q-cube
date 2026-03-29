"""Spec tests for CVM shares parser (Plan 5 S1).

Written before implementation — these define the contract.
"""

from __future__ import annotations

from datetime import date

import pytest

from q3_fundamentals_engine.shares.parser import (
    ShareCountRow,
    _normalize_cnpj,
    _estimate_publication_date,
    parse_composicao_capital,
)


# ---------------------------------------------------------------------------
# _normalize_cnpj
# ---------------------------------------------------------------------------


class TestNormalizeCnpj:
    def test_digits_only(self) -> None:
        assert _normalize_cnpj("33000167000101") == "33000167000101"

    def test_with_punctuation(self) -> None:
        assert _normalize_cnpj("33.000.167/0001-01") == "33000167000101"

    def test_empty(self) -> None:
        assert _normalize_cnpj("") == ""

    def test_with_spaces(self) -> None:
        assert _normalize_cnpj(" 33.000.167 / 0001-01 ") == "33000167000101"


# ---------------------------------------------------------------------------
# _estimate_publication_date
# ---------------------------------------------------------------------------


class TestEstimatePublicationDate:
    def test_dfp_adds_90_days(self) -> None:
        # DFP ref 2024-12-31 → pub 2025-03-31
        result = _estimate_publication_date(date(2024, 12, 31), "DFP")
        assert result == date(2025, 3, 31)

    def test_itr_adds_45_days(self) -> None:
        # ITR ref 2024-06-30 → pub 2024-08-14
        result = _estimate_publication_date(date(2024, 6, 30), "ITR")
        assert result == date(2024, 8, 14)

    def test_itr_q1(self) -> None:
        # ITR ref 2024-03-31 → pub 2024-05-15
        result = _estimate_publication_date(date(2024, 3, 31), "ITR")
        assert result == date(2024, 5, 15)


# ---------------------------------------------------------------------------
# parse_composicao_capital
# ---------------------------------------------------------------------------


def _make_row(
    cnpj: str = "33.000.167/0001-01",
    dt_refer: str = "2024-12-31",
    total: str = "1000000",
    treasury: str = "50000",
) -> dict[str, str]:
    return {
        "CNPJ_CIA": cnpj,
        "DT_REFER": dt_refer,
        "QT_ACAO_TOTAL_CAP_INTEGR": total,
        "QT_ACAO_TOTAL_TESOURO": treasury,
    }


class TestParseComposicaoCapital:
    def test_basic_parse(self) -> None:
        rows = [_make_row()]
        result = parse_composicao_capital(rows, "DFP", "CVM_DFP_2024")
        assert len(result) == 1
        r = result[0]
        assert r.cnpj == "33000167000101"
        assert r.reference_date == date(2024, 12, 31)
        assert r.document_type == "DFP"
        assert r.total_shares == 1_000_000
        assert r.treasury_shares == 50_000
        assert r.net_shares == 950_000
        assert r.publication_date_estimated == date(2025, 3, 31)
        assert r.source_file == "CVM_DFP_2024"

    def test_skips_total_zero(self) -> None:
        rows = [_make_row(total="0")]
        result = parse_composicao_capital(rows, "DFP", "src")
        assert len(result) == 0

    def test_skips_total_negative(self) -> None:
        rows = [_make_row(total="-100")]
        result = parse_composicao_capital(rows, "DFP", "src")
        assert len(result) == 0

    def test_skips_empty_cnpj(self) -> None:
        rows = [_make_row(cnpj="")]
        result = parse_composicao_capital(rows, "DFP", "src")
        assert len(result) == 0

    def test_normalizes_cnpj(self) -> None:
        rows = [_make_row(cnpj="33.000.167/0001-01")]
        result = parse_composicao_capital(rows, "DFP", "src")
        assert result[0].cnpj == "33000167000101"

    def test_multiple_rows(self) -> None:
        rows = [
            _make_row(cnpj="11111111000100", total="500"),
            _make_row(cnpj="22222222000100", total="1000"),
        ]
        result = parse_composicao_capital(rows, "ITR", "src")
        assert len(result) == 2

    def test_itr_publication_date(self) -> None:
        rows = [_make_row(dt_refer="2024-06-30")]
        result = parse_composicao_capital(rows, "ITR", "src")
        assert result[0].publication_date_estimated == date(2024, 8, 14)

    def test_invalid_document_type_raises(self) -> None:
        with pytest.raises(ValueError, match="document_type"):
            parse_composicao_capital([], "FCA", "src")

    def test_skips_invalid_date(self) -> None:
        rows = [_make_row(dt_refer="not-a-date")]
        result = parse_composicao_capital(rows, "DFP", "src")
        assert len(result) == 0

    def test_skips_invalid_total(self) -> None:
        rows = [_make_row(total="abc")]
        result = parse_composicao_capital(rows, "DFP", "src")
        assert len(result) == 0

    def test_treasury_zero(self) -> None:
        rows = [_make_row(treasury="0")]
        result = parse_composicao_capital(rows, "DFP", "src")
        assert result[0].net_shares == result[0].total_shares

    def test_empty_treasury_field(self) -> None:
        rows = [_make_row(treasury="")]
        result = parse_composicao_capital(rows, "DFP", "src")
        assert result[0].treasury_shares == 0
        assert result[0].net_shares == result[0].total_shares

    def test_empty_input(self) -> None:
        result = parse_composicao_capital([], "DFP", "src")
        assert result == []

    def test_frozen_dataclass(self) -> None:
        rows = [_make_row()]
        result = parse_composicao_capital(rows, "DFP", "src")
        with pytest.raises(AttributeError):
            result[0].cnpj = "modified"  # type: ignore[misc]
