"""Add plan2_runs and plan2_thesis_scores tables for Global Thesis Layer.

Revision ID: 20260315_0016
Revises: 20260309_0015
Create Date: 2026-03-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "20260315_0016"
down_revision = "20260309_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create thesis_bucket enum type
    thesis_bucket_enum = sa.Enum(
        "A_DIRECT", "B_INDIRECT", "C_NEUTRAL", "D_FRAGILE",
        name="thesis_bucket",
    )
    thesis_bucket_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create plan2_runs table
    op.create_table(
        "plan2_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "strategy_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("strategy_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # versioning
        sa.Column("thesis_config_version", sa.String(20), nullable=False),
        sa.Column("pipeline_version", sa.String(20), nullable=False),
        # metadata
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("total_eligible", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_ineligible", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bucket_distribution_json", JSONB, nullable=False, server_default="{}"),
        # lifecycle
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_plan2_runs_tenant_id", "plan2_runs", ["tenant_id"])
    op.create_index("ix_plan2_runs_strategy_run_id", "plan2_runs", ["strategy_run_id"])
    op.create_index("ix_plan2_runs_as_of_date", "plan2_runs", ["as_of_date"])

    # 3. Create plan2_thesis_scores table
    op.create_table(
        "plan2_thesis_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "plan2_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("plan2_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "issuer_id",
            UUID(as_uuid=True),
            sa.ForeignKey("issuers.id"),
            nullable=False,
        ),
        # eligibility
        sa.Column("eligible", sa.Boolean, nullable=False),
        sa.Column("eligibility_json", JSONB, nullable=False),
        # opportunity vector
        sa.Column("direct_commodity_exposure_score", sa.Numeric, nullable=True),
        sa.Column("indirect_commodity_exposure_score", sa.Numeric, nullable=True),
        sa.Column("export_fx_leverage_score", sa.Numeric, nullable=True),
        sa.Column("final_commodity_affinity_score", sa.Numeric, nullable=True),
        # fragility vector
        sa.Column("refinancing_stress_score", sa.Numeric, nullable=True),
        sa.Column("usd_debt_exposure_score", sa.Numeric, nullable=True),
        sa.Column("usd_import_dependence_score", sa.Numeric, nullable=True),
        sa.Column("usd_revenue_offset_score", sa.Numeric, nullable=True),
        sa.Column("final_dollar_fragility_score", sa.Numeric, nullable=True),
        # ranking
        sa.Column("bucket", sa.String(20), nullable=True),
        sa.Column("thesis_rank_score", sa.Numeric, nullable=True),
        sa.Column("thesis_rank", sa.Integer, nullable=True),
        # provenance
        sa.Column("feature_input_json", JSONB, nullable=False),
        sa.Column("explanation_json", JSONB, nullable=True),
        # audit
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # constraints
        sa.UniqueConstraint("plan2_run_id", "issuer_id", name="uq_plan2_thesis_scores_run_issuer"),
    )

    op.create_index("ix_plan2_thesis_scores_run_id", "plan2_thesis_scores", ["plan2_run_id"])
    op.create_index("ix_plan2_thesis_scores_issuer_id", "plan2_thesis_scores", ["issuer_id"])
    op.create_index("ix_plan2_thesis_scores_bucket", "plan2_thesis_scores", ["bucket"])


def downgrade() -> None:
    op.drop_table("plan2_thesis_scores")
    op.drop_table("plan2_runs")
    sa.Enum(name="thesis_bucket").drop(op.get_bind(), checkfirst=True)
