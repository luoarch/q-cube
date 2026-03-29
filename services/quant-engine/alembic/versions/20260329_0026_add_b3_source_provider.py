"""Add 'b3' to source_provider pgEnum.

Revision ID: 20260329_0026
Revises: 20260326_0025
Create Date: 2026-03-29

Allows market_snapshots.source = 'b3' for B3 COTAHIST data.
"""

from __future__ import annotations

from alembic import op


revision = "20260329_0026"
down_revision = "20260326_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE source_provider ADD VALUE IF NOT EXISTS 'b3'")


def downgrade() -> None:
    # pgEnum values cannot be removed in Postgres. No-op.
    pass
