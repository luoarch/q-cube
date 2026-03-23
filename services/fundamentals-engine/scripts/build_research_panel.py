"""Build the NPY research panel for a given reference date.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/build_research_panel.py --reference-date 2024-12-31 --dataset-version npy_panel_2024q4_v1
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

from q3_fundamentals_engine.db.session import SessionLocal
from q3_fundamentals_engine.research.panel_builder import build_npy_research_panel

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build NPY research panel")
    parser.add_argument("--reference-date", type=date.fromisoformat, default=date(2024, 12, 31))
    parser.add_argument("--dataset-version", type=str, default="npy_panel_2024q4_v1")
    parser.add_argument("--knowledge-date", type=date.fromisoformat, default=None,
                        help="Enable PIT mode: only consider data available by this date")
    args = parser.parse_args()

    from collections import Counter

    with SessionLocal() as session:
        rows = build_npy_research_panel(
            session,
            reference_date=args.reference_date,
            dataset_version=args.dataset_version,
            knowledge_date=args.knowledge_date,
        )

        # Collect summary before commit (while session is open)
        total = len(rows)
        quality_dist = Counter(r.quality_flag for r in rows)
        tier_dist = Counter(r.npy_source_tier for r in rows)
        has_dy = sum(1 for r in rows if r.dividend_yield is not None)
        has_nby = sum(1 for r in rows if r.net_buyback_yield is not None)
        has_npy = sum(1 for r in rows if r.net_payout_yield is not None)
        pit_true = sum(1 for r in rows if r.pit_compliant is True)
        pit_false = sum(1 for r in rows if r.pit_compliant is False)

        session.commit()

    print(f"\nBuilt {total} research panel rows")
    print(f"\nQuality distribution: {dict(sorted(quality_dist.items()))}")
    print(f"NPY tier distribution: {dict(sorted(tier_dist.items()))}")
    print(f"\nDY present: {has_dy}/{total}")
    print(f"NBY present: {has_nby}/{total}")
    print(f"NPY present: {has_npy}/{total}")
    if args.knowledge_date:
        print(f"\nPIT mode: strict (knowledge_date={args.knowledge_date})")
        print(f"PIT compliant: {pit_true}/{total}")
        print(f"PIT violations: {pit_false}/{total}")


if __name__ == "__main__":
    main()
