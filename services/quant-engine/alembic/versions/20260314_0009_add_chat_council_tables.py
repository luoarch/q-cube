"""add chat + council tables for AI Council system

Revision ID: 20260314_0009
Revises: 20260313_0008
Create Date: 2026-03-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "20260314_0009"
down_revision = "20260313_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AI enums (shared with ai-assistant service)
    from sqlalchemy.dialects import postgresql

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

    # AI suggestions table
    op.create_table(
        "ai_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("module", ai_module, nullable=False),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("trigger_entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("output_schema_version", sa.String(20), nullable=False),
        sa.Column("input_snapshot", JSONB, nullable=False),
        sa.Column("output_text", sa.Text, nullable=False),
        sa.Column("structured_output", JSONB),
        sa.Column("confidence", confidence_level, nullable=False),
        sa.Column("model_used", sa.String(50), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("tokens_used", sa.Integer, nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False),
        sa.Column("completion_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("review_status", review_status, nullable=False, server_default="pending"),
        sa.Column("reviewed_by", UUID(as_uuid=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
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
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("suggestion_id", UUID(as_uuid=True), sa.ForeignKey("ai_suggestions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("explanation_type", explanation_type, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ai_research_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("suggestion_id", UUID(as_uuid=True), sa.ForeignKey("ai_suggestions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_type", note_type, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Chat sessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("mode", sa.String, nullable=False, server_default="free_chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_chat_sessions_tenant_user", "chat_sessions", ["tenant_id", "user_id"])

    # Chat messages
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("agent_id", sa.String),
        sa.Column("tool_calls_json", JSONB),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("cost_usd", sa.Numeric),
        sa.Column("provider_used", sa.String),
        sa.Column("model_used", sa.String),
        sa.Column("fallback_level", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_chat_messages_session", "chat_messages", ["session_id"])

    # Council sessions
    op.create_table(
        "council_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("asset_ids", JSONB, nullable=False),
        sa.Column("agent_ids", JSONB, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Council opinions
    op.create_table(
        "council_opinions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("council_session_id", UUID(as_uuid=True), sa.ForeignKey("council_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.String, nullable=False),
        sa.Column("verdict", sa.String, nullable=False),
        sa.Column("confidence", sa.Integer, nullable=False),
        sa.Column("opinion_json", JSONB, nullable=False),
        sa.Column("hard_rejects_json", JSONB),
        sa.Column("profile_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("prompt_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("provider_used", sa.String),
        sa.Column("model_used", sa.String),
        sa.Column("fallback_level", sa.Integer),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("cost_usd", sa.Numeric),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Council debates
    op.create_table(
        "council_debates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("council_session_id", UUID(as_uuid=True), sa.ForeignKey("council_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("agent_id", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("target_agent_id", sa.String),
        sa.Column("provider_used", sa.String),
        sa.Column("model_used", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Council syntheses
    op.create_table(
        "council_syntheses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("council_session_id", UUID(as_uuid=True), sa.ForeignKey("council_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scoreboard_json", JSONB, nullable=False),
        sa.Column("conflicts_json", JSONB, nullable=False),
        sa.Column("synthesis_text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("council_syntheses")
    op.drop_table("council_debates")
    op.drop_table("council_opinions")
    op.drop_table("council_sessions")
    op.drop_index("idx_chat_messages_session", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("idx_chat_sessions_tenant_user", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_table("ai_research_notes")
    op.drop_table("ai_explanations")
    op.drop_table("ai_suggestions")
    from sqlalchemy.dialects import postgresql
    for name in ["note_type", "explanation_type", "confidence_level", "review_status", "ai_module"]:
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
