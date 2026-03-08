"""Tests for refiner behavior with missing/partial data."""

from datetime import date

from q3_quant_engine.refiner.classification import classify_issuer
from q3_quant_engine.refiner.completeness import assess_completeness
from q3_quant_engine.refiner.scoring import (
    score_capital_discipline,
    score_earnings_quality,
    score_operating_consistency,
    score_safety,
)
from q3_quant_engine.refiner.types import PeriodValue


def _make_1p(v: float | None) -> list[PeriodValue]:
    return [PeriodValue(date(2024, 12, 31), v)]


def _make_2p(v1: float | None, v2: float | None) -> list[PeriodValue]:
    return [
        PeriodValue(date(2023, 12, 31), v1),
        PeriodValue(date(2024, 12, 31), v2),
    ]


class TestClassification:
    def test_non_financial(self):
        assert classify_issuer("Bens Industriais", "Máquinas e Equipamentos") == "non_financial"

    def test_bank(self):
        assert classify_issuer("Financeiro", "Bancos") == "bank"

    def test_insurer(self):
        assert classify_issuer("Financeiro", "Previdência e Seguros") == "insurer"

    def test_utility(self):
        assert classify_issuer("Utilidade Pública", "Energia Elétrica") == "utility"

    def test_holding(self):
        assert classify_issuer("Financeiro", "Holdings") == "holding"

    def test_none_sector(self):
        assert classify_issuer(None, None) == "non_financial"


class TestCompleteness:
    def test_full_data_high_reliability(self):
        data = {k: [1.0, 2.0, 3.0] for k in [
            "revenue", "ebit", "net_income", "ebitda", "gross_profit",
            "cash_from_operations", "cash_from_investing",
            "net_debt", "current_assets", "current_liabilities",
            "total_assets", "equity", "short_term_debt",
            "gross_margin", "ebit_margin", "net_margin",
            "roic", "debt_to_ebitda", "cash_conversion",
        ]}
        completeness, reliability = assess_completeness(data, 3, "non_financial")
        assert reliability == "high"
        assert completeness.completeness_ratio == 1.0
        assert completeness.missing_critical == []

    def test_no_data_unavailable(self):
        completeness, reliability = assess_completeness({}, 0, "non_financial")
        assert reliability == "unavailable"

    def test_one_period_low(self):
        data = {"revenue": [100.0], "ebit": [20.0], "net_income": [15.0], "cash_from_operations": [25.0]}
        completeness, reliability = assess_completeness(data, 1, "non_financial")
        assert reliability == "low"

    def test_missing_critical_lowers_reliability(self):
        data = {k: [1.0, 2.0, 3.0] for k in [
            "gross_profit", "current_assets", "current_liabilities",
            "total_assets", "equity", "short_term_debt",
            "gross_margin", "ebit_margin", "net_margin",
            "roic", "debt_to_ebitda", "cash_conversion",
        ]}
        # Missing: revenue, ebit, net_income, cash_from_operations (all critical)
        completeness, reliability = assess_completeness(data, 3, "non_financial")
        assert reliability == "low"
        assert "revenue" in completeness.missing_critical

    def test_bank_expected_metrics_smaller(self):
        data = {
            "revenue": [1.0], "net_income": [1.0], "equity": [1.0],
            "total_assets": [1.0], "roe": [1.0], "net_margin": [1.0],
        }
        completeness, reliability = assess_completeness(data, 3, "bank")
        assert completeness.completeness_ratio == 1.0


class TestScoringWithLimitedData:
    def test_single_period_scores_neutral_for_trends(self):
        data = {
            "cash_conversion": _make_1p(0.9),
            "cash_from_operations": _make_1p(100),
            "net_income": _make_1p(80),
        }
        block = score_earnings_quality(data)
        # Trends can't be computed with 1 period, should get neutral-ish score
        assert 0 <= block.score <= 1.0

    def test_two_period_computes_trends(self):
        data = {
            "revenue": _make_2p(100, 120),
            "ebit": _make_2p(20, 25),
        }
        block = score_operating_consistency(data)
        assert block.score > 0.5  # improving trend

    def test_all_none_values(self):
        data = {
            "revenue": [PeriodValue(date(2024, 12, 31), None)],
            "ebit": [PeriodValue(date(2024, 12, 31), None)],
        }
        block = score_operating_consistency(data)
        assert block.score == 0.5  # neutral

    def test_safety_empty_for_non_financial(self):
        block = score_safety({}, "non_financial")
        assert block.score == 0.5

    def test_safety_empty_for_bank(self):
        block = score_safety({}, "bank")
        assert block.score == 0.5
