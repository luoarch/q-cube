from __future__ import annotations

from q3_shared_models.entities import CanonicalKey


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
    def map(cls, cvm_code: str) -> CanonicalKey | None:
        """Return the canonical key for a CVM CD_CONTA code, or None if unmapped."""
        return cls.CVM_TO_CANONICAL.get(cvm_code)
