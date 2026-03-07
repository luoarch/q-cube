"""ITR (Informacoes Trimestrais) parser — quarterly financial statements."""

from __future__ import annotations

import logging

from q3_fundamentals_engine.parsers.base import BaseFilingParser
from q3_fundamentals_engine.parsers.models import ParsedRow

logger = logging.getLogger(__name__)

# Same statement types as DFP — ITR uses the same layout with different filenames
_STATEMENT_TYPES = ["DRE", "BPA", "BPP", "DFC_MD", "DFC_MI", "DMPL", "DVA"]
_SCOPES = ["con", "ind"]


class ItrParser(BaseFilingParser):
    """Parser for quarterly ITR ZIPs from CVM.

    ITR ZIPs contain CSVs named like:
        itr_cia_aberta_DRE_con_2024.csv
        itr_cia_aberta_BPA_ind_2024.csv
        etc.

    Layout is identical to DFP — same columns, same structure.
    """

    def _extract_rows(self, csvs: dict[str, list[dict[str, str]]]) -> list[ParsedRow]:
        """Extract ParsedRow instances from all ITR statement CSVs."""
        rows: list[ParsedRow] = []

        for statement_type in _STATEMENT_TYPES:
            for scope in _SCOPES:
                target_pattern = f"_{statement_type}_{scope}_"
                matching_csvs = [
                    (name, csv_rows)
                    for name, csv_rows in csvs.items()
                    if target_pattern.lower() in name.lower()
                ]

                for csv_name, csv_rows in matching_csvs:
                    logger.debug(
                        "parsing ITR %s/%s from %s (%d rows)",
                        statement_type,
                        scope,
                        csv_name,
                        len(csv_rows),
                    )
                    for raw_row in csv_rows:
                        value = self._normalize_value(raw_row)
                        parsed = ParsedRow(
                            cd_cvm=raw_row.get("CD_CVM", "").strip(),
                            cnpj=raw_row.get("CNPJ_CIA", "").strip(),
                            company_name=raw_row.get("DENOM_CIA", "").strip(),
                            ref_date=raw_row.get("DT_REFER", "").strip(),
                            account_code=raw_row.get("CD_CONTA", "").strip(),
                            account_description=raw_row.get("DS_CONTA", "").strip(),
                            value=value,
                            scale=raw_row.get("ESCALA_MOEDA", "").strip(),
                            period_order=raw_row.get("ORDEM_EXERC", "").strip(),
                            version=self._parse_version(raw_row),
                            statement_type=statement_type,
                            scope=scope,
                            doc_type="ITR",
                        )
                        rows.append(parsed)

        logger.info("ITR parser extracted %d total rows", len(rows))
        return rows
