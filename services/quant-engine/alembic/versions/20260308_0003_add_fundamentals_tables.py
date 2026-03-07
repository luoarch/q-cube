"""add fundamentals tables (raw, normalized, derived layers)

Revision ID: 20260308_0003
Revises: 20260307_0002
Create Date: 2026-03-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260308_0003"
down_revision = "20260307_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- New enums ---
    source_provider = postgresql.ENUM(
        "cvm", "brapi", "dados_de_mercado", "manual",
        name="source_provider", create_type=False,
    )
    filing_type = postgresql.ENUM("DFP", "ITR", "FCA", name="filing_type", create_type=False)
    batch_status = postgresql.ENUM(
        "pending", "downloading", "processing", "completed", "failed",
        name="batch_status", create_type=False,
    )
    filing_status = postgresql.ENUM(
        "pending", "processing", "completed", "failed", "superseded",
        name="filing_status", create_type=False,
    )
    statement_type = postgresql.ENUM(
        "DRE", "BPA", "BPP", "DFC_MD", "DFC_MI", "DMPL", "DVA",
        name="statement_type", create_type=False,
    )
    scope_type = postgresql.ENUM("con", "ind", name="scope_type", create_type=False)
    period_type = postgresql.ENUM("annual", "quarterly", name="period_type", create_type=False)

    for enum in [source_provider, filing_type, batch_status, filing_status, statement_type, scope_type, period_type]:
        enum.create(op.get_bind(), checkfirst=True)

    # --- Raw layer ---
    op.create_table(
        "raw_source_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", source_provider, nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("document_type", filing_type, nullable=False),
        sa.Column("status", batch_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "raw_source_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["raw_source_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Normalized layer ---
    op.create_table(
        "issuers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cvm_code", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=False),
        sa.Column("trade_name", sa.String(), nullable=True),
        sa.Column("cnpj", sa.String(), nullable=False),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("subsector", sa.String(), nullable=True),
        sa.Column("segment", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cvm_code"),
        sa.UniqueConstraint("cnpj"),
    )

    op.create_table(
        "securities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("security_class", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["issuer_id"], ["issuers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer_id", "ticker", "valid_from", name="uq_securities_issuer_ticker_valid"),
    )

    op.create_table(
        "filings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", source_provider, nullable=False),
        sa.Column("filing_type", filing_type, nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_restatement", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("supersedes_filing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", filing_status, nullable=False),
        sa.Column("raw_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("validation_result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["issuer_id"], ["issuers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_filing_id"], ["filings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["raw_file_id"], ["raw_source_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "statement_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_type", statement_type, nullable=False),
        sa.Column("scope", scope_type, nullable=False),
        sa.Column("period_type", period_type, nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("canonical_key", sa.String(), nullable=True),
        sa.Column("as_reported_label", sa.String(), nullable=False),
        sa.Column("as_reported_code", sa.String(), nullable=False),
        sa.Column("normalized_value", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.String(), server_default="BRL", nullable=False),
        sa.Column("unit_scale", sa.String(), server_default="UNIDADE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Derived layer ---
    op.create_table(
        "computed_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metric_code", sa.String(), nullable=False),
        sa.Column("period_type", period_type, nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("formula_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("inputs_snapshot_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_filing_ids_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["issuer_id"], ["issuers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "restatement_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("new_filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("affected_metrics", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["original_filing_id"], ["filings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["new_filing_id"], ["filings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Indexes ---
    op.create_index("idx_issuers_cvm_code", "issuers", ["cvm_code"], unique=True)
    op.create_index("idx_securities_issuer_id", "securities", ["issuer_id"])
    op.create_index("idx_filings_issuer_ref_date", "filings", ["issuer_id", "reference_date"])
    op.create_index("idx_statement_lines_filing_id", "statement_lines", ["filing_id"])
    op.create_index("idx_statement_lines_canonical_key", "statement_lines", ["canonical_key"])
    op.create_index("idx_computed_metrics_issuer_code", "computed_metrics", ["issuer_id", "metric_code"])
    op.create_index("idx_raw_source_files_hash", "raw_source_files", ["sha256_hash"])


def downgrade() -> None:
    op.drop_index("idx_raw_source_files_hash", table_name="raw_source_files")
    op.drop_index("idx_computed_metrics_issuer_code", table_name="computed_metrics")
    op.drop_index("idx_statement_lines_canonical_key", table_name="statement_lines")
    op.drop_index("idx_statement_lines_filing_id", table_name="statement_lines")
    op.drop_index("idx_filings_issuer_ref_date", table_name="filings")
    op.drop_index("idx_securities_issuer_id", table_name="securities")
    op.drop_index("idx_issuers_cvm_code", table_name="issuers")

    op.drop_table("restatement_events")
    op.drop_table("computed_metrics")
    op.drop_table("statement_lines")
    op.drop_table("filings")
    op.drop_table("securities")
    op.drop_table("issuers")
    op.drop_table("raw_source_files")
    op.drop_table("raw_source_batches")

    for name in ["period_type", "scope_type", "statement_type", "filing_status", "batch_status", "filing_type", "source_provider"]:
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
