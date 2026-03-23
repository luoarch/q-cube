"""Plan 4 — Investable Universe Classification Engine.

Revision ID: 20260322_0020
Revises: 20260321_0019
Create Date: 2026-03-22

Creates:
- 4 pgEnums: universe_class, dedicated_strategy_type, permanent_exclusion_reason, classification_rule_code
- universe_classifications table with supersede pattern
- Partial unique index (1 active row per issuer)
- 4 check constraints for semantic consistency
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260322_0020"
down_revision = "20260321_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enums ---
    op.execute("""
        CREATE TYPE universe_class AS ENUM (
            'CORE_ELIGIBLE',
            'DEDICATED_STRATEGY_ONLY',
            'PERMANENTLY_EXCLUDED'
        )
    """)
    op.execute("""
        CREATE TYPE dedicated_strategy_type AS ENUM (
            'FINANCIAL',
            'REAL_ESTATE_DEVELOPMENT',
            'UNCLASSIFIED_HOLDING'
        )
    """)
    op.execute("""
        CREATE TYPE permanent_exclusion_reason AS ENUM (
            'RETAIL_WHOLESALE',
            'AIRLINE',
            'TOURISM_HOSPITALITY',
            'FOREIGN_RETAIL',
            'NOT_A_COMPANY'
        )
    """)
    op.execute("""
        CREATE TYPE classification_rule_code AS ENUM (
            'SECTOR_MAP',
            'ISSUER_OVERRIDE'
        )
    """)

    # --- Table (use raw SQL to avoid sa.Enum auto-create issues) ---
    op.execute("""
        CREATE TABLE universe_classifications (
            id UUID PRIMARY KEY,
            issuer_id UUID NOT NULL REFERENCES issuers(id) ON DELETE CASCADE,
            universe_class universe_class NOT NULL,
            dedicated_strategy_type dedicated_strategy_type,
            permanent_exclusion_reason permanent_exclusion_reason,
            classification_rule_code classification_rule_code NOT NULL,
            classification_reason TEXT NOT NULL,
            matched_sector_key TEXT,
            policy_version VARCHAR(20) NOT NULL,
            classified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            superseded_at TIMESTAMPTZ
        )
    """)

    # --- Partial unique index: 1 active row per issuer ---
    op.execute("""
        CREATE UNIQUE INDEX uq_universe_class_active
        ON universe_classifications (issuer_id)
        WHERE superseded_at IS NULL
    """)

    # --- Check constraints ---
    op.execute("""
        ALTER TABLE universe_classifications ADD CONSTRAINT chk_core_eligible
        CHECK (universe_class != 'CORE_ELIGIBLE'
            OR (dedicated_strategy_type IS NULL AND permanent_exclusion_reason IS NULL))
    """)
    op.execute("""
        ALTER TABLE universe_classifications ADD CONSTRAINT chk_dedicated
        CHECK (universe_class != 'DEDICATED_STRATEGY_ONLY'
            OR (dedicated_strategy_type IS NOT NULL AND permanent_exclusion_reason IS NULL))
    """)
    op.execute("""
        ALTER TABLE universe_classifications ADD CONSTRAINT chk_excluded
        CHECK (universe_class != 'PERMANENTLY_EXCLUDED'
            OR (dedicated_strategy_type IS NULL AND permanent_exclusion_reason IS NOT NULL))
    """)
    op.execute("""
        ALTER TABLE universe_classifications ADD CONSTRAINT chk_sector_map_key
        CHECK (classification_rule_code != 'SECTOR_MAP'
            OR matched_sector_key IS NOT NULL)
    """)


def downgrade() -> None:
    op.drop_table("universe_classifications")
    op.execute("DROP TYPE IF EXISTS classification_rule_code")
    op.execute("DROP TYPE IF EXISTS permanent_exclusion_reason")
    op.execute("DROP TYPE IF EXISTS dedicated_strategy_type")
    op.execute("DROP TYPE IF EXISTS universe_class")
