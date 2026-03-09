"""upgrade embeddings column from JSONB to halfvec(1536) with HNSW index

Revision ID: 20260316_0012
Revises: 20260315_0011
Create Date: 2026-03-16
"""

from __future__ import annotations

from alembic import op


revision = "20260316_0012"
down_revision = "20260315_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add temporary halfvec column
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding_vec halfvec(1536)")

    # Copy existing JSONB embeddings to halfvec (array → vector cast)
    op.execute("""
        UPDATE embeddings
        SET embedding_vec = (
            SELECT array_to_string(
                ARRAY(SELECT jsonb_array_elements_text(embedding)),
                ','
            )
        )::halfvec(1536)
        WHERE jsonb_typeof(embedding) = 'array'
          AND jsonb_array_length(embedding) = 1536
    """)

    # Drop old JSONB column and rename
    op.execute("ALTER TABLE embeddings DROP COLUMN embedding")
    op.execute("ALTER TABLE embeddings RENAME COLUMN embedding_vec TO embedding")
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding SET NOT NULL")

    # Create HNSW index for cosine similarity
    op.execute("""
        CREATE INDEX idx_embeddings_hnsw
        ON embeddings
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_hnsw")
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding_jsonb JSONB")
    op.execute("""
        UPDATE embeddings
        SET embedding_jsonb = (
            SELECT jsonb_agg(v::float8)
            FROM unnest(embedding::float4[]) AS v
        )
    """)
    op.execute("ALTER TABLE embeddings DROP COLUMN embedding")
    op.execute("ALTER TABLE embeddings RENAME COLUMN embedding_jsonb TO embedding")
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding SET NOT NULL")
