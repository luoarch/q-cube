from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime

from q3_shared_models.entities import (
    Filing,
    FilingStatus,
    FilingType,
    Issuer,
    PeriodType,
    ScopeType,
    SourceProvider,
    StatementLine,
    StatementType,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from q3_fundamentals_engine.normalization.canonical_mapper import CanonicalKeyMapper
from q3_fundamentals_engine.normalization.scope_resolver import resolve_scope
from q3_fundamentals_engine.normalization.sign_normalizer import normalize_sign
from q3_fundamentals_engine.parsers.models import ParsedRow

logger = logging.getLogger(__name__)

# Maps CVM period_order values to our PeriodType enum.
# "PENÚLTIMO"/"PENULTIMO" = prior-year comparison data included in the same DFP filing.
# We SKIP those rows entirely — they duplicate the previous year's actual filing.
_PERIOD_TYPE_MAP: dict[str, PeriodType] = {
    "ÚLTIMO": PeriodType.annual,
    "ULTIMO": PeriodType.annual,
}

# Period orders that should be discarded (prior-year comparison data)
_SKIP_PERIOD_ORDERS: set[str] = {"PENÚLTIMO", "PENULTIMO"}

# Maps CVM statement_type strings to FilingType
_FILING_TYPE_FROM_PERIOD: dict[str, FilingType] = {
    "annual": FilingType.DFP,
    "quarterly": FilingType.ITR,
}


def _parse_ref_date(ref_date_str: str) -> date:
    """Parse a reference date string (YYYY-MM-DD) into a date object."""
    return datetime.strptime(ref_date_str, "%Y-%m-%d").date()


def _resolve_period_type(period_order: str) -> PeriodType:
    """Resolve period_order string to PeriodType enum."""
    return _PERIOD_TYPE_MAP.get(period_order, PeriodType.quarterly)


def _resolve_statement_type(statement_type_str: str) -> StatementType:
    """Resolve CVM statement_type string to StatementType enum."""
    cleaned = statement_type_str.strip().upper().replace(" ", "_")
    try:
        return StatementType(cleaned)
    except ValueError:
        logger.warning("Unknown statement type '%s', defaulting to DRE", statement_type_str)
        return StatementType.DRE


def _resolve_scope_type(scope_str: str) -> ScopeType:
    """Resolve scope string to ScopeType enum."""
    try:
        return ScopeType(scope_str.lower())
    except ValueError:
        return ScopeType.ind


class NormalizationPipeline:
    """Transforms ParsedRows into Filing + StatementLine records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def normalize(self, parsed_rows: list[ParsedRow]) -> list[uuid.UUID]:
        """Normalize parsed rows into filings + statement_lines.

        Groups by (cd_cvm, ref_date, version).
        Each group becomes one Filing with many StatementLines.
        Returns list of created filing IDs.
        """
        if not parsed_rows:
            return []

        # Filter out prior-year comparison rows ("PENÚLTIMO")
        filtered_rows = [
            row for row in parsed_rows
            if row.period_order.upper() not in _SKIP_PERIOD_ORDERS
        ]
        skipped = len(parsed_rows) - len(filtered_rows)
        if skipped:
            logger.info(
                "Skipped %d prior-year (PENÚLTIMO) rows out of %d total",
                skipped,
                len(parsed_rows),
            )

        # Group rows by (cd_cvm, ref_date, version)
        groups: dict[tuple[str, str, int], list[ParsedRow]] = defaultdict(list)
        for row in filtered_rows:
            key = (row.cd_cvm, row.ref_date, row.version)
            groups[key].append(row)

        filing_ids: list[uuid.UUID] = []

        for (cd_cvm, ref_date_str, version), group_rows in groups.items():
            # Resolve scope: group rows by scope, pick consolidated if available
            rows_by_scope: dict[str, list[ParsedRow]] = defaultdict(list)
            for row in group_rows:
                rows_by_scope[row.scope.lower()].append(row)

            chosen_scope, scoped_rows = resolve_scope(rows_by_scope)

            if not scoped_rows:
                logger.warning(
                    "No rows after scope resolution for cd_cvm=%s ref_date=%s version=%d",
                    cd_cvm,
                    ref_date_str,
                    version,
                )
                continue

            # Get or create issuer stub
            sample_row = scoped_rows[0]
            issuer = self._get_or_create_issuer(
                cvm_code=cd_cvm,
                cnpj=sample_row.cnpj,
                legal_name=sample_row.company_name,
            )

            # Determine filing type from doc_type (parser knows) or fallback to period
            if sample_row.doc_type:
                filing_type = FilingType(sample_row.doc_type)
            else:
                period_type_val = _resolve_period_type(sample_row.period_order)
                filing_type = _FILING_TYPE_FROM_PERIOD.get(period_type_val.value, FilingType.DFP)
            period_type = _resolve_period_type(sample_row.period_order)
            ref_date = _parse_ref_date(ref_date_str)

            # Create Filing
            filing_id = uuid.uuid4()
            filing = Filing(
                id=filing_id,
                issuer_id=issuer.id,
                source=SourceProvider.cvm,
                filing_type=filing_type,
                reference_date=ref_date,
                version_number=version,
                is_restatement=version > 1,
                status=FilingStatus.completed,
            )
            self._session.add(filing)

            # Create StatementLines (with dedup safety net)
            lines_created = 0
            seen_keys: set[tuple[str | None, str, str, str, str]] = set()
            for row in scoped_rows:
                canonical_key = CanonicalKeyMapper.map(row.account_code)
                normalized_value = normalize_sign(canonical_key, row.value)
                statement_type = _resolve_statement_type(row.statement_type)
                scope_type = _resolve_scope_type(chosen_scope)

                dedup_key = (canonical_key, statement_type.value, scope_type.value, period_type.value, str(ref_date))
                if dedup_key in seen_keys:
                    logger.warning(
                        "Duplicate statement_line skipped: canonical_key=%s stmt=%s scope=%s period=%s ref=%s",
                        canonical_key, statement_type.value, scope_type.value, period_type.value, ref_date,
                    )
                    continue
                if canonical_key is not None:
                    seen_keys.add(dedup_key)

                line = StatementLine(
                    id=uuid.uuid4(),
                    filing_id=filing_id,
                    statement_type=statement_type,
                    scope=scope_type,
                    period_type=period_type,
                    reference_date=ref_date,
                    canonical_key=canonical_key,
                    as_reported_label=row.account_description,
                    as_reported_code=row.account_code,
                    normalized_value=normalized_value,
                    unit_scale=row.scale or "UNIDADE",
                )
                self._session.add(line)
                lines_created += 1

            self._session.flush()
            filing_ids.append(filing_id)

            logger.info(
                "Created filing %s for issuer cvm_code=%s ref_date=%s with %d statement lines",
                filing_id,
                cd_cvm,
                ref_date_str,
                lines_created,
            )

        return filing_ids

    def _get_or_create_issuer(
        self,
        cvm_code: str,
        cnpj: str,
        legal_name: str,
    ) -> Issuer:
        """Look up an issuer by cvm_code, creating a minimal stub if not found.

        Uses INSERT ... ON CONFLICT DO NOTHING to handle concurrent workers.
        """
        # Check local session cache first
        issuer = self._session.execute(
            select(Issuer).where(Issuer.cvm_code == cvm_code)
        ).scalar_one_or_none()
        if issuer is not None:
            return issuer

        # Upsert: insert if not exists, ignore if already present
        new_id = uuid.uuid4()
        stmt = pg_insert(Issuer).values(
            id=new_id,
            cvm_code=cvm_code,
            cnpj=cnpj,
            legal_name=legal_name,
        ).on_conflict_do_nothing(index_elements=["cvm_code"])
        self._session.execute(stmt)
        self._session.flush()

        # Re-fetch to get the actual row (might be pre-existing)
        issuer = self._session.execute(
            select(Issuer).where(Issuer.cvm_code == cvm_code)
        ).scalar_one()
        logger.info("Created issuer stub cvm_code=%s cnpj=%s", cvm_code, cnpj)
        return issuer
