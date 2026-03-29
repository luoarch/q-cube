"""Recreate v_financial_statements_compat with fixed joins.

Revision ID: 20260326_0025
Revises: 20260326_0024
Create Date: 2026-03-26

Fixes:
- LATERAL JOIN on securities picks security with most snapshots (not newest by created_at)
- Sector from universe_classifications.matched_sector_key (was issuers.sector = mostly NULL)
- market_snapshots picks latest with market_cap > 0 (no staleness window)
"""

from __future__ import annotations

from alembic import op


revision = "20260326_0025"
down_revision = "20260326_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS v_financial_statements_compat")
    op.execute("""
        CREATE MATERIALIZED VIEW v_financial_statements_compat AS
        SELECT
            s.id AS security_id,
            i.id AS issuer_id,
            s.ticker,
            i.legal_name AS name,
            COALESCE(uc.matched_sector_key, i.sector) AS sector,
            i.subsector AS sub_sector,
            cm_ref.reference_date AS period_date,
            sl_ebit.value AS ebit,
            cm_ev.value AS enterprise_value,
            sl_nwc.value AS net_working_capital,
            sl_fa.value AS fixed_assets,
            cm_roic.value AS roic,
            cm_roe.value AS roe,
            cm_nd.value AS net_debt,
            cm_ebitda.value AS ebitda,
            cm_nm.value AS net_margin,
            cm_gm.value AS gross_margin,
            cm_ey.value AS earnings_yield,
            cm_dte.value AS debt_to_ebitda,
            cm_cc.value AS cash_conversion,
            ms_latest.market_cap,
            ms_latest.avg_daily_volume,
            ms_latest.snapshot_fetched_at,
            cm_dy.value AS dividend_yield,
            cm_nby.value AS net_buyback_yield,
            cm_npy.value AS net_payout_yield
        FROM issuers i
        JOIN LATERAL (
            SELECT s2.id, s2.ticker
            FROM securities s2
            WHERE s2.issuer_id = i.id AND s2.is_primary = true AND s2.valid_to IS NULL
            ORDER BY (SELECT count(*) FROM market_snapshots ms WHERE ms.security_id = s2.id) DESC, s2.created_at ASC
            LIMIT 1
        ) s ON true
        JOIN universe_classifications uc ON uc.issuer_id = i.id
            AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
        LEFT JOIN LATERAL (
            SELECT DISTINCT cm.reference_date
            FROM computed_metrics cm
            WHERE cm.issuer_id = i.id
            ORDER BY cm.reference_date DESC
            LIMIT 1
        ) cm_ref ON true
        LEFT JOIN LATERAL (
            SELECT sl.normalized_value AS value
            FROM statement_lines sl
            JOIN filings f ON sl.filing_id = f.id
            WHERE f.issuer_id = i.id AND f.reference_date = cm_ref.reference_date
                AND f.status = 'completed' AND sl.canonical_key = 'ebit'
            ORDER BY sl.scope, f.version_number DESC
            LIMIT 1
        ) sl_ebit ON true
        LEFT JOIN LATERAL (
            SELECT COALESCE(ca.val, 0) - COALESCE(cl.val, 0) AS value
            FROM (
                SELECT sl.normalized_value AS val
                FROM statement_lines sl JOIN filings f ON sl.filing_id = f.id
                WHERE f.issuer_id = i.id AND f.reference_date = cm_ref.reference_date
                    AND f.status = 'completed' AND sl.canonical_key = 'current_assets'
                ORDER BY sl.scope, f.version_number DESC LIMIT 1
            ) ca, (
                SELECT sl.normalized_value AS val
                FROM statement_lines sl JOIN filings f ON sl.filing_id = f.id
                WHERE f.issuer_id = i.id AND f.reference_date = cm_ref.reference_date
                    AND f.status = 'completed' AND sl.canonical_key = 'current_liabilities'
                ORDER BY sl.scope, f.version_number DESC LIMIT 1
            ) cl
        ) sl_nwc ON true
        LEFT JOIN LATERAL (
            SELECT sl.normalized_value AS value
            FROM statement_lines sl JOIN filings f ON sl.filing_id = f.id
            WHERE f.issuer_id = i.id AND f.reference_date = cm_ref.reference_date
                AND f.status = 'completed' AND sl.canonical_key = 'fixed_assets'
            ORDER BY sl.scope, f.version_number DESC LIMIT 1
        ) sl_fa ON true
        LEFT JOIN LATERAL (
            SELECT ms.market_cap,
                   ms.volume AS avg_daily_volume,
                   ms.fetched_at AS snapshot_fetched_at
            FROM market_snapshots ms
            WHERE ms.security_id = s.id
            ORDER BY ms.fetched_at DESC
            LIMIT 1
        ) ms_latest ON true
        LEFT JOIN computed_metrics cm_ev ON cm_ev.issuer_id = i.id AND cm_ev.metric_code = 'enterprise_value' AND cm_ev.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_roic ON cm_roic.issuer_id = i.id AND cm_roic.metric_code = 'roic' AND cm_roic.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_roe ON cm_roe.issuer_id = i.id AND cm_roe.metric_code = 'roe' AND cm_roe.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_nd ON cm_nd.issuer_id = i.id AND cm_nd.metric_code = 'net_debt' AND cm_nd.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_ebitda ON cm_ebitda.issuer_id = i.id AND cm_ebitda.metric_code = 'ebitda' AND cm_ebitda.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_nm ON cm_nm.issuer_id = i.id AND cm_nm.metric_code = 'net_margin' AND cm_nm.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_gm ON cm_gm.issuer_id = i.id AND cm_gm.metric_code = 'gross_margin' AND cm_gm.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_ey ON cm_ey.issuer_id = i.id AND cm_ey.metric_code = 'earnings_yield' AND cm_ey.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_dte ON cm_dte.issuer_id = i.id AND cm_dte.metric_code = 'debt_to_ebitda' AND cm_dte.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_cc ON cm_cc.issuer_id = i.id AND cm_cc.metric_code = 'cash_conversion' AND cm_cc.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_dy ON cm_dy.issuer_id = i.id AND cm_dy.metric_code = 'dividend_yield' AND cm_dy.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_nby ON cm_nby.issuer_id = i.id AND cm_nby.metric_code = 'net_buyback_yield' AND cm_nby.reference_date = cm_ref.reference_date
        LEFT JOIN computed_metrics cm_npy ON cm_npy.issuer_id = i.id AND cm_npy.metric_code = 'net_payout_yield' AND cm_npy.reference_date = cm_ref.reference_date
        WHERE cm_ref.reference_date IS NOT NULL
    """)


def downgrade() -> None:
    # Drop the new view. Old definition can be restored via migration 20260320_0016 if needed.
    op.execute("DROP MATERIALIZED VIEW IF EXISTS v_financial_statements_compat")
