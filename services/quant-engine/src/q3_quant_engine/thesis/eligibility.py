"""Plan 2 base eligibility gate."""

from __future__ import annotations

from q3_quant_engine.thesis.config import (
    ELIGIBILITY_MAX_DEBT_TO_EBITDA,
    ELIGIBILITY_MIN_INTEREST_COVERAGE,
)
from q3_quant_engine.thesis.types import BaseEligibility


def check_base_eligibility(
    passed_core_screening: bool,
    has_valid_financials: bool,
    interest_coverage: float | None,
    debt_to_ebitda: float | None,
) -> BaseEligibility:
    """Check if an asset is eligible for Plan 2 thesis ranking.

    Canonical signature — 4 params, returns BaseEligibility with failed_reasons.
    Does NOT depend on refiner scores.
    """
    reasons: list[str] = []

    if not passed_core_screening:
        reasons.append("failed_core_screening")
    if not has_valid_financials:
        reasons.append("missing_valid_financials")
    if interest_coverage is None or interest_coverage < ELIGIBILITY_MIN_INTEREST_COVERAGE:
        reasons.append("interest_coverage_below_1.5")
    if debt_to_ebitda is None or debt_to_ebitda > ELIGIBILITY_MAX_DEBT_TO_EBITDA:
        reasons.append("debt_to_ebitda_above_6.0")

    return BaseEligibility(
        eligible_for_plan2=len(reasons) == 0,
        failed_reasons=reasons,
        passed_core_screening=passed_core_screening,
        has_valid_financials=has_valid_financials,
        interest_coverage=interest_coverage,
        debt_to_ebitda=debt_to_ebitda,
    )
