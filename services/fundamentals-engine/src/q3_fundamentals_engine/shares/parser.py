"""Parse CVM composicao_capital CSV rows into ShareCountRow objects.

Extracted from compute_nby_proxy_free.py. Pure function — no DB access, no downloads.
Owner: fundamentals-engine (Plan 5 §6.3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ShareCountRow:
    """One parsed row from CVM composicao_capital CSV."""

    cnpj: str  # normalized (digits only)
    reference_date: date
    document_type: str  # 'DFP' or 'ITR'
    total_shares: int
    treasury_shares: int
    net_shares: int
    publication_date_estimated: date
    source_file: str


def _normalize_cnpj(cnpj: str) -> str:
    """Strip non-digit chars from CNPJ."""
    return re.sub(r"[^0-9]", "", cnpj)


def _estimate_publication_date(reference_date: date, document_type: str) -> date:
    """Estimate publication date from CVM regulatory deadlines.

    DFP: reference_date + 90 days (3 months after fiscal year end).
    ITR: reference_date + 45 days.
    """
    if document_type == "DFP":
        return reference_date + timedelta(days=90)
    return reference_date + timedelta(days=45)


def parse_composicao_capital(
    rows: list[dict[str, str]],
    document_type: str,
    source_file: str,
) -> list[ShareCountRow]:
    """Parse composicao_capital CSV rows into ShareCountRow list.

    Args:
        rows: CSV DictReader rows from CVM composicao_capital file.
        document_type: 'DFP' or 'ITR'.
        source_file: Provenance string (e.g. 'CVM_DFP_2024_composicao_capital').

    Returns:
        List of parsed ShareCountRow. Rows with total_shares <= 0 are skipped.
    """
    if document_type not in ("DFP", "ITR"):
        msg = f"document_type must be 'DFP' or 'ITR', got '{document_type}'"
        raise ValueError(msg)

    result: list[ShareCountRow] = []
    for row in rows:
        cnpj = _normalize_cnpj(row.get("CNPJ_CIA", ""))
        if not cnpj:
            continue

        try:
            ref_date = date.fromisoformat(row["DT_REFER"])
            total = int(row.get("QT_ACAO_TOTAL_CAP_INTEGR", "0") or "0")
            treasury = int(row.get("QT_ACAO_TOTAL_TESOURO", "0") or "0")
        except (ValueError, KeyError):
            continue

        if total <= 0:
            continue

        net = total - treasury
        pub_date = _estimate_publication_date(ref_date, document_type)

        result.append(ShareCountRow(
            cnpj=cnpj,
            reference_date=ref_date,
            document_type=document_type,
            total_shares=total,
            treasury_shares=treasury,
            net_shares=net,
            publication_date_estimated=pub_date,
            source_file=source_file,
        ))

    return result
