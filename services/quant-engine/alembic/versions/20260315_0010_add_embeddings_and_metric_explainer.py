"""add embeddings table + metric_explainer to ai_module enum

Revision ID: 20260315_0010
Revises: 20260314_0009
Create Date: 2026-03-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "20260315_0010"
down_revision = "20260314_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add metric_explainer to ai_module enum
    op.execute("ALTER TYPE ai_module ADD VALUE IF NOT EXISTS 'metric_explainer'")

    # Create embeddings table
    op.create_table(
        "embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String, nullable=False),
        sa.Column("entity_id", sa.String, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding", JSONB, nullable=False),
        sa.Column("metadata_json", JSONB),
        sa.Column("model_used", sa.String, nullable=False, server_default="text-embedding-3-small"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("entity_type", "entity_id", "chunk_index", name="uq_embeddings_entity_chunk"),
    )
    op.create_index("idx_embeddings_entity", "embeddings", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("idx_embeddings_entity", table_name="embeddings")
    op.drop_table("embeddings")
    # Note: PostgreSQL does not support removing enum values
