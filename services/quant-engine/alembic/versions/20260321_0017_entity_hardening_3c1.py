"""3C.1 Entity Hardening — supersede duplicates + deterministic primary selection

Revision ID: 20260321_0017
Revises: 20260320_0016
Create Date: 2026-03-21

Migration note:
- Adds primary_rule_version and primary_rule_reason columns to securities
- Scope A: Supersedes 439 duplicate securities from 2026-03-09 (valid_to + is_primary=false)
- Scope B: Deterministic primary selection for multi-ticker issuers
  - Rule: highest snapshot_count wins; tiebreak suffix 3>4>5>6>11; then lowest security_id
  - Records primary_rule_version='v1-data-continuity' and primary_rule_reason
  - Populates security_class from ticker suffix (3→ON, 4→PN, 5→PNA, 6→PNB, 11→UNIT)
- Refreshes materialized view v_financial_statements_compat
- No data deletion — audit trail preserved via valid_to
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260321_0017"
down_revision = "20260320_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Schema: add metadata columns ---
    op.add_column("securities", sa.Column("primary_rule_version", sa.String(), nullable=True))
    op.add_column("securities", sa.Column("primary_rule_reason", sa.String(), nullable=True))

    # --- Scope A: Supersede 439 duplicate securities from 2026-03-09 ---
    op.execute("""
        UPDATE securities
        SET valid_to = now()::date,
            is_primary = false,
            primary_rule_version = 'v1-data-continuity',
            primary_rule_reason = 'superseded_reimport'
        WHERE valid_from = '2026-03-09'::date
    """)

    # --- Scope B: Deterministic primary selection ---

    # Step 1: Populate security_class from ticker suffix for all current securities
    op.execute("""
        UPDATE securities
        SET security_class = CASE
            WHEN ticker ~ '3$' THEN 'ON'
            WHEN ticker ~ '4$' THEN 'PN'
            WHEN ticker ~ '5$' THEN 'PNA'
            WHEN ticker ~ '6$' THEN 'PNB'
            WHEN ticker ~ '11$' THEN 'UNIT'
            ELSE NULL
        END
        WHERE valid_to IS NULL
    """)

    # Step 2: Reset all is_primary to false for current securities
    op.execute("""
        UPDATE securities
        SET is_primary = false
        WHERE valid_to IS NULL
    """)

    # Step 3: For issuers with exactly 1 current security, that security is primary
    op.execute("""
        UPDATE securities s
        SET is_primary = true,
            primary_rule_version = 'v1-data-continuity',
            primary_rule_reason = 'single_ticker'
        FROM (
            SELECT issuer_id
            FROM securities
            WHERE valid_to IS NULL
            GROUP BY issuer_id
            HAVING count(*) = 1
        ) single
        WHERE s.issuer_id = single.issuer_id
          AND s.valid_to IS NULL
    """)

    # Step 4: For issuers with multiple current securities, pick by snapshot count + tiebreak
    # Uses a window function to rank securities per issuer
    op.execute("""
        UPDATE securities s
        SET is_primary = true,
            primary_rule_version = 'v1-data-continuity',
            primary_rule_reason = ranked.reason
        FROM (
            SELECT
                sec.id AS security_id,
                CASE
                    WHEN snap_count > 0 AND snap_count > COALESCE(
                        LEAD(snap_count) OVER (
                            PARTITION BY sec.issuer_id
                            ORDER BY snap_count DESC, suffix_rank ASC, sec.id ASC
                        ), -1
                    ) THEN 'highest_snapshot_count'
                    WHEN suffix_rank = 1 THEN 'tiebreak_suffix_3'
                    WHEN suffix_rank = 2 THEN 'tiebreak_suffix_4'
                    ELSE 'tiebreak_id'
                END AS reason,
                ROW_NUMBER() OVER (
                    PARTITION BY sec.issuer_id
                    ORDER BY snap_count DESC, suffix_rank ASC, sec.id ASC
                ) AS rn
            FROM securities sec
            LEFT JOIN LATERAL (
                SELECT count(*) AS snap_count
                FROM market_snapshots ms
                WHERE ms.security_id = sec.id
            ) sc ON true
            CROSS JOIN LATERAL (
                SELECT CASE
                    WHEN sec.ticker ~ '3$' THEN 1
                    WHEN sec.ticker ~ '4$' THEN 2
                    WHEN sec.ticker ~ '5$' THEN 3
                    WHEN sec.ticker ~ '6$' THEN 4
                    WHEN sec.ticker ~ '11$' THEN 5
                    ELSE 6
                END AS suffix_rank
            ) sr
            WHERE sec.valid_to IS NULL
              AND sec.issuer_id IN (
                  SELECT issuer_id FROM securities
                  WHERE valid_to IS NULL
                  GROUP BY issuer_id HAVING count(*) > 1
              )
        ) ranked
        WHERE s.id = ranked.security_id
          AND ranked.rn = 1
    """)

    # --- Refresh compat view ---
    op.execute("REFRESH MATERIALIZED VIEW v_financial_statements_compat")


def downgrade() -> None:
    # Restore is_primary=true on all current securities (original blanket state)
    op.execute("""
        UPDATE securities
        SET is_primary = true,
            primary_rule_version = NULL,
            primary_rule_reason = NULL
        WHERE valid_to IS NULL
    """)

    # Restore superseded securities to current
    op.execute("""
        UPDATE securities
        SET valid_to = NULL,
            is_primary = true,
            primary_rule_version = NULL,
            primary_rule_reason = NULL,
            security_class = NULL
        WHERE primary_rule_reason = 'superseded_reimport'
    """)

    # Reset security_class
    op.execute("UPDATE securities SET security_class = NULL WHERE security_class IS NOT NULL AND security_class != 'INDEX'")

    op.drop_column("securities", "primary_rule_reason")
    op.drop_column("securities", "primary_rule_version")

    op.execute("REFRESH MATERIALIZED VIEW v_financial_statements_compat")
