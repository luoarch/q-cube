"""Issuer classification for sector-aware refiner scoring."""

from __future__ import annotations

FINANCIAL_SECTORS = {"financeiro", "financial"}
FINANCIAL_SUBSECTORS = {
    "bancos",
    "seguradoras",
    "holdings",
    "intermediários financeiros",
    "previdência e seguros",
    "serviços financeiros diversos",
}
UTILITY_SECTORS = {"utilidade pública", "utilities"}


def classify_issuer(sector: str | None, subsector: str | None) -> str:
    s = (sector or "").strip().lower()
    sub = (subsector or "").strip().lower()

    if s in UTILITY_SECTORS:
        return "utility"

    if s in FINANCIAL_SECTORS:
        if "banco" in sub or "bancos" in sub:
            return "bank"
        if "segur" in sub or "previdência" in sub:
            return "insurer"
        if "holding" in sub:
            return "holding"
        return "bank"  # default financial to bank

    return "non_financial"
