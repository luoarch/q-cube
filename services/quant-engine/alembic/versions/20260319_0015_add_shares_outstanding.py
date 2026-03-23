"""add shares_outstanding column to market_snapshots

Revision ID: 20260319_0015
Revises: 20260318_0014
Create Date: 2026-03-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_0015"
down_revision = "20260315_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_snapshots",
        sa.Column("shares_outstanding", sa.Numeric, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_snapshots", "shares_outstanding")
