"""add per-tenant rate limit and cost limit columns

Revision ID: 20260317_0013
Revises: 20260316_0012
Create Date: 2026-03-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0013"
down_revision = "20260316_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("rate_limit_rpm", sa.Integer, nullable=False, server_default="100"))
    op.add_column("tenants", sa.Column("ai_daily_cost_limit_usd", sa.Numeric, nullable=False, server_default="10.0"))


def downgrade() -> None:
    op.drop_column("tenants", "ai_daily_cost_limit_usd")
    op.drop_column("tenants", "rate_limit_rpm")
