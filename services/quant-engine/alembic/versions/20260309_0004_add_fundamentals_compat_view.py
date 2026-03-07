"""add fundamentals compatibility materialized view

Revision ID: 20260309_0004
Revises: 20260308_0003
Create Date: 2026-03-09
"""

from __future__ import annotations

from alembic import op


revision = "20260309_0004"
down_revision = "20260308_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS v_financial_statements_compat AS
        SELECT
            s.id AS security_id,
            i.id AS issuer_id,
            s.ticker,
            i.legal_name AS name,
            i.sector,
            i.subsector AS sub_sector,
            cm_ref.reference_date AS period_date,
            sl_ebit.value AS ebit,
            cm_ev.value AS enterprise_value,
            sl_nwc.value AS net_working_capital,
            sl_fa.value AS fixed_assets,
            cm_roic.value AS roic,
            cm_nd.value AS net_debt,
            cm_ebitda.value AS ebitda,
            cm_nm.value AS net_margin,
            cm_gm.value AS gross_margin
        FROM issuers i
        JOIN securities s ON s.issuer_id = i.id AND s.is_primary = true
        LEFT JOIN LATERAL (
            SELECT DISTINCT reference_date
            FROM computed_metrics
            WHERE issuer_id = i.id
            ORDER BY reference_date DESC
            LIMIT 1
        ) cm_ref ON true
        -- ebit from statement_lines (canonical_key = 'ebit')
        LEFT JOIN LATERAL (
            SELECT sl.normalized_value AS value
            FROM statement_lines sl
            JOIN filings f ON sl.filing_id = f.id
            WHERE f.issuer_id = i.id
              AND f.reference_date = cm_ref.reference_date
              AND f.status = 'completed'
              AND sl.canonical_key = 'ebit'
            ORDER BY sl.scope ASC, f.version_number DESC
            LIMIT 1
        ) sl_ebit ON true
        -- net_working_capital = current_assets - current_liabilities (from statement_lines)
        LEFT JOIN LATERAL (
            SELECT (COALESCE(ca.val, 0) - COALESCE(cl.val, 0)) AS value
            FROM (
                SELECT sl.normalized_value AS val
                FROM statement_lines sl JOIN filings f ON sl.filing_id = f.id
                WHERE f.issuer_id = i.id AND f.reference_date = cm_ref.reference_date
                  AND f.status = 'completed' AND sl.canonical_key = 'current_assets'
                ORDER BY sl.scope ASC, f.version_number DESC LIMIT 1
            ) ca, (
                SELECT sl.normalized_value AS val
                FROM statement_lines sl JOIN filings f ON sl.filing_id = f.id
                WHERE f.issuer_id = i.id AND f.reference_date = cm_ref.reference_date
                  AND f.status = 'completed' AND sl.canonical_key = 'current_liabilities'
                ORDER BY sl.scope ASC, f.version_number DESC LIMIT 1
            ) cl
        ) sl_nwc ON true
        -- fixed_assets from statement_lines
        LEFT JOIN LATERAL (
            SELECT sl.normalized_value AS value
            FROM statement_lines sl
            JOIN filings f ON sl.filing_id = f.id
            WHERE f.issuer_id = i.id
              AND f.reference_date = cm_ref.reference_date
              AND f.status = 'completed'
              AND sl.canonical_key = 'fixed_assets'
            ORDER BY sl.scope ASC, f.version_number DESC
            LIMIT 1
        ) sl_fa ON true
        LEFT JOIN computed_metrics cm_ev
            ON cm_ev.issuer_id = i.id AND cm_ev.metric_code = 'enterprise_value'
            AND cm_ev.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_roic
            ON cm_roic.issuer_id = i.id AND cm_roic.metric_code = 'roic'
            AND cm_roic.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_nd
            ON cm_nd.issuer_id = i.id AND cm_nd.metric_code = 'net_debt'
            AND cm_nd.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_ebitda
            ON cm_ebitda.issuer_id = i.id AND cm_ebitda.metric_code = 'ebitda'
            AND cm_ebitda.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_nm
            ON cm_nm.issuer_id = i.id AND cm_nm.metric_code = 'net_margin'
            AND cm_nm.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_gm
            ON cm_gm.issuer_id = i.id AND cm_gm.metric_code = 'gross_margin'
            AND cm_gm.reference_date = cm_ref.reference_date
        WHERE cm_ref.reference_date IS NOT NULL
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_compat_view_security_date
        ON v_financial_statements_compat (security_id, period_date)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS v_financial_statements_compat")
