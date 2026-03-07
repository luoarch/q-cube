from __future__ import annotations


class CanonicalKeyMapper:
    """Maps CVM CD_CONTA codes to internal canonical keys."""

    CVM_TO_CANONICAL: dict[str, str] = {
        # DRE
        "3.01": "revenue",
        "3.02": "cost_of_goods_sold",
        "3.03": "gross_profit",
        "3.04": "operating_expenses",
        "3.05": "ebit",
        "3.06": "financial_result",
        "3.07": "ebt",
        "3.08": "income_tax",
        "3.11": "net_income",
        # BPA
        "1": "total_assets",
        "1.01": "current_assets",
        "1.01.01": "cash_and_equivalents",
        "1.02": "non_current_assets",
        "1.02.03": "fixed_assets",
        "1.02.04": "intangible_assets",
        # BPP
        "2": "total_liabilities",
        "2.01": "current_liabilities",
        "2.01.04": "short_term_debt",
        "2.02": "non_current_liabilities",
        "2.02.01": "long_term_debt",
        "2.03": "equity",
        # DFC_MD
        "6.01": "cash_from_operations",
        "6.02": "cash_from_investing",
        "6.03": "cash_from_financing",
    }

    @classmethod
    def map(cls, cvm_code: str) -> str | None:
        """Return the canonical key for a CVM CD_CONTA code, or None if unmapped."""
        return cls.CVM_TO_CANONICAL.get(cvm_code)
