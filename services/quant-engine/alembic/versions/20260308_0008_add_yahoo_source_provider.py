"""add yahoo to source_provider enum

Revision ID: 20260308_0008
Revises: 20260312_0007
Create Date: 2026-03-08
"""

from __future__ import annotations

from alembic import op


revision = "20260308_0008"
down_revision = "20260312_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE source_provider ADD VALUE IF NOT EXISTS 'yahoo'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # A full enum rebuild would be needed; safe to leave 'yahoo' in place.
    pass
