"""Tests for Plan 2 base eligibility gate."""

from __future__ import annotations

import pytest

from q3_quant_engine.thesis.eligibility import check_base_eligibility


class TestCheckBaseEligibility:
    """Tests for check_base_eligibility canonical function."""

    def test_eligible_all_checks_pass(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=2.0,
        )
        assert result.eligible_for_plan2 is True
        assert result.failed_reasons == []
        assert result.passed_core_screening is True
        assert result.has_valid_financials is True
        assert result.interest_coverage == 5.0
        assert result.debt_to_ebitda == 2.0

    def test_ineligible_failed_core_screening(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=False,
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=2.0,
        )
        assert result.eligible_for_plan2 is False
        assert "failed_core_screening" in result.failed_reasons

    def test_ineligible_missing_valid_financials(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=False,
            interest_coverage=5.0,
            debt_to_ebitda=2.0,
        )
        assert result.eligible_for_plan2 is False
        assert "missing_valid_financials" in result.failed_reasons

    def test_ineligible_low_interest_coverage(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=1.0,
            debt_to_ebitda=2.0,
        )
        assert result.eligible_for_plan2 is False
        assert "interest_coverage_below_1.5" in result.failed_reasons

    def test_ineligible_none_interest_coverage(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=None,
            debt_to_ebitda=2.0,
        )
        assert result.eligible_for_plan2 is False
        assert "interest_coverage_below_1.5" in result.failed_reasons

    def test_ineligible_high_debt_to_ebitda(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=7.0,
        )
        assert result.eligible_for_plan2 is False
        assert "debt_to_ebitda_above_6.0" in result.failed_reasons

    def test_ineligible_none_debt_to_ebitda(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=None,
        )
        assert result.eligible_for_plan2 is False
        assert "debt_to_ebitda_above_6.0" in result.failed_reasons

    def test_boundary_interest_coverage_exactly_1_5(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=1.5,
            debt_to_ebitda=2.0,
        )
        assert result.eligible_for_plan2 is True
        assert result.failed_reasons == []

    def test_boundary_interest_coverage_1_49(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=1.49,
            debt_to_ebitda=2.0,
        )
        assert result.eligible_for_plan2 is False
        assert "interest_coverage_below_1.5" in result.failed_reasons

    def test_boundary_debt_to_ebitda_exactly_6(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=6.0,
        )
        assert result.eligible_for_plan2 is True
        assert result.failed_reasons == []

    def test_boundary_debt_to_ebitda_6_01(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=6.01,
        )
        assert result.eligible_for_plan2 is False
        assert "debt_to_ebitda_above_6.0" in result.failed_reasons

    def test_multiple_failures(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=False,
            has_valid_financials=True,
            interest_coverage=0.5,
            debt_to_ebitda=2.0,
        )
        assert result.eligible_for_plan2 is False
        assert "failed_core_screening" in result.failed_reasons
        assert "interest_coverage_below_1.5" in result.failed_reasons
        assert len(result.failed_reasons) == 2

    def test_all_failures(self) -> None:
        result = check_base_eligibility(
            passed_core_screening=False,
            has_valid_financials=False,
            interest_coverage=0.5,
            debt_to_ebitda=10.0,
        )
        assert result.eligible_for_plan2 is False
        assert len(result.failed_reasons) == 4
        assert "failed_core_screening" in result.failed_reasons
        assert "missing_valid_financials" in result.failed_reasons
        assert "interest_coverage_below_1.5" in result.failed_reasons
        assert "debt_to_ebitda_above_6.0" in result.failed_reasons
