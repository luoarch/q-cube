"""add assets and financial_statements tables

Revision ID: 20260307_0002
Revises: 20260307_0001
Create Date: 2026-03-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_0002"
down_revision = "20260307_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("sub_sector", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "ticker", name="uq_assets_tenant_ticker"),
    )

    op.create_table(
        "financial_statements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ebit", sa.Numeric(), nullable=True),
        sa.Column("enterprise_value", sa.Numeric(), nullable=True),
        sa.Column("net_working_capital", sa.Numeric(), nullable=True),
        sa.Column("fixed_assets", sa.Numeric(), nullable=True),
        sa.Column("roic", sa.Numeric(), nullable=True),
        sa.Column("net_debt", sa.Numeric(), nullable=True),
        sa.Column("ebitda", sa.Numeric(), nullable=True),
        sa.Column("net_margin", sa.Numeric(), nullable=True),
        sa.Column("gross_margin", sa.Numeric(), nullable=True),
        sa.Column("net_margin_std", sa.Numeric(), nullable=True),
        sa.Column("avg_daily_volume", sa.Numeric(), nullable=True),
        sa.Column("market_cap", sa.Numeric(), nullable=True),
        sa.Column("momentum_12m", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "period_date", name="uq_financial_statements_asset_period"),
    )

    op.create_index(
        "idx_financial_statements_tenant_period",
        "financial_statements",
        ["tenant_id", "period_date"],
        unique=False,
    )

    op.create_index(
        "idx_assets_tenant_active",
        "assets",
        ["tenant_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_assets_tenant_active", table_name="assets")
    op.drop_index("idx_financial_statements_tenant_period", table_name="financial_statements")
    op.drop_table("financial_statements")
    op.drop_table("assets")
