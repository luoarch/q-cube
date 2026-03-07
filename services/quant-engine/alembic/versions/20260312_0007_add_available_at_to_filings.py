"""add available_at to filings for point-in-time data

Revision ID: 20260312_0007
Revises: 20260311_0006
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260312_0007"
down_revision = "20260311_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "filings",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill with created_at as best available proxy
    op.execute("UPDATE filings SET available_at = created_at")
    op.alter_column("filings", "available_at", nullable=False)
    op.create_index(
        "idx_filings_issuer_available",
        "filings",
        ["issuer_id", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_filings_issuer_available", table_name="filings")
    op.drop_column("filings", "available_at")
