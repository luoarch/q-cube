"""add refinement_results table for Top-30 Refiner

Revision ID: 20260313_0008
Revises: 20260312_0007
Create Date: 2026-03-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "20260313_0008"
down_revision = "20260312_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refinement_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy_run_id", UUID(as_uuid=True), sa.ForeignKey("strategy_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issuer_id", UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String, nullable=False),
        sa.Column("base_rank", sa.Integer, nullable=False),
        sa.Column("earnings_quality_score", sa.Numeric),
        sa.Column("safety_score", sa.Numeric),
        sa.Column("operating_consistency_score", sa.Numeric),
        sa.Column("capital_discipline_score", sa.Numeric),
        sa.Column("refinement_score", sa.Numeric),
        sa.Column("adjusted_score", sa.Numeric),
        sa.Column("adjusted_rank", sa.Integer),
        sa.Column("flags_json", JSONB),
        sa.Column("trend_data_json", JSONB),
        sa.Column("scoring_details_json", JSONB),
        sa.Column("data_completeness_json", JSONB),
        sa.Column("score_reliability", sa.String),
        sa.Column("issuer_classification", sa.String),
        sa.Column("formula_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("weights_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("strategy_run_id", "issuer_id", name="uq_refinement_results_run_issuer"),
    )
    op.create_index(
        "idx_refinement_results_run_id",
        "refinement_results",
        ["strategy_run_id"],
    )
    op.create_index(
        "idx_refinement_results_tenant_id",
        "refinement_results",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_refinement_results_tenant_id", table_name="refinement_results")
    op.drop_index("idx_refinement_results_run_id", table_name="refinement_results")
    op.drop_table("refinement_results")
