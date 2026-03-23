"""Strategy Status Governance — strategy_status_registry table.

Revision ID: 20260321_0022
Revises: 20260322_0021
Create Date: 2026-03-21

Creates:
- 3 pgEnums: strategy_role, promotion_status, decision_source
- strategy_status_registry table with supersede pattern
- Partial unique index on strategy_fingerprint
"""

from __future__ import annotations

from alembic import op


revision = "20260321_0022"
down_revision = "20260322_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE strategy_role AS ENUM ('CONTROL', 'CANDIDATE', 'FRONTRUNNER')
    """)
    op.execute("""
        CREATE TYPE promotion_status AS ENUM ('NOT_EVALUATED', 'BLOCKED', 'PROMOTED', 'REJECTED')
    """)
    op.execute("""
        CREATE TYPE decision_source AS ENUM ('TECH_LEAD_REVIEW', 'AUTOMATED_PIPELINE')
    """)

    op.execute("""
        CREATE TABLE strategy_status_registry (
            id UUID PRIMARY KEY,
            strategy_key VARCHAR(100) NOT NULL,
            strategy_fingerprint VARCHAR(64) NOT NULL,
            strategy_type strategy_type NOT NULL,
            role strategy_role NOT NULL,
            promotion_status promotion_status NOT NULL,
            config_json JSONB NOT NULL,
            evidence_summary TEXT NOT NULL,
            experiment_ids JSONB NOT NULL DEFAULT '[]',
            is_sharpe_avg NUMERIC,
            oos_sharpe_avg NUMERIC,
            promotion_checks JSONB NOT NULL DEFAULT '{}',
            decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            decided_by decision_source NOT NULL,
            superseded_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX uq_strategy_status_active
        ON strategy_status_registry (strategy_fingerprint)
        WHERE superseded_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS strategy_status_registry")
    op.execute("DROP TYPE IF EXISTS decision_source")
    op.execute("DROP TYPE IF EXISTS promotion_status")
    op.execute("DROP TYPE IF EXISTS strategy_role")
