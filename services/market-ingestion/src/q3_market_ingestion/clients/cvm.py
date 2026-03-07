"""CVM Portal Dados Abertos client — source of truth for regulatory filings.

Downloads bulk ZIP files from https://dados.cvm.gov.br containing
DFP (annual) and ITR (quarterly) financial statements as CSVs.

CSV schema (common to all statement types):
  CD_CVM        — company CVM code (char 6)
  CNPJ_CIA      — company CNPJ
  DENOM_CIA     — company legal name
  DT_REFER      — reference date (YYYY-MM-DD)
  DT_FIM_EXERC  — fiscal year end date
  VERSAO        — document version
  CD_CONTA      — account code (e.g. "3.05" for EBIT)
  DS_CONTA      — account description
  VL_CONTA      — account value (decimal)
  ESCALA_MOEDA  — "MIL" or "UNIDADE"
  ORDEM_EXERC   — "ÚLTIMO" or "PENÚLTIMO"
  ST_CONTA_FIXA — "S" or "N" (standardized account)

Key accounts for Magic Formula:
  DRE  3.05     — EBIT (Resultado Antes do Resultado Financeiro)
  DRE  3.01     — Receita Líquida
  DRE  3.03     — Resultado Bruto
  BPA  1.01     — Ativo Circulante (current assets)
  BPA  1.02.03  — Imobilizado (fixed assets / PP&E)
  BPP  2.01     — Passivo Circulante (current liabilities)
  BPP  2.03     — Patrimônio Líquido (equity)
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from q3_market_ingestion.config import CVM_BASE_URL, CVM_CADASTRO_URL

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(120.0, connect=30.0)

DFP_URL = f"{CVM_BASE_URL}/DFP/DADOS/dfp_cia_aberta_{{year}}.zip"
ITR_URL = f"{CVM_BASE_URL}/ITR/DADOS/itr_cia_aberta_{{year}}.zip"
FCA_URL = f"{CVM_BASE_URL}/FCA/DADOS/fca_cia_aberta_{{year}}.zip"

# CVM account codes relevant for Magic Formula
ACCOUNT_EBIT = "3.05"           # EBIT (Resultado Antes do Resultado Financeiro)
ACCOUNT_REVENUE = "3.01"        # Receita Líquida
ACCOUNT_GROSS_PROFIT = "3.03"   # Resultado Bruto
ACCOUNT_CURRENT_ASSETS = "1.01"     # Ativo Circulante
ACCOUNT_FIXED_ASSETS = "1.02.03"    # Imobilizado (PP&E)
ACCOUNT_CURRENT_LIABILITIES = "2.01"  # Passivo Circulante
ACCOUNT_EQUITY = "2.03"            # Patrimônio Líquido
ACCOUNT_TOTAL_ASSETS = "1"         # Ativo Total


async def download_zip(url: str) -> bytes:
    """Download a ZIP file from CVM."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def extract_csvs(zip_bytes: bytes) -> dict[str, list[dict[str, str]]]:
    """Extract all CSVs from a CVM ZIP file into parsed rows.

    Returns a dict keyed by filename (e.g. "dfp_cia_aberta_DRE_con_2024.csv")
    with each value being a list of dicts (one per row).
    """
    result: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            with zf.open(name) as f:
                text = io.TextIOWrapper(f, encoding="latin-1")
                reader = csv.DictReader(text, delimiter=";")
                result[name] = list(reader)
    return result


