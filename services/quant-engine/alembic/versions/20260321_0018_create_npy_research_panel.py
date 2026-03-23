"""3C.2 — Create npy_research_panel table for research-grade NPY dataset.

Revision ID: 20260321_0018
Revises: 20260321_0017
Create Date: 2026-03-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260321_0018"
down_revision = "20260321_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "npy_research_panel",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("issuer_id", UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("primary_security_id", UUID(as_uuid=True), sa.ForeignKey("securities.id", ondelete="SET NULL")),
        sa.Column("dividend_yield", sa.Numeric()),
        sa.Column("net_buyback_yield", sa.Numeric()),
        sa.Column("net_payout_yield", sa.Numeric()),
        sa.Column("dy_source_tier", sa.String(1)),
        sa.Column("nby_source_tier", sa.String(1)),
        sa.Column("market_cap_source_tier", sa.String(1)),
        sa.Column("shares_source_tier", sa.String(1)),
        sa.Column("npy_source_tier", sa.String(1)),
        sa.Column("quality_flag", sa.String(1)),
        sa.Column("formula_version", sa.String(60), nullable=False),
        sa.Column("dataset_version", sa.String(100), nullable=False),
        sa.Column("dy_metric_id", UUID(as_uuid=True)),
        sa.Column("nby_metric_id", UUID(as_uuid=True)),
        sa.Column("npy_metric_id", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("issuer_id", "reference_date", "dataset_version", name="uq_npy_panel_issuer_date_version"),
    )


def downgrade() -> None:
    op.drop_table("npy_research_panel")
