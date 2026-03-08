"""Create AI assistant tables.

Revision ID: ai0001
Revises:
Create Date: 2026-03-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ai0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    ai_module = postgresql.ENUM(
        "ranking_explainer", "backtest_narrator",
        name="ai_module", create_type=False,
    )
    review_status = postgresql.ENUM(
        "pending", "approved", "rejected", "expired",
        name="review_status", create_type=False,
    )
    confidence_level = postgresql.ENUM(
        "high", "medium", "low",
        name="confidence_level", create_type=False,
    )
    explanation_type = postgresql.ENUM(
        "position", "sector", "outlier", "metric",
        name="explanation_type", create_type=False,
    )
    note_type = postgresql.ENUM(
        "summary", "concern", "highlight", "recommendation",
        name="note_type", create_type=False,
    )

    for enum in [ai_module, review_status, confidence_level, explanation_type, note_type]:
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ai_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module", ai_module, nullable=False),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("trigger_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("output_schema_version", sa.String(20), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("structured_output", postgresql.JSONB()),
        sa.Column("confidence", confidence_level, nullable=False),
        sa.Column("model_used", sa.String(50), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("review_status", review_status, nullable=False, server_default="pending"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "module", "trigger_entity_id", "input_hash", "prompt_version",
            name="uq_ai_suggestions_dedup",
        ),
    )

    op.create_index("idx_ai_suggestions_tenant_module", "ai_suggestions", ["tenant_id", "module"])
    op.create_index("idx_ai_suggestions_trigger", "ai_suggestions", ["trigger_entity_id"])
    op.create_index("idx_ai_suggestions_review", "ai_suggestions", ["review_status"])

    op.create_table(
        "ai_explanations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suggestion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("explanation_type", explanation_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["suggestion_id"], ["ai_suggestions.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "ai_research_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suggestion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_type", note_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["suggestion_id"], ["ai_suggestions.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("ai_research_notes")
    op.drop_table("ai_explanations")
    op.drop_table("ai_suggestions")

    for name in ["note_type", "explanation_type", "confidence_level", "review_status", "ai_module"]:
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
