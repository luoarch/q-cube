"""Unit tests for refiner flag detection."""

from datetime import date

from q3_quant_engine.refiner.flags import detect_flags
from q3_quant_engine.refiner.types import PeriodValue


def _make_3p(v1: float | None, v2: float | None, v3: float | None) -> list[PeriodValue]:
    return [
        PeriodValue(date(2022, 12, 31), v1),
        PeriodValue(date(2023, 12, 31), v2),
        PeriodValue(date(2024, 12, 31), v3),
    ]


class TestRedFlags:
    def test_earnings_cfo_divergence(self):
        data = {
            "net_income": _make_3p(50, 60, 70),
            "cash_from_operations": _make_3p(40, 30, -10),
        }
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "earnings_cfo_divergence" in codes

    def test_ebit_deterioration(self):
        data = {"ebit": _make_3p(100, 80, 60)}
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "ebit_deterioration" in codes

    def test_margin_compression(self):
        data = {"gross_margin": _make_3p(0.40, 0.35, 0.30)}
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "margin_compression" in codes

    def test_leverage_rising(self):
        data = {"net_debt": _make_3p(100, 200, 300)}
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "leverage_rising" in codes

    def test_leverage_not_flagged_for_banks(self):
        data = {"net_debt": _make_3p(100, 200, 300)}
        flags = detect_flags(data, "bank")
        codes = [f.code for f in flags]
        assert "leverage_rising" not in codes

    def test_debt_ebitda_worsening(self):
        data = {"debt_to_ebitda": _make_3p(2.5, 3.0, 3.5)}
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "debt_ebitda_worsening" in codes

    def test_weak_interest_coverage(self):
        data = {
            "ebit": _make_3p(10, 10, 10),
            "financial_result": _make_3p(-10, -10, -10),
        }
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "weak_interest_coverage" in codes

    def test_negative_fcf_recurring(self):
        data = {
            "cash_from_operations": _make_3p(50, 40, 30),
            "cash_from_investing": _make_3p(-80, -70, -60),
        }
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "negative_fcf_recurring" in codes


class TestStrengthFlags:
    def test_ebit_growing(self):
        data = {"ebit": _make_3p(80, 90, 100)}
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "ebit_growing" in codes

    def test_deleveraging(self):
        data = {"net_debt": _make_3p(300, 250, 200)}
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "deleveraging" in codes

    def test_strong_cash_conversion(self):
        data = {"cash_conversion": _make_3p(0.9, 1.0, 1.2)}
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "strong_cash_conversion" in codes

    def test_consistent_fcf(self):
        data = {
            "cash_from_operations": _make_3p(100, 110, 120),
            "cash_from_investing": _make_3p(-50, -45, -40),
        }
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "consistent_fcf" in codes

    def test_strong_operating_consistency(self):
        data = {
            "revenue": _make_3p(100, 120, 140),
            "ebit": _make_3p(20, 25, 30),
        }
        flags = detect_flags(data, "non_financial")
        codes = [f.code for f in flags]
        assert "strong_operating_consistency" in codes


class TestNoFlags:
    def test_empty_data(self):
        flags = detect_flags({}, "non_financial")
        assert flags == []