def filter_latest_version(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep only the latest version of each (CD_CVM, DT_REFER, ORDEM_EXERC, CD_CONTA) combo."""
    best: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["CD_CVM"], row["DT_REFER"], row.get("ORDEM_EXERC", ""), row["CD_CONTA"])
        version = int(row.get("VERSAO", "1"))
        existing = best.get(key)
        if existing is None or version > int(existing.get("VERSAO", "1")):
            best[key] = row
    return list(best.values())


def normalize_value(row: dict[str, str]) -> float | None:
    """Convert VL_CONTA to a float in full units (not thousands)."""
    raw = row.get("VL_CONTA", "").strip()
    if not raw:
        return None
    value = float(raw.replace(",", "."))
    scale = row.get("ESCALA_MOEDA", "").strip().upper()
    if scale == "MIL":
        value *= 1000
    return value


def parse_statements(
    csvs: dict[str, list[dict[str, str]]],
    *,
    statement_type: str = "DRE",
    consolidated: bool = True,
) -> list[dict[str, Any]]:
    """Parse specific statement CSVs, filtering to latest version only.

    Args:
        csvs: Output from extract_csvs.
        statement_type: One of DRE, BPA, BPP, DFC_MD, DFC_MI, DMPL, DVA.
        consolidated: If True, use "con" files; otherwise "ind".
    """
    con_ind = "con" if consolidated else "ind"
    target_prefix = f"_{statement_type}_{con_ind}_"

    all_rows: list[dict[str, str]] = []
    for name, rows in csvs.items():
        if target_prefix in name:
            all_rows.extend(rows)

    if not all_rows:
        return []

    filtered = filter_latest_version(all_rows)

    return [
        {
            "cd_cvm": row["CD_CVM"].strip(),
            "cnpj": row.get("CNPJ_CIA", "").strip(),
            "company_name": row.get("DENOM_CIA", "").strip(),
            "reference_date": row["DT_REFER"].strip(),
            "fiscal_year_end": row.get("DT_FIM_EXERC", "").strip(),
            "account_code": row["CD_CONTA"].strip(),
            "account_description": row.get("DS_CONTA", "").strip(),
            "value": normalize_value(row),
            "scale": row.get("ESCALA_MOEDA", "").strip(),
            "period_order": row.get("ORDEM_EXERC", "").strip(),
            "is_fixed_account": row.get("ST_CONTA_FIXA", "") == "S",
            "version": int(row.get("VERSAO", "1")),
        }
        for row in filtered
    ]


async def download_dfp(year: int) -> dict[str, list[dict[str, str]]]:
    """Download and extract DFP (annual) data for a given year."""
    url = DFP_URL.format(year=year)
    logger.info("downloading DFP year=%d url=%s", year, url)
    zip_bytes = await download_zip(url)
    return extract_csvs(zip_bytes)


async def download_itr(year: int) -> dict[str, list[dict[str, str]]]:
    """Download and extract ITR (quarterly) data for a given year."""
    url = ITR_URL.format(year=year)
    logger.info("downloading ITR year=%d url=%s", year, url)
    zip_bytes = await download_zip(url)
    return extract_csvs(zip_bytes)


def save_raw(csvs: dict[str, list[dict[str, str]]], output_dir: Path) -> list[Path]:
    """Persist raw CSV data to disk for audit trail."""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for name, rows in csvs.items():
        if not rows:
            continue
        path = output_dir / name
        fieldnames = list(rows[0].keys())
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        saved.append(path)
    return saved


# ---------------------------------------------------------------------------
# CVM cadastro + FCA — company registry and ticker mapping
# ---------------------------------------------------------------------------

async def download_cadastro() -> list[dict[str, str]]:
    """Download CVM company cadastro (cad_cia_aberta.csv).

    Returns list of dicts with keys: CD_CVM, DENOM_CIA, CNPJ_CIA, SIT_REG, etc.
    Useful for getting active company list.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(CVM_CADASTRO_URL)
        resp.raise_for_status()
        text = resp.content.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        return list(reader)


async def download_fca(year: int) -> dict[str, list[dict[str, str]]]:
    """Download FCA (Formulário Cadastral Ativo) data for a year.

    Contains ticker mapping in fca_cia_aberta_valor_mobiliario_{year}.csv.
    """
    url = FCA_URL.format(year=year)
    logger.info("downloading FCA year=%d url=%s", year, url)
    zip_bytes = await download_zip(url)
    return extract_csvs(zip_bytes)


def extract_ticker_mapping(fca_csvs: dict[str, list[dict[str, str]]]) -> dict[str, list[str]]:
    """Build CNPJ → list of tickers mapping from FCA valor_mobiliario CSV.

    FCA uses CNPJ_Companhia (not CD_CVM). The returned dict is keyed by
    normalized CNPJ (digits only) for cross-referencing with DFP/ITR data.

    Returns dict: {"33000167000101": ["PETR3", "PETR4"], ...}
    """
    mapping: dict[str, list[str]] = {}
    for name, rows in fca_csvs.items():
        if "valor_mobiliario" not in name.lower():
            continue
        for row in rows:
            cnpj_raw = row.get("CNPJ_Companhia", "").strip()
            ticker = row.get("Codigo_Negociacao", "").strip()
            if not cnpj_raw or not ticker:
                continue
            # Only keep actively traded tickers (no Data_Fim_Negociacao)
            if row.get("Data_Fim_Negociacao", "").strip():
                continue
            # Filter to common stock tickers (ON=3, PN=4, UNT=11)
            if not any(ticker.endswith(suffix) for suffix in ("3", "4", "11")):
                continue
            # Normalize CNPJ: keep digits only
            cnpj = "".join(c for c in cnpj_raw if c.isdigit())
            mapping.setdefault(cnpj, [])
            if ticker not in mapping[cnpj]:
                mapping[cnpj].append(ticker)
    return mapping


# ---------------------------------------------------------------------------
# Fundamentals extraction — build structured data from parsed CVM statements
# ---------------------------------------------------------------------------

@dataclass
class CompanyFundamentals:
    """Consolidated fundamentals for one company from CVM data."""
    cd_cvm: str
    company_name: str
    cnpj: str
    reference_date: str  # YYYY-MM-DD
    ebit: Decimal | None = None
    revenue: Decimal | None = None
    gross_profit: Decimal | None = None
    current_assets: Decimal | None = None
    fixed_assets: Decimal | None = None
    current_liabilities: Decimal | None = None
    equity: Decimal | None = None
    total_assets: Decimal | None = None
    tickers: list[str] = field(default_factory=list)

    @property
    def net_working_capital(self) -> Decimal | None:
        if self.current_assets is not None and self.current_liabilities is not None:
            return self.current_assets - self.current_liabilities
        return None

    @property
    def gross_margin(self) -> Decimal | None:
        if self.gross_profit is not None and self.revenue and self.revenue != 0:
            return self.gross_profit / self.revenue
        return None

    @property
    def ebit_margin(self) -> Decimal | None:
        if self.ebit is not None and self.revenue and self.revenue != 0:
            return self.ebit / self.revenue
        return None

    @property
    def roic(self) -> Decimal | None:
        """ROIC = EBIT / (NWC + Fixed Assets). Proxy used by Magic Formula."""
        nwc = self.net_working_capital
        if self.ebit is not None and nwc is not None and self.fixed_assets is not None:
            capital = nwc + self.fixed_assets
            if capital != 0:
                return self.ebit / capital
        return None

    @property
    def roe(self) -> Decimal | None:
        if self.ebit is not None and self.equity and self.equity != 0:
            return self.ebit / self.equity
        return None


def build_fundamentals(
    dre_rows: list[dict[str, Any]],
    bpa_rows: list[dict[str, Any]],
    bpp_rows: list[dict[str, Any]],
    *,
    ticker_mapping: dict[str, list[str]] | None = None,
    period_order: str = "ÚLTIMO",
) -> list[CompanyFundamentals]:
    """Build CompanyFundamentals from parsed CVM DRE/BPA/BPP data.

    Only keeps rows with ORDEM_EXERC = period_order (default: "ÚLTIMO").
    Groups by (cd_cvm, reference_date) and extracts key accounts.
    """
    # Index all rows by (cd_cvm, reference_date, account_code)
    account_map: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    company_info: dict[str, tuple[str, str]] = {}  # cd_cvm → (company_name, cnpj)

    for row in [*dre_rows, *bpa_rows, *bpp_rows]:
        if row["period_order"] != period_order:
            continue
        cd_cvm = row["cd_cvm"]
        ref_date = row["reference_date"]
        key = (cd_cvm, ref_date)
        account_map.setdefault(key, {})[row["account_code"]] = row
        if cd_cvm not in company_info:
            company_info[cd_cvm] = (row["company_name"], row["cnpj"])

    results: list[CompanyFundamentals] = []
    for (cd_cvm, ref_date), accounts in account_map.items():
        name, cnpj = company_info.get(cd_cvm, ("", ""))
        fund = CompanyFundamentals(
            cd_cvm=cd_cvm,
            company_name=name,
            cnpj=cnpj,
            reference_date=ref_date,
        )
        if ACCOUNT_EBIT in accounts and accounts[ACCOUNT_EBIT]["value"] is not None:
            fund.ebit = Decimal(str(accounts[ACCOUNT_EBIT]["value"]))
        if ACCOUNT_REVENUE in accounts and accounts[ACCOUNT_REVENUE]["value"] is not None:
            fund.revenue = Decimal(str(accounts[ACCOUNT_REVENUE]["value"]))
        if ACCOUNT_GROSS_PROFIT in accounts and accounts[ACCOUNT_GROSS_PROFIT]["value"] is not None:
            fund.gross_profit = Decimal(str(accounts[ACCOUNT_GROSS_PROFIT]["value"]))
        if ACCOUNT_CURRENT_ASSETS in accounts and accounts[ACCOUNT_CURRENT_ASSETS]["value"] is not None:
            fund.current_assets = Decimal(str(accounts[ACCOUNT_CURRENT_ASSETS]["value"]))
        if ACCOUNT_FIXED_ASSETS in accounts and accounts[ACCOUNT_FIXED_ASSETS]["value"] is not None:
            fund.fixed_assets = Decimal(str(accounts[ACCOUNT_FIXED_ASSETS]["value"]))
        if ACCOUNT_CURRENT_LIABILITIES in accounts and accounts[ACCOUNT_CURRENT_LIABILITIES]["value"] is not None:
            fund.current_liabilities = Decimal(str(accounts[ACCOUNT_CURRENT_LIABILITIES]["value"]))
        if ACCOUNT_EQUITY in accounts and accounts[ACCOUNT_EQUITY]["value"] is not None:
            fund.equity = Decimal(str(accounts[ACCOUNT_EQUITY]["value"]))
        if ACCOUNT_TOTAL_ASSETS in accounts and accounts[ACCOUNT_TOTAL_ASSETS]["value"] is not None:
            fund.total_assets = Decimal(str(accounts[ACCOUNT_TOTAL_ASSETS]["value"]))

        if ticker_mapping:
            # Normalize CNPJ for lookup (FCA uses CNPJ, DFP uses CNPJ_CIA)
            cnpj_normalized = "".join(c for c in cnpj if c.isdigit())
            fund.tickers = ticker_mapping.get(cnpj_normalized, [])

        results.append(fund)

    return results
