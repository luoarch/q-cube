from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default tolerance for accounting identity checks (0.1% relative).
_DEFAULT_TOLERANCE = 0.001


class AccountingValidator:
    """Validates fundamental accounting identities on statement data."""

    def __init__(self, tolerance: float = _DEFAULT_TOLERANCE) -> None:
        self._tolerance = tolerance

    def validate(self, values: dict[str, float | None]) -> dict[str, Any]:
        """Run accounting identity checks.

        Checks:
        - Balance sheet: total_assets ~= total_liabilities + total_equity
        - Income statement: gross_profit ~= revenue - cost_of_goods_sold

        Returns dict mapping check_name to result dict containing:
            passed, expected, actual, tolerance, diff
        """
        results: dict[str, Any] = {}

        # --- Balance sheet identity ---
        total_assets = values.get("total_assets")
        total_liabilities = values.get("total_liabilities")
        total_equity = values.get("total_equity")

        if total_assets is not None and total_liabilities is not None and total_equity is not None:
            expected = total_liabilities + total_equity
            results["assets_eq_liabilities_plus_equity"] = self._check(
                expected=expected,
                actual=total_assets,
            )
        else:
            results["assets_eq_liabilities_plus_equity"] = {
                "passed": None,
                "reason": "missing_inputs",
                "available": {
                    "total_assets": total_assets is not None,
                    "total_liabilities": total_liabilities is not None,
                    "total_equity": total_equity is not None,
                },
            }

        # --- Gross profit identity ---
        revenue = values.get("revenue")
        cogs = values.get("cost_of_goods_sold")
        gross_profit = values.get("gross_profit")

        if revenue is not None and cogs is not None and gross_profit is not None:
            expected_gp = revenue - cogs
            results["gross_profit_eq_revenue_minus_cogs"] = self._check(
                expected=expected_gp,
                actual=gross_profit,
            )
        else:
            results["gross_profit_eq_revenue_minus_cogs"] = {
                "passed": None,
                "reason": "missing_inputs",
                "available": {
                    "revenue": revenue is not None,
                    "cost_of_goods_sold": cogs is not None,
                    "gross_profit": gross_profit is not None,
                },
            }

        return results

    def _check(self, expected: float, actual: float) -> dict[str, Any]:
        """Compare expected vs actual within tolerance."""
        diff = abs(expected - actual)
        denominator = max(abs(expected), abs(actual), 1.0)
        relative_diff = diff / denominator

        passed = relative_diff <= self._tolerance

        if not passed:
            logger.warning(
                "Accounting check failed: expected=%.2f actual=%.2f diff=%.2f rel=%.4f",
                expected,
                actual,
                diff,
                relative_diff,
            )

        return {
            "passed": passed,
            "expected": expected,
            "actual": actual,
            "diff": diff,
            "relative_diff": relative_diff,
            "tolerance": self._tolerance,
        }
