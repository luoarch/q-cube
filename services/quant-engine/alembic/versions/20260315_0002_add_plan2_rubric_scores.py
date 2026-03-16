"""Add plan2_rubric_scores table for manual/AI dimension scoring.

Revision ID: 20260315_0017
Revises: 20260315_0016
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260315_0017"
down_revision = "20260315_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan2_rubric_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("issuer_id", UUID(as_uuid=True), sa.ForeignKey("issuers.id"), nullable=False),
        sa.Column("dimension_key", sa.String(60), nullable=False),
        sa.Column("score", sa.Numeric, nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_version", sa.String(60), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("evidence_ref", sa.Text, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("assessed_by", sa.String(100), nullable=True),
        sa.Column("assessed_at", sa.Date, nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_plan2_rubric_scores_issuer_dim",
        "plan2_rubric_scores",
        ["issuer_id", "dimension_key"],
    )
    op.create_index(
        "ix_plan2_rubric_scores_active",
        "plan2_rubric_scores",
        ["issuer_id", "dimension_key"],
        postgresql_where=sa.text("superseded_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_plan2_rubric_scores_active")
    op.drop_index("ix_plan2_rubric_scores_issuer_dim")
    op.drop_table("plan2_rubric_scores")
