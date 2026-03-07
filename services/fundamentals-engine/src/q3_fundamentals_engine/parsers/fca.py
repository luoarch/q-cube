"""FCA (Formulario Cadastral Ativo) parser — company registration and ticker mapping."""

from __future__ import annotations

import csv
import io
import logging
import zipfile

from q3_fundamentals_engine.parsers.models import FcaCompanyInfo

logger = logging.getLogger(__name__)


class FcaParser:
    """Parser for FCA ZIPs from CVM.

    FCA ZIPs contain multiple CSVs. The key ones are:
        - fca_cia_aberta_geral_{year}.csv — general company info
        - fca_cia_aberta_valor_mobiliario_{year}.csv — ticker mapping

    Unlike DFP/ITR parsers, this returns FcaCompanyInfo instead of ParsedRow.
    """

    def run(self, zip_bytes: bytes) -> list[FcaCompanyInfo]:
        """Parse an FCA ZIP and return company info with ticker mappings."""
        csvs = self._load(zip_bytes)
        companies = self._extract_company_info(csvs)
        tickers = self._extract_ticker_mapping(csvs)
        return self._merge(companies, tickers)

    def _load(self, zip_bytes: bytes) -> dict[str, list[dict[str, str]]]:
        """Extract all CSVs from the FCA ZIP."""
        result: dict[str, list[dict[str, str]]] = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.endswith(".csv"):
                    continue
                with zf.open(name) as f:
                    text = io.TextIOWrapper(f, encoding="latin-1")
                    reader = csv.DictReader(text, delimiter=";")
                    result[name] = list(reader)
                    logger.debug("loaded %s: %d rows", name, len(result[name]))
        return result

    def _extract_company_info(
        self, csvs: dict[str, list[dict[str, str]]]
    ) -> dict[str, FcaCompanyInfo]:
        """Extract company info from the 'geral' CSV.

        Returns a dict keyed by normalized CNPJ (digits only).
        """
        companies: dict[str, FcaCompanyInfo] = {}
        for name, rows in csvs.items():
            if "geral" not in name.lower():
                continue
            for row in rows:
                cnpj_raw = row.get("CNPJ_Companhia", "").strip()
                if not cnpj_raw:
                    continue
                cnpj = "".join(c for c in cnpj_raw if c.isdigit())
                if cnpj in companies:
                    continue
                companies[cnpj] = FcaCompanyInfo(
                    cnpj=cnpj,
                    company_name=row.get("Nome_Companhia", "").strip(),
                    cvm_code=row.get("Codigo_CVM", "").strip(),
                    situation=row.get("Situacao_Registro_CVM", "").strip(),
                    category=row.get("Categoria_Registro_CVM", "").strip(),
                )
        logger.info("FCA geral: %d companies extracted", len(companies))
        return companies

    def _extract_ticker_mapping(
        self, csvs: dict[str, list[dict[str, str]]]
    ) -> dict[str, list[str]]:
        """Build CNPJ -> list of tickers from the 'valor_mobiliario' CSV.

        Migrated from market-ingestion's cvm.py extract_ticker_mapping.
        Filters to actively traded common/preferred stocks (suffixes 3, 4, 11).
        """
        mapping: dict[str, list[str]] = {}
        for name, rows in csvs.items():
            if "valor_mobiliario" not in name.lower():
                continue
            for row in rows:
                cnpj_raw = row.get("CNPJ_Companhia", "").strip()
                ticker = row.get("Codigo_Negociacao", "").strip()
                if not cnpj_raw or not ticker:
                    continue
                # Only keep actively traded tickers (no end date)
                if row.get("Data_Fim_Negociacao", "").strip():
                    continue
                # Filter to ON=3, PN=4, UNT=11
                if not any(ticker.endswith(suffix) for suffix in ("3", "4", "11")):
                    continue
                cnpj = "".join(c for c in cnpj_raw if c.isdigit())
                mapping.setdefault(cnpj, [])
                if ticker not in mapping[cnpj]:
                    mapping[cnpj].append(ticker)
        logger.info("FCA valor_mobiliario: %d companies with tickers", len(mapping))
        return mapping

    def _merge(
        self,
        companies: dict[str, FcaCompanyInfo],
        tickers: dict[str, list[str]],
    ) -> list[FcaCompanyInfo]:
        """Merge ticker mappings into company info.

        Companies without tickers are still included (they may not be listed yet
        or may only have debentures/other securities).
        """
        # Attach tickers to existing companies
        for cnpj, ticker_list in tickers.items():
            if cnpj in companies:
                companies[cnpj].tickers = ticker_list
            else:
                # Company found in valor_mobiliario but not in geral
                companies[cnpj] = FcaCompanyInfo(
                    cnpj=cnpj,
                    tickers=ticker_list,
                )

        result = list(companies.values())
        logger.info(
            "FCA merge: %d total companies, %d with tickers",
            len(result),
            sum(1 for c in result if c.tickers),
        )
        return result
