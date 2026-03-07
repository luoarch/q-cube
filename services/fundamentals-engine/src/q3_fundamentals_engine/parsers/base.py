"""Template Method base class for CVM filing parsers."""

from __future__ import annotations

import abc
import csv
import io
import logging
import zipfile

from q3_fundamentals_engine.parsers.models import ParsedRow

logger = logging.getLogger(__name__)


class BaseFilingParser(abc.ABC):
    """Template Method parser for CVM filing ZIPs.

    Subclasses implement _extract_rows to handle statement-specific CSV layouts.
    The base class handles ZIP extraction, structural validation, and version filtering.
    """

    def run(self, zip_bytes: bytes) -> list[ParsedRow]:
        """Parse a CVM ZIP file and return deduplicated rows.

        Steps:
            1. Load (extract CSVs from ZIP)
            2. Validate structure (check required columns)
            3. Extract rows (statement-specific logic)
            4. Filter versions (keep latest version per key)
        """
        csvs = self._load(zip_bytes)
        self._validate_structure(csvs)
        rows = self._extract_rows(csvs)
        return self._filter_versions(rows)

    def _load(self, zip_bytes: bytes) -> dict[str, list[dict[str, str]]]:
        """Extract all CSVs from a CVM ZIP file into parsed rows.

        Returns a dict keyed by filename with each value being a list of
        row dicts (one per CSV row).
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
                    logger.debug("loaded %s: %d rows", name, len(result[name]))
        return result

    def _validate_structure(self, csvs: dict[str, list[dict[str, str]]]) -> None:
        """Check that required columns exist in the CSVs.

        Logs warnings for CSVs missing expected columns but does not raise —
        downstream _extract_rows can handle missing data gracefully.
        """
        required_columns = {
            "CD_CVM", "CNPJ_CIA", "DENOM_CIA", "DT_REFER",
            "CD_CONTA", "DS_CONTA", "VL_CONTA", "VERSAO",
        }
        for name, rows in csvs.items():
            if not rows:
                continue
            available = set(rows[0].keys())
            missing = required_columns - available
            if missing:
                logger.warning(
                    "CSV %s missing columns: %s (available: %s)",
                    name,
                    missing,
                    available,
                )

    @abc.abstractmethod
    def _extract_rows(self, csvs: dict[str, list[dict[str, str]]]) -> list[ParsedRow]:
        """Extract ParsedRow instances from loaded CSVs.

        Subclasses implement this to handle their specific statement types.
        """
        ...

    def _filter_versions(self, rows: list[ParsedRow]) -> list[ParsedRow]:
        """Keep only the latest version per (cd_cvm, ref_date, period_order, account_code).

        When CVM publishes restatements, the version number increments. We keep
        only the highest version for each unique combination.
        """
        best: dict[tuple[str, str, str, str, str, str], ParsedRow] = {}
        for row in rows:
            key = (
                row.cd_cvm,
                row.ref_date,
                row.period_order,
                row.account_code,
                row.statement_type,
                row.scope,
            )
            existing = best.get(key)
            if existing is None or row.version > existing.version:
                best[key] = row
        filtered = list(best.values())
        logger.info(
            "version filter: %d rows -> %d rows (removed %d superseded)",
            len(rows),
            len(filtered),
            len(rows) - len(filtered),
        )
        return filtered

    # --- Utility methods for subclasses ---

    @staticmethod
    def _normalize_value(row: dict[str, str]) -> float | None:
        """Convert VL_CONTA to a float in full units (not thousands).

        Migrated from market-ingestion's cvm.py normalize_value.
        """
        raw = row.get("VL_CONTA", "").strip()
        if not raw:
            return None
        value = float(raw.replace(",", "."))
        scale = row.get("ESCALA_MOEDA", "").strip().upper()
        if scale == "MIL":
            value *= 1000
        return value

    @staticmethod
    def _parse_version(row: dict[str, str]) -> int:
        """Extract version number from a CSV row."""
        return int(row.get("VERSAO", "1"))
