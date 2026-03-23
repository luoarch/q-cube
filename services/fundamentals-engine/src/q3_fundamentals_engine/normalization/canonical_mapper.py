from __future__ import annotations

import logging
import re

from q3_shared_models.entities import CanonicalKey

logger = logging.getLogger(__name__)


# Label patterns that indicate shareholder distributions (dividends + JCP).
# Applied to DFC sub-accounts (6.03.XX) via case-insensitive matching.
_DISTRIBUTION_INCLUDE: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"dividend",
        r"\bjcp\b",
        r"juros sobre (?:o )?capital",
        r"jscp",
        r"proventos\s+pagos",
        r"distribui[çc][ãa]o\s+de\s+lucr",
        r"distribui[çc][ãa]o\s+de\s+dividend",
        r"remunera[çc][ãa]o\s+a(?:os?)?\s+acionista",
    ]
]

# Labels that look like distributions but are NOT outflows to shareholders.
# "Recebidos" = dividends received (income, not distribution).
_DISTRIBUTION_EXCLUDE: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"recebid",
        r"a\s+receber",
    ]
]


def _is_shareholder_distribution(label: str) -> bool:
    """Return True if the DFC label represents a shareholder distribution."""
    if any(pat.search(label) for pat in _DISTRIBUTION_EXCLUDE):
        return False
    return any(pat.search(label) for pat in _DISTRIBUTION_INCLUDE)


class CanonicalKeyMapper:
    """Maps CVM CD_CONTA codes to internal canonical keys."""

    CVM_TO_CANONICAL: dict[str, CanonicalKey] = {
        # DRE
        "3.01": CanonicalKey.revenue,
        "3.02": CanonicalKey.cost_of_goods_sold,
        "3.03": CanonicalKey.gross_profit,
        "3.04": CanonicalKey.operating_expenses,
        "3.05": CanonicalKey.ebit,
        "3.06": CanonicalKey.financial_result,
        "3.07": CanonicalKey.ebt,
        "3.08": CanonicalKey.income_tax,
        "3.11": CanonicalKey.net_income,
        # BPA
        "1": CanonicalKey.total_assets,
        "1.01": CanonicalKey.current_assets,
        "1.01.01": CanonicalKey.cash_and_equivalents,
        "1.02": CanonicalKey.non_current_assets,
        "1.02.03": CanonicalKey.fixed_assets,
        "1.02.04": CanonicalKey.intangible_assets,
        # BPP
        "2": CanonicalKey.total_liabilities,
        "2.01": CanonicalKey.current_liabilities,
        "2.01.04": CanonicalKey.short_term_debt,
        "2.02": CanonicalKey.non_current_liabilities,
        "2.02.01": CanonicalKey.long_term_debt,
        "2.03": CanonicalKey.equity,
        # DFC_MD
        "6.01": CanonicalKey.cash_from_operations,
        "6.02": CanonicalKey.cash_from_investing,
        "6.03": CanonicalKey.cash_from_financing,
    }

    @classmethod
    def map(
        cls,
        cvm_code: str,
        *,
        label: str = "",
        statement_type: str = "",
    ) -> CanonicalKey | None:
        """Return the canonical key for a CVM CD_CONTA code, or None if unmapped.

        For DFC sub-accounts (6.03.XX), uses label-based matching to identify
        shareholder distributions (dividends + JCP).
        """
        # Direct code mapping (level 1 accounts + specific codes)
        exact = cls.CVM_TO_CANONICAL.get(cvm_code)
        if exact is not None:
            return exact

        # Label-based mapping for DFC financing sub-accounts
        if (
            cvm_code.startswith("6.03.")
            and statement_type in ("DFC_MD", "DFC_MI", "")
            and label
            and _is_shareholder_distribution(label)
        ):
            return CanonicalKey.shareholder_distributions

        return None
