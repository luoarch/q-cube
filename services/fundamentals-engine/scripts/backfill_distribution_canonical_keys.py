"""Backfill shareholder_distributions canonical key on existing statement_lines.

The canonical mapper was updated after initial import to recognize distribution
patterns in DFC 6.03.XX sub-accounts. This script retroactively applies the
pattern to existing statement_lines where canonical_key is NULL.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/backfill_distribution_canonical_keys.py
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import select, text, update

from q3_fundamentals_engine.db.session import SessionLocal
from q3_shared_models.entities import CanonicalKey, StatementLine, Filing

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_distributions")

# Same patterns as canonical_mapper.py
_DISTRIBUTION_INCLUDE = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"dividend",
        r"\bjcp\b",
        r"juros sobre (?:o )?capital",
        r"jscp",
        r"proventos\s+pagos",
        r"distribui[çc][ãa]o\s+de\s+lucr",
        r"distribui[çc][ãa]o\s+de\s+dividend",
        r"remunera[çc][ãa]o\s+a(?:os?)?\s+acionista",
    ]
]

_DISTRIBUTION_EXCLUDE = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"recebid",
        r"a\s+receber",
    ]
]


def _is_shareholder_distribution(label: str) -> bool:
    if any(pat.search(label) for pat in _DISTRIBUTION_EXCLUDE):
        return False
    return any(pat.search(label) for pat in _DISTRIBUTION_INCLUDE)


def main() -> None:
    with SessionLocal() as session:
        # Find DFC 6.03.XX lines with NULL canonical_key,
        # excluding filings that already have a shareholder_distributions line
        candidates = session.execute(
            select(StatementLine.id, StatementLine.as_reported_label)
            .join(Filing, StatementLine.filing_id == Filing.id)
            .where(
                StatementLine.as_reported_code.like("6.03.%"),
                StatementLine.statement_type.in_(["DFC_MD", "DFC_MI"]),
                StatementLine.canonical_key.is_(None),
            )
            .where(
                ~StatementLine.filing_id.in_(
                    select(StatementLine.filing_id).where(
                        StatementLine.canonical_key == CanonicalKey.shareholder_distributions
                    )
                )
            )
        ).all()

        logger.info("Found %d DFC 6.03.XX lines with NULL canonical_key", len(candidates))

        matched_ids = []
        for sl_id, label in candidates:
            if _is_shareholder_distribution(label):
                matched_ids.append(sl_id)

        logger.info("Matched %d as shareholder_distributions", len(matched_ids))

        if not matched_ids:
            logger.info("Nothing to update.")
            return

        # Batch update
        BATCH = 500
        for i in range(0, len(matched_ids), BATCH):
            batch = matched_ids[i:i + BATCH]
            session.execute(
                update(StatementLine)
                .where(StatementLine.id.in_(batch))
                .values(canonical_key=CanonicalKey.shareholder_distributions)
            )
            logger.info("Updated batch %d-%d", i, i + len(batch))

        session.commit()
        logger.info("Backfill complete: %d lines updated", len(matched_ids))

        # Count affected issuers
        affected = session.execute(text("""
            SELECT count(DISTINCT f.issuer_id)
            FROM statement_lines sl
            JOIN filings f ON f.id = sl.filing_id
            WHERE sl.canonical_key = 'shareholder_distributions'
        """)).scalar()
        print(f"\nIssuers with shareholder_distributions: {affected}")


if __name__ == "__main__":
    main()
