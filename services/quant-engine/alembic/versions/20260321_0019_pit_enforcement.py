"""3C.3 — Point-in-time enforcement: publication_date, dataset versions, PIT flag.

Revision ID: 20260321_0019
Revises: 20260321_0018
Create Date: 2026-03-21

Adds:
- publication_date column to filings (estimated CVM publication date)
- npy_dataset_versions table for dataset lifecycle governance
- pit_compliant + knowledge_date columns to npy_research_panel
- Backfills publication_date based on CVM regulatory deadlines
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "20260321_0019"
down_revision = "20260321_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- S1: Add publication_date to filings ---
    op.add_column("filings", sa.Column("publication_date", sa.Date(), nullable=True))

    # Backfill: DFP = reference_date + 90 days, ITR = reference_date + 45 days
    op.execute("""
        UPDATE filings
        SET publication_date = CASE
            WHEN filing_type = 'DFP' THEN reference_date + INTERVAL '90 days'
            WHEN filing_type = 'ITR' THEN reference_date + INTERVAL '45 days'
            ELSE reference_date + INTERVAL '90 days'
        END
    """)

    # --- S3: Add PIT columns to npy_research_panel ---
    op.add_column("npy_research_panel", sa.Column("pit_compliant", sa.Boolean()))
    op.add_column("npy_research_panel", sa.Column("knowledge_date", sa.Date()))

    # --- S4: Create dataset versions table ---
    op.create_table(
        "npy_dataset_versions",
        sa.Column("dataset_version", sa.String(100), primary_key=True),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("knowledge_date", sa.Date()),
        sa.Column("pit_mode", sa.String(20), nullable=False, server_default="relaxed"),
        sa.Column("formula_version", sa.String(60), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("quality_distribution", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("npy_dataset_versions")
    op.drop_column("npy_research_panel", "knowledge_date")
    op.drop_column("npy_research_panel", "pit_compliant")
    op.drop_column("filings", "publication_date")
