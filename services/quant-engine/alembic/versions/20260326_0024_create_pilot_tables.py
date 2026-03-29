"""MF-RUNTIME-01A — Pilot snapshot + forward returns tables.

Revision ID: 20260326_0024
Revises: 20260325_0023
Create Date: 2026-03-26

Creates:
- ranking_snapshots: daily capture of ranking state
- forward_returns: realized forward returns per snapshot/ticker/horizon
"""

from __future__ import annotations

from alembic import op


revision = "20260326_0024"
down_revision = "20260325_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE ranking_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date DATE NOT NULL,
            ticker VARCHAR NOT NULL,
            model_family VARCHAR NOT NULL,
            rank_within_model INTEGER NOT NULL,
            composite_score NUMERIC,
            investability_status VARCHAR NOT NULL,
            earnings_yield NUMERIC,
            return_on_capital NUMERIC,
            net_payout_yield NUMERIC,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT uq_ranking_snapshots_date_ticker
                UNIQUE (snapshot_date, ticker),
            CONSTRAINT chk_model_family
                CHECK (model_family IN ('NPY_ROC', 'EY_ROC')),
            CONSTRAINT chk_investability_status
                CHECK (investability_status IN ('fully_evaluated', 'partially_evaluated'))
        )
    """)

    op.execute("""
        CREATE INDEX ix_ranking_snapshots_date
            ON ranking_snapshots (snapshot_date)
    """)

    op.execute("""
        CREATE TABLE forward_returns (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date DATE NOT NULL,
            ticker VARCHAR NOT NULL,
            horizon VARCHAR NOT NULL,
            price_t0 NUMERIC,
            price_tn NUMERIC,
            return_value NUMERIC,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT uq_forward_returns_date_ticker_horizon
                UNIQUE (snapshot_date, ticker, horizon),
            CONSTRAINT chk_horizon
                CHECK (horizon IN ('1d', '5d', '21d'))
        )
    """)

    op.execute("""
        CREATE INDEX ix_forward_returns_date
            ON forward_returns (snapshot_date)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS forward_returns")
    op.execute("DROP TABLE IF EXISTS ranking_snapshots")
