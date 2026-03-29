"""Plan 5 — CVM Share Counts table.

Revision ID: 20260325_0023
Revises: 20260321_0022
Create Date: 2026-03-25

Creates:
- cvm_share_counts table (PIT time series of CVM composicao_capital)
- Unique constraint on (issuer_id, reference_date, document_type)
- Check constraints for data integrity
"""

from __future__ import annotations

from alembic import op


revision = "20260325_0023"
down_revision = "20260321_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE cvm_share_counts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            issuer_id UUID NOT NULL REFERENCES issuers(id) ON DELETE CASCADE,
            reference_date DATE NOT NULL,
            document_type VARCHAR(3) NOT NULL,
            total_shares NUMERIC NOT NULL,
            treasury_shares NUMERIC NOT NULL,
            net_shares NUMERIC NOT NULL,
            publication_date_estimated DATE NOT NULL,
            source_file TEXT NOT NULL,
            loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT uq_cvm_shares_issuer_date_doctype
                UNIQUE (issuer_id, reference_date, document_type),
            CONSTRAINT chk_document_type
                CHECK (document_type IN ('DFP', 'ITR')),
            CONSTRAINT chk_total_shares_positive
                CHECK (total_shares > 0),
            CONSTRAINT chk_net_shares_consistent
                CHECK (net_shares = total_shares - treasury_shares)
        )
    """)

    op.execute("""
        CREATE INDEX ix_cvm_share_counts_issuer_refdate
            ON cvm_share_counts (issuer_id, reference_date)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cvm_share_counts")
