"""Tests for CVM filing parsers."""

from __future__ import annotations

from q3_fundamentals_engine.parsers.models import ParsedRow
from q3_fundamentals_engine.parsers.dfp import DfpParser
from q3_fundamentals_engine.parsers.itr import ItrParser
from q3_fundamentals_engine.parsers.factory import FilingParserFactory


def test_factory_creates_dfp_parser() -> None:
    parser = FilingParserFactory.create("DFP")
    assert isinstance(parser, DfpParser)


def test_factory_creates_itr_parser() -> None:
    parser = FilingParserFactory.create("ITR")
    assert isinstance(parser, ItrParser)


def test_factory_raises_for_unknown() -> None:
    import pytest
    with pytest.raises(ValueError, match="Unknown document type"):
        FilingParserFactory.create("UNKNOWN")


def test_parsed_row_dataclass() -> None:
    row = ParsedRow(
        cd_cvm="9512",
        cnpj="33000167000101",
        company_name="PETROLEO BRASILEIRO S.A. PETROBRAS",
        ref_date="2024-12-31",
        account_code="3.05",
        account_description="Resultado Antes do Resultado Financeiro e dos Tributos",
        value=137_000_000_000.0,
        scale="MIL",
        period_order="ÚLTIMO",
        version=1,
        statement_type="DRE",
        scope="con",
    )
    assert row.cd_cvm == "9512"
    assert row.value == 137_000_000_000.0
