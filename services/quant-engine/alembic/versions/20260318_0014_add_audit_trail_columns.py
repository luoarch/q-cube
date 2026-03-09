"""add input_hash and audit_trail_json to council_sessions, input_hash to chat_messages

Revision ID: 20260318_0014
Revises: 20260317_0013
Create Date: 2026-03-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260318_0014"
down_revision = "20260317_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("council_sessions", sa.Column("input_hash", sa.String, nullable=True))
    op.add_column("council_sessions", sa.Column("audit_trail_json", JSONB, nullable=True))
    op.add_column("chat_messages", sa.Column("input_hash", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "input_hash")
    op.drop_column("council_sessions", "audit_trail_json")
    op.drop_column("council_sessions", "input_hash")
