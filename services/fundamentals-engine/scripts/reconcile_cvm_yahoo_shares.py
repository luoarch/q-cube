"""Reconcile CVM share counts vs Yahoo shares_outstanding.

Compares cvm_share_counts.net_shares with market_snapshots.shares_outstanding
for issuers with both sources at a given reference_date.

Report: 5 categories (concordance_total, divergence_moderate, divergence_severe,
only_cvm, only_yahoo) per Plan 5 §R5.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/reconcile_cvm_yahoo_shares.py
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from q3_fundamentals_engine.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("reconcile")

REF_DATE = "2024-12-31"


def main() -> None:
    with SessionLocal() as session:
        # Segmented reconciliation
        recon = session.execute(text(f"""
            WITH cvm AS (
                SELECT DISTINCT ON (issuer_id) issuer_id, net_shares
                FROM cvm_share_counts
                WHERE reference_date = '{REF_DATE}'
                ORDER BY issuer_id, CASE WHEN document_type = 'DFP' THEN 0 ELSE 1 END
            ),
            yahoo AS (
                SELECT DISTINCT ON (s.issuer_id) s.issuer_id, ms.shares_outstanding
                FROM market_snapshots ms
                JOIN securities s ON s.id = ms.security_id AND s.is_primary = true AND s.valid_to IS NULL
                WHERE ms.shares_outstanding IS NOT NULL
                  AND ms.fetched_at >= '{REF_DATE}'::date - interval '30 days'
                  AND ms.fetched_at <= '{REF_DATE}'::date + interval '30 days'
                ORDER BY s.issuer_id, abs(extract(epoch from ms.fetched_at - '{REF_DATE}'::timestamptz))
            )
            SELECT
                CASE
                    WHEN y.issuer_id IS NULL THEN 'only_cvm'
                    WHEN c.issuer_id IS NULL THEN 'only_yahoo'
                    WHEN abs(c.net_shares - y.shares_outstanding) / NULLIF(GREATEST(c.net_shares, y.shares_outstanding), 0) < 0.02 THEN 'concordance_total'
                    WHEN abs(c.net_shares - y.shares_outstanding) / NULLIF(GREATEST(c.net_shares, y.shares_outstanding), 0) < 0.10 THEN 'divergence_moderate'
                    ELSE 'divergence_severe'
                END AS category,
                count(*) AS cnt
            FROM cvm c
            FULL OUTER JOIN yahoo y ON c.issuer_id = y.issuer_id
            GROUP BY 1
            ORDER BY 1
        """)).fetchall()

        total = sum(r[1] for r in recon)

        print(f"\n{'=' * 60}")
        print(f"CVM vs Yahoo Reconciliation Report ({REF_DATE})")
        print(f"{'=' * 60}")
        for cat, cnt in recon:
            print(f"  {cat:25s}: {cnt:4d} ({cnt / total * 100:.1f}%)")
        print(f"  {'TOTAL':25s}: {total:4d}")

        # Ratio distribution for those with both sources
        ratios = session.execute(text(f"""
            WITH cvm AS (
                SELECT DISTINCT ON (issuer_id) issuer_id, net_shares
                FROM cvm_share_counts
                WHERE reference_date = '{REF_DATE}'
                ORDER BY issuer_id, CASE WHEN document_type = 'DFP' THEN 0 ELSE 1 END
            ),
            yahoo AS (
                SELECT DISTINCT ON (s.issuer_id) s.issuer_id, ms.shares_outstanding
                FROM market_snapshots ms
                JOIN securities s ON s.id = ms.security_id AND s.is_primary = true AND s.valid_to IS NULL
                WHERE ms.shares_outstanding IS NOT NULL
                  AND ms.fetched_at >= '{REF_DATE}'::date - interval '30 days'
                  AND ms.fetched_at <= '{REF_DATE}'::date + interval '30 days'
                ORDER BY s.issuer_id, abs(extract(epoch from ms.fetched_at - '{REF_DATE}'::timestamptz))
            )
            SELECT round(y.shares_outstanding / NULLIF(c.net_shares, 0)) AS ratio, count(*)
            FROM cvm c
            JOIN yahoo y ON c.issuer_id = y.issuer_id
            WHERE c.net_shares > 0 AND y.shares_outstanding > 0
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 10
        """)).fetchall()

        print(f"\nYahoo/CVM ratio distribution:")
        for ratio, cnt in ratios:
            print(f"  ~{ratio:,.0f}x: {cnt} issuers")

        print(f"\nNote: ~1000x divergences are a systematic CVM unit scale issue")
        print(f"(CVM in thousands, Yahoo in units). NBY is scale-invariant.")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
