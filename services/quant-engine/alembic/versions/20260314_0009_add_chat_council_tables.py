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
