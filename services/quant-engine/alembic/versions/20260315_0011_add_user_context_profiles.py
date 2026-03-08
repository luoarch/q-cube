"""add user_context_profiles table

Revision ID: 20260315_0011
Revises: 20260315_0010
Create Date: 2026-03-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "20260315_0011"
down_revision = "20260315_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_context_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preferred_strategy", sa.String),
        sa.Column("watchlist_json", JSONB),
        sa.Column("preferences_json", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_context_profiles_user_tenant"),
    )
    op.create_index("idx_user_context_profiles_user", "user_context_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_user_context_profiles_user", table_name="user_context_profiles")
    op.drop_table("user_context_profiles")
