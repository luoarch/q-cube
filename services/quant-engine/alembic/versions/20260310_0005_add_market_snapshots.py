"""add market_snapshots table + computed_metrics unique index + compat view update

Revision ID: 20260310_0005
Revises: 20260309_0004
Create Date: 2026-03-10
"""

from __future__ import annotations

from alembic import op


revision = "20260310_0005"
down_revision = "20260309_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create market_snapshots table
    op.execute("""
        CREATE TABLE market_snapshots (
            id UUID PRIMARY KEY,
            security_id UUID NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
            source source_provider NOT NULL,
            price NUMERIC,
            market_cap NUMERIC,
            volume NUMERIC,
            currency VARCHAR NOT NULL DEFAULT 'BRL',
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            raw_json JSONB,
            CONSTRAINT uq_market_snapshots_security_fetched UNIQUE (security_id, fetched_at)
        )
    """)
    op.execute("CREATE INDEX ix_market_snapshots_security_id ON market_snapshots (security_id)")
    op.execute("CREATE INDEX ix_market_snapshots_fetched_at ON market_snapshots (fetched_at DESC)")

    # 2. Unique constraint on computed_metrics to prevent duplicates.
    # Assumes 1 active metric value per (issuer, code, period_type, date).
    # Market-dependent metrics (EV, earnings yield) use the primary security's
    # latest snapshot — issuer-level, not per-security.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_computed_metrics_issuer_code_period_date
        ON computed_metrics (issuer_id, metric_code, period_type, reference_date)
    """)

    # 3. Drop and recreate compat view with market_cap from snapshots
    op.execute("DROP MATERIALIZED VIEW IF EXISTS v_financial_statements_compat")
    op.execute("""
        CREATE MATERIALIZED VIEW v_financial_statements_compat AS
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
            cm_gm.value AS gross_margin,
            cm_ey.value AS earnings_yield,
            ms_latest.market_cap,
            ms_latest.avg_daily_volume,
            ms_latest.snapshot_fetched_at
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
        -- net_working_capital = current_assets - current_liabilities
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
        -- latest market snapshot (NULL if older than 7 days = stale)
        LEFT JOIN LATERAL (
            SELECT
                CASE WHEN ms.fetched_at >= now() - INTERVAL '7 days'
                     THEN ms.market_cap END AS market_cap,
                CASE WHEN ms.fetched_at >= now() - INTERVAL '7 days'
                     THEN ms.volume END AS avg_daily_volume,
                ms.fetched_at AS snapshot_fetched_at
            FROM market_snapshots ms
            WHERE ms.security_id = s.id
            ORDER BY ms.fetched_at DESC
            LIMIT 1
        ) ms_latest ON true
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
        LEFT JOIN computed_metrics cm_ey
            ON cm_ey.issuer_id = i.id AND cm_ey.metric_code = 'earnings_yield'
            AND cm_ey.reference_date = cm_ref.reference_date
        WHERE cm_ref.reference_date IS NOT NULL
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_compat_view_security_date
        ON v_financial_statements_compat (security_id, period_date)
    """)


def downgrade() -> None:
    # Restore original compat view (without market_cap)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS v_financial_statements_compat")
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

    op.execute("DROP INDEX IF EXISTS uq_computed_metrics_issuer_code_period_date")
    op.execute("DROP TABLE IF EXISTS market_snapshots")
