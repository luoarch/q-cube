"""Add unique partial index on statement_lines for data integrity.

Revision ID: 20260309_0015
Revises: 20260318_0014
Create Date: 2026-03-09
"""
from alembic import op

revision = "20260309_0015"
down_revision = "20260318_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_statement_lines_canonical
        ON statement_lines (filing_id, canonical_key, statement_type, scope, period_type, reference_date)
        WHERE canonical_key IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_statement_lines_canonical")
