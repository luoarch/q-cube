from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Keys to cross-check between CVM and vendor data.
_RECONCILE_KEYS = [
    "revenue",
    "net_income",
    "ebit",
    "total_assets",
    "total_equity",
    "cash_and_equivalents",
]

# Tolerance for considering values "matching" (1% relative difference).
_DEFAULT_TOLERANCE = 0.01


class CrossSourceReconciler:
    """Cross-checks CVM data against vendor-provided data when available."""

    def __init__(self, tolerance: float = _DEFAULT_TOLERANCE) -> None:
        self._tolerance = tolerance

    def reconcile(
        self,
        issuer_id: uuid.UUID,
        cvm_values: dict[str, float | None],
        vendor_values: dict[str, float | None] | None,
    ) -> dict[str, Any]:
        """Cross-check CVM data vs vendor data.

        Returns a reconciliation report with:
        - status: "ok" | "mismatches_found" | "vendor_data_unavailable"
        - checks: per-key comparison results
        - summary: counts of matched, mismatched, and skipped keys
        """
        if vendor_values is None:
            logger.debug("No vendor data available for issuer=%s; skipping reconciliation", issuer_id)
            return {
                "status": "vendor_data_unavailable",
                "issuer_id": str(issuer_id),
                "checks": {},
                "summary": {"matched": 0, "mismatched": 0, "skipped": len(_RECONCILE_KEYS)},
            }

        checks: dict[str, Any] = {}
        matched = 0
        mismatched = 0
        skipped = 0

        for key in _RECONCILE_KEYS:
            cvm_val = cvm_values.get(key)
            vendor_val = vendor_values.get(key)

            if cvm_val is None or vendor_val is None:
                checks[key] = {
                    "status": "skipped",
                    "reason": "missing_value",
                    "cvm": cvm_val,
                    "vendor": vendor_val,
                }
                skipped += 1
                continue

            diff = abs(cvm_val - vendor_val)
            denominator = max(abs(cvm_val), abs(vendor_val), 1.0)
            relative_diff = diff / denominator

            if relative_diff <= self._tolerance:
                checks[key] = {
                    "status": "matched",
                    "cvm": cvm_val,
                    "vendor": vendor_val,
                    "relative_diff": relative_diff,
                }
                matched += 1
            else:
                checks[key] = {
                    "status": "mismatched",
                    "cvm": cvm_val,
                    "vendor": vendor_val,
                    "diff": diff,
                    "relative_diff": relative_diff,
                    "tolerance": self._tolerance,
                }
                mismatched += 1

        status = "ok" if mismatched == 0 else "mismatches_found"

        if mismatched > 0:
            logger.warning(
                "Reconciliation for issuer=%s found %d mismatches: %s",
                issuer_id,
                mismatched,
                [k for k, v in checks.items() if v.get("status") == "mismatched"],
            )

        return {
            "status": status,
            "issuer_id": str(issuer_id),
            "checks": checks,
            "summary": {"matched": matched, "mismatched": mismatched, "skipped": skipped},
        }
