"""CLI script to classify all issuers in the investable universe.

Usage:
    source .venv/bin/activate
    python scripts/classify_universe.py
"""
from __future__ import annotations

import logging
import sys
from collections import Counter

from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.universe.classifier import (
    ClassificationResult,
    MissingOverrideBatchError,
    UnmatchedSectorBatchError,
    classify_all,
)
from q3_fundamentals_engine.universe.policy import POLICY_VERSION

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("classify_universe")


def _print_report(result: ClassificationResult, session) -> None:
    from sqlalchemy import func, select
    from q3_shared_models.entities import UniverseClassification

    print(f"\n{'=' * 60}")
    print(f"Universe Classification Report — policy {POLICY_VERSION}")
    print(f"{'=' * 60}")
    print(f"Total issuers:  {result.total}")
    print(f"Inserted:       {result.inserted}")
    print(f"Superseded:     {result.superseded}")
    print(f"Unchanged:      {result.unchanged}")
    print()

    # Distribution by universe_class
    rows = session.execute(
        select(
            UniverseClassification.universe_class,
            func.count(UniverseClassification.id),
        )
        .where(UniverseClassification.superseded_at.is_(None))
        .group_by(UniverseClassification.universe_class)
    ).all()
    print("Distribution by universe_class:")
    for cls, count in sorted(rows, key=lambda x: -x[1]):
        print(f"  {count:4d}  {cls}")

    # Distribution by dedicated_strategy_type
    ded_rows = session.execute(
        select(
            UniverseClassification.dedicated_strategy_type,
            func.count(UniverseClassification.id),
        )
        .where(
            UniverseClassification.superseded_at.is_(None),
            UniverseClassification.universe_class == "DEDICATED_STRATEGY_ONLY",
        )
        .group_by(UniverseClassification.dedicated_strategy_type)
    ).all()
    if ded_rows:
        print("\nDedicated strategy breakdown:")
        for typ, count in sorted(ded_rows, key=lambda x: -x[1]):
            print(f"  {count:4d}  {typ}")

    # Distribution by permanent_exclusion_reason
    excl_rows = session.execute(
        select(
            UniverseClassification.permanent_exclusion_reason,
            func.count(UniverseClassification.id),
        )
        .where(
            UniverseClassification.superseded_at.is_(None),
            UniverseClassification.universe_class == "PERMANENTLY_EXCLUDED",
        )
        .group_by(UniverseClassification.permanent_exclusion_reason)
    ).all()
    if excl_rows:
        print("\nExclusion reason breakdown:")
        for reason, count in sorted(excl_rows, key=lambda x: -x[1]):
            print(f"  {count:4d}  {reason}")

    # Distribution by rule code
    rule_rows = session.execute(
        select(
            UniverseClassification.classification_rule_code,
            func.count(UniverseClassification.id),
        )
        .where(UniverseClassification.superseded_at.is_(None))
        .group_by(UniverseClassification.classification_rule_code)
    ).all()
    print("\nClassification rule breakdown:")
    for rule, count in sorted(rule_rows, key=lambda x: -x[1]):
        print(f"  {count:4d}  {rule}")

    print(f"\n{'=' * 60}")


def _refresh_compat_view(session) -> None:
    """Refresh the materialized compat view after classification changes."""
    from sqlalchemy import text
    logger.info("Refreshing v_financial_statements_compat...")
    try:
        session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY v_financial_statements_compat"))
    except Exception:
        session.execute(text("REFRESH MATERIALIZED VIEW v_financial_statements_compat"))
    session.commit()
    logger.info("Compat view refreshed.")


def main() -> None:
    with SessionLocal() as session:
        try:
            result = classify_all(session, POLICY_VERSION)
            session.commit()
            _print_report(result, session)
            if result.inserted > 0 or result.superseded > 0:
                _refresh_compat_view(session)
            else:
                logger.info("No classification changes — skipping compat view refresh.")
        except UnmatchedSectorBatchError as e:
            logger.error("BATCH FAILED — unmatched sectors:")
            for sector, cvm in e.unmatched:
                logger.error("  sector=%r cvm=%s", sector, cvm)
            sys.exit(1)
        except MissingOverrideBatchError as e:
            logger.error("BATCH FAILED — NULL-sector issuers without override:")
            for cvm in e.missing:
                logger.error("  cvm=%s", cvm)
            sys.exit(1)


if __name__ == "__main__":
    main()
