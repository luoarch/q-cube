"""Unit tests for refiner scoring blocks."""

from datetime import date

from q3_quant_engine.refiner.scoring import (
    score_capital_discipline,
    score_earnings_quality,
    score_operating_consistency,
    score_safety,
)
from q3_quant_engine.refiner.types import PeriodValue


def _pv(dates_values: list[tuple[str, float | None]]) -> list[PeriodValue]:
    return [PeriodValue(date.fromisoformat(d), v) for d, v in dates_values]


DATES_3P = [("2022-12-31", None), ("2023-12-31", None), ("2024-12-31", None)]


def _make_3p(v1: float | None, v2: float | None, v3: float | None) -> list[PeriodValue]:
    return _pv([
        ("2022-12-31", v1),
        ("2023-12-31", v2),
        ("2024-12-31", v3),
    ])


class TestEarningsQuality:
    def test_all_improving_returns_high_score(self):
        data = {
            "cash_conversion": _make_3p(0.8, 0.9, 1.0),
            "cash_from_operations": _make_3p(100, 120, 140),
            "net_income": _make_3p(80, 90, 100),
            "cash_from_investing": _make_3p(-50, -45, -40),
            "revenue": _make_3p(500, 550, 600),
        }
        block = score_earnings_quality(data)
        assert block.name == "earnings_quality"
        assert block.score >= 0.7

    def test_all_declining_returns_low_score(self):
        data = {
            "cash_conversion": _make_3p(1.0, 0.8, 0.6),
            "cash_from_operations": _make_3p(140, 120, 100),
            "net_income": _make_3p(100, 110, 120),
            "cash_from_investing": _make_3p(-40, -50, -60),
            "revenue": _make_3p(600, 580, 560),
        }
        block = score_earnings_quality(data)
        assert block.score <= 0.5

    def test_empty_data_returns_neutral(self):
        block = score_earnings_quality({})
        assert block.score == 0.5

    def test_partial_data(self):
        data = {
            "cash_conversion": _make_3p(0.8, 0.9, 1.0),
        }
        block = score_earnings_quality(data)
        assert 0 <= block.score <= 1.0


class TestSafety:
    def test_standard_good_safety(self):
        data = {
            "net_debt": _make_3p(500, 400, 300),
            "debt_to_ebitda": _make_3p(3.0, 2.5, 2.0),
            "ebit": _make_3p(100, 110, 120),
            "financial_result": _make_3p(-20, -18, -15),
            "cash_and_equivalents": _make_3p(200, 250, 300),
            "short_term_debt": _make_3p(100, 90, 80),
        }
        block = score_safety(data, "non_financial")
        assert block.score >= 0.6

    def test_bank_uses_fallback(self):
        data = {
            "equity": _make_3p(1000, 1100, 1200),
            "total_assets": _make_3p(10000, 10500, 11000),
            "roe": _make_3p(0.15, 0.16, 0.15),
        }
        block = score_safety(data, "bank")
        assert block.name == "safety"
        assert block.components.get("sector_policy") == "bank_fallback"

    def test_empty_data_returns_neutral(self):
        block = score_safety({}, "non_financial")
        assert block.score == 0.5


class TestOperatingConsistency:
    def test_all_growing(self):
        data = {
            "revenue": _make_3p(100, 120, 140),
            "ebit": _make_3p(20, 25, 30),
            "gross_margin": _make_3p(0.4, 0.42, 0.44),
            "ebit_margin": _make_3p(0.2, 0.21, 0.22),
            "roic": _make_3p(0.15, 0.16, 0.17),
        }
        block = score_operating_consistency(data)
        assert block.score >= 0.7


class TestCapitalDiscipline:
    def test_improving_wc(self):
        data = {
            "current_assets": _make_3p(300, 320, 350),
            "current_liabilities": _make_3p(200, 200, 200),
            "revenue": _make_3p(1000, 1100, 1200),
            "cash_from_investing": _make_3p(-80, -70, -60),
        }
        block = score_capital_discipline(data)
        assert block.score >= 0.5

    def test_no_data_returns_neutral(self):
        block = score_capital_discipline({})
        assert block.score == 0.5
