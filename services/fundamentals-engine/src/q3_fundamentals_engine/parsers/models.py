"""Data models for parsed CVM filing rows."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedRow:
    """A single parsed row from a CVM financial statement CSV.

    Values are stored in their original scale (MIL or UNIDADE) — normalization
    to full units happens downstream in the normalization layer.
    """

    cd_cvm: str
    cnpj: str
    company_name: str
    ref_date: str  # YYYY-MM-DD
    account_code: str
    account_description: str
    value: float | None
    scale: str  # MIL or UNIDADE
    period_order: str  # ULTIMO or PENULTIMO
    version: int
    statement_type: str  # DRE, BPA, BPP, DFC_MD, etc.
    scope: str  # con or ind
    doc_type: str = ""  # DFP, ITR — set by the parser that produced this row


@dataclass
class FcaCompanyInfo:
    """Parsed company registration data from an FCA filing."""

    cnpj: str
    tickers: list[str] = field(default_factory=list)
    company_name: str = ""
    cvm_code: str = ""
    situation: str = ""
    category: str = ""
