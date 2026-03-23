"""One-time re-mapping: apply label-based DFC mapping to existing statement_lines.

For each filing, finds all DFC 6.03.XX sub-accounts that match distribution
patterns (dividends + JCP), sums their values, and assigns canonical_key
'shareholder_distributions' to ONE representative line per filing/scope/period
group. This respects the unique partial index on statement_lines.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/remap_dfc_distributions.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict

from sqlalchemy import select, update, func

sys.path.insert(0, "src")

from q3_fundamentals_engine.db.session import SessionLocal  # noqa: E402
from q3_fundamentals_engine.normalization.canonical_mapper import _is_shareholder_distribution  # noqa: E402
from q3_shared_models.entities import CanonicalKey, Filing, StatementLine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remap DFC 6.03.XX sub-accounts for shareholder distributions")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        # Find all DFC 6.03.XX lines without a canonical key
        rows = session.execute(
            select(
                StatementLine.id,
                StatementLine.filing_id,
                StatementLine.statement_type,
                StatementLine.scope,
                StatementLine.period_type,
                StatementLine.reference_date,
                StatementLine.as_reported_label,
                StatementLine.normalized_value,
            ).where(
                StatementLine.statement_type.in_(["DFC_MD", "DFC_MI"]),
                StatementLine.as_reported_code.like("6.03.%"),
                StatementLine.canonical_key.is_(None),
            )
        ).all()

        logger.info("Found %d DFC 6.03.XX lines without canonical_key", len(rows))

        # Group matched lines by unique constraint key:
        # (filing_id, statement_type, scope, period_type, reference_date)
        GroupKey = tuple  # (filing_id, stmt_type, scope, period_type, ref_date)
        matched_groups: dict[GroupKey, list] = defaultdict(list)
        matched_labels: dict[str, int] = {}
        excluded_labels: dict[str, int] = {}

        for row_id, filing_id, stmt_type, scope, period_type, ref_date, label, value in rows:
            if _is_shareholder_distribution(label):
                group_key = (filing_id, str(stmt_type), str(scope), str(period_type), str(ref_date))
                matched_groups[group_key].append((row_id, label, value))
                matched_labels[label] = matched_labels.get(label, 0) + 1
            else:
                excluded_labels[label] = excluded_labels.get(label, 0) + 1

        total_matched = sum(len(v) for v in matched_groups.values())
        logger.info("Matched %d lines across %d filing groups", total_matched, len(matched_groups))

        # Show top matched labels
        logger.info("\nTop matched labels:")
        for label, cnt in sorted(matched_labels.items(), key=lambda x: -x[1])[:15]:
            logger.info("  [%4d] %s", cnt, label)

        # Show top excluded labels
        logger.info("\nTop excluded labels (NOT matched):")
        for label, cnt in sorted(excluded_labels.items(), key=lambda x: -x[1])[:10]:
            logger.info("  [%4d] %s", cnt, label)

        # For each group: sum values, pick one representative line to update
        updates_to_apply: list[tuple] = []  # (winner_id, summed_value)
        multi_line_groups = 0

        for group_key, lines in matched_groups.items():
            if len(lines) > 1:
                multi_line_groups += 1
            # Sum all distribution values in this group
            total_value = sum(v for _, _, v in lines if v is not None)
            # Pick the first line as the representative
            winner_id = lines[0][0]
            updates_to_apply.append((winner_id, total_value))

        logger.info(
            "\n%d groups to update (%d with multiple distribution lines aggregated)",
            len(updates_to_apply), multi_line_groups,
        )

        if args.dry_run:
            logger.info("[DRY RUN] Would update %d rows. Exiting.", len(updates_to_apply))
            return

        if not updates_to_apply:
            logger.info("Nothing to update.")
            return

        # Apply updates one by one (each is a different row)
        for i, (row_id, summed_value) in enumerate(updates_to_apply):
            session.execute(
                update(StatementLine)
                .where(StatementLine.id == row_id)
                .values(
                    canonical_key=CanonicalKey.shareholder_distributions.value,
                    normalized_value=summed_value,
                )
            )
            if (i + 1) % 500 == 0:
                session.commit()
                logger.info("  committed %d / %d", i + 1, len(updates_to_apply))

        session.commit()
        logger.info("All %d updates committed.", len(updates_to_apply))

        # Coverage report
        distinct_issuers = session.execute(
            select(func.count(func.distinct(Filing.issuer_id)))
            .join(StatementLine, StatementLine.filing_id == Filing.id)
            .where(StatementLine.canonical_key == CanonicalKey.shareholder_distributions.value)
        ).scalar()
        logger.info("\nCoverage: %d distinct issuers with shareholder_distributions", distinct_issuers)

    finally:
        session.close()


if __name__ == "__main__":
    main()
