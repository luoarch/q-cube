"""Magic Formula ranking strategies.

Three variants:
  - magic_formula_original: Greenblatt's original EY + ROC ranking
  - magic_formula_brazil: Original + B3-specific filters (sector, liquidity, EBIT)
  - magic_formula_hybrid: Brazil + quality overlay (leverage + cash conversion)
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from q3_shared_models.entities import Asset, FinancialStatement

logger = logging.getLogger(__name__)

USE_CANONICAL_FUNDAMENTALS = os.getenv("USE_CANONICAL_FUNDAMENTALS", "true").lower() in ("true", "1", "yes")

# --- Brazil filters ---
EXCLUDED_SECTORS = {"financeiro", "utilidade pública"}
MIN_AVG_DAILY_VOLUME = Decimal("1_000_000")
MIN_MARKET_CAP = Decimal("500_000_000")

# --- Hybrid weights ---
WEIGHT_CORE = 0.75
WEIGHT_QUALITY = 0.25


@dataclass
class RankedAsset:
    ticker: str
    name: str
    sector: str | None
    earnings_yield: float | None
    return_on_capital: float | None
    combined_rank: int
    score_details: dict[str, float]


def _rank_ascending(values: list[tuple[int, float | None]]) -> dict[int, int]:
    """Rank items ascending (lower value = better rank). None gets worst rank."""
    sortable = [(idx, v if v is not None else float("inf")) for idx, v in values]
    sortable.sort(key=lambda x: x[1])
    return {idx: rank + 1 for rank, (idx, _) in enumerate(sortable)}


def _rank_descending(values: list[tuple[int, float | None]]) -> dict[int, int]:
    """Rank items descending (higher value = better rank). None gets worst rank."""
    sortable = [(idx, v if v is not None else float("-inf")) for idx, v in values]
    sortable.sort(key=lambda x: x[1], reverse=True)
    return {idx: rank + 1 for rank, (idx, _) in enumerate(sortable)}


def _safe_div(numerator: float | Decimal | None, denominator: float | Decimal | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(Decimal(str(numerator)) / Decimal(str(denominator)))


def _fetch_latest_fundamentals(
    session: Session,
    tenant_id: uuid.UUID,
) -> list[tuple[Asset, FinancialStatement]]:
    """Fetch assets joined with their most recent financial statement."""
    latest_subq = (
        select(
            FinancialStatement.asset_id,
            FinancialStatement.period_date,
        )
        .where(FinancialStatement.tenant_id == tenant_id)
        .distinct(FinancialStatement.asset_id)
        .order_by(FinancialStatement.asset_id, FinancialStatement.period_date.desc())
        .subquery()
    )

    rows = session.execute(
        select(Asset, FinancialStatement)
        .join(FinancialStatement, FinancialStatement.asset_id == Asset.id)
        .join(
            latest_subq,
            (FinancialStatement.asset_id == latest_subq.c.asset_id)
            & (FinancialStatement.period_date == latest_subq.c.period_date),
        )
        .where(
            Asset.tenant_id == tenant_id,
            Asset.is_active.is_(True),
        )
    ).all()

    return [(row[0], row[1]) for row in rows]


@dataclass
class _CompatAsset:
    """Lightweight stand-in for Asset when reading from canonical view."""
    ticker: str
    name: str
    sector: str | None
    is_active: bool = True


@dataclass
class _CompatFS:
    """Lightweight stand-in for FinancialStatement when reading from canonical view."""
    ebit: Decimal | None = None
    enterprise_value: Decimal | None = None
    net_working_capital: Decimal | None = None
    fixed_assets: Decimal | None = None
    roic: Decimal | None = None
    roe: Decimal | None = None
    net_debt: Decimal | None = None
    ebitda: Decimal | None = None
    net_margin: Decimal | None = None
    gross_margin: Decimal | None = None
    earnings_yield: Decimal | None = None
    debt_to_ebitda: Decimal | None = None
    cash_conversion: Decimal | None = None
    market_cap: Decimal | None = None
    avg_daily_volume: Decimal | None = None


def _fetch_latest_fundamentals_v2(
    session: Session,
    tenant_id: uuid.UUID,
) -> list[tuple[_CompatAsset, _CompatFS]]:
    """Fetch fundamentals from the canonical v_financial_statements_compat view.

    tenant_id is accepted for interface compatibility but not used — fundamentals
    data is global (not tenant-scoped).
    """
    sql = text("""
        SELECT ticker, name, sector,
               ebit, enterprise_value, net_working_capital, fixed_assets,
               roic, net_debt, ebitda, net_margin, gross_margin,
               earnings_yield,
               market_cap, avg_daily_volume
        FROM v_financial_statements_compat
    """)

    rows = session.execute(sql).all()
    results: list[tuple[_CompatAsset, _CompatFS]] = []

    for row in rows:
        asset = _CompatAsset(
            ticker=row.ticker,
            name=row.name or "",
            sector=row.sector,
        )
        _dec = lambda v: Decimal(str(v)) if v is not None else None
        net_debt = _dec(row.net_debt)
        ebitda = _dec(row.ebitda)
        fs = _CompatFS(
            ebit=_dec(row.ebit),
            enterprise_value=_dec(row.enterprise_value),
            net_working_capital=_dec(row.net_working_capital),
            fixed_assets=_dec(row.fixed_assets),
            roic=_dec(row.roic),
            roe=None,
            net_debt=net_debt,
            ebitda=ebitda,
            net_margin=_dec(row.net_margin),
            gross_margin=_dec(row.gross_margin),
            earnings_yield=_dec(row.earnings_yield),
            debt_to_ebitda=Decimal(str(float(net_debt) / float(ebitda))) if net_debt is not None and ebitda and ebitda != 0 else None,
            cash_conversion=None,
            market_cap=_dec(row.market_cap),
            avg_daily_volume=_dec(row.avg_daily_volume),
        )
        results.append((asset, fs))

    logger.info("canonical view returned %d rows (tenant_id=%s ignored)", len(results), tenant_id)
    return results


def _compute_ey_roc(
    fs: FinancialStatement | _CompatFS,
) -> tuple[float | None, float | None]:
    # Prefer pre-computed earnings_yield from computed_metrics (via compat view)
    if hasattr(fs, "earnings_yield") and fs.earnings_yield is not None:
        ey = float(fs.earnings_yield)
    else:
        # Try enterprise_value first, then approximate EV = market_cap + net_debt
        ev = fs.enterprise_value
        if ev is None and hasattr(fs, "market_cap") and fs.market_cap is not None:
            net_debt = Decimal(str(fs.net_debt)) if fs.net_debt is not None else Decimal(0)
            ev = Decimal(str(fs.market_cap)) + net_debt
        ey = _safe_div(fs.ebit, ev)
    nwc = Decimal(str(fs.net_working_capital)) if fs.net_working_capital is not None else Decimal(0)
    fa = Decimal(str(fs.fixed_assets)) if fs.fixed_assets is not None else Decimal(0)
    capital = nwc + fa
    roc = _safe_div(fs.ebit, capital) if capital else None
    return ey, roc


def _fetch_data(session: Session, tenant_id: uuid.UUID) -> list[tuple]:
    """Dispatch to canonical view or legacy tables based on feature flag."""
    if USE_CANONICAL_FUNDAMENTALS:
        return _fetch_latest_fundamentals_v2(session, tenant_id)
    return _fetch_latest_fundamentals(session, tenant_id)


def run_magic_formula_original(
    session: Session,
    tenant_id: uuid.UUID,
) -> list[RankedAsset]:
    """Greenblatt's original Magic Formula: Rank(EY) + Rank(ROC)."""
    data = _fetch_data(session, tenant_id)
    if not data:
        return []

    items: list[tuple[int, Asset, FinancialStatement, float | None, float | None]] = []
    for i, (asset, fs) in enumerate(data):
        ey, roc = _compute_ey_roc(fs)
        items.append((i, asset, fs, ey, roc))

    ey_ranks = _rank_descending([(i, ey) for i, _, _, ey, _ in items])
    roc_ranks = _rank_descending([(i, roc) for i, _, _, _, roc in items])

    results: list[RankedAsset] = []
    for i, asset, _fs, ey, roc in items:
        combined = ey_ranks[i] + roc_ranks[i]
        results.append(RankedAsset(
            ticker=asset.ticker,
            name=asset.name,
            sector=asset.sector,
            earnings_yield=ey,
            return_on_capital=roc,
            combined_rank=combined,
            score_details={
                "ey_rank": ey_ranks[i],
                "roc_rank": roc_ranks[i],
            },
        ))

    results.sort(key=lambda r: r.combined_rank)
    for final_rank, r in enumerate(results, 1):
        r.combined_rank = final_rank

    return results


def run_magic_formula_brazil(
    session: Session,
    tenant_id: uuid.UUID,
) -> list[RankedAsset]:
    """Magic Formula with B3-specific filters.

    Filters:
      - Exclude financials and utilities sectors
      - Minimum average daily volume (R$ 1M)
      - Minimum market cap (R$ 500M)
      - Positive EBIT
    """
    data = _fetch_data(session, tenant_id)
    if not data:
        return []

    filtered: list[tuple[int, Asset, FinancialStatement, float | None, float | None]] = []
    idx = 0
    for asset, fs in data:
        if asset.sector and asset.sector.lower() in EXCLUDED_SECTORS:
            continue
        if fs.avg_daily_volume is not None and fs.avg_daily_volume < MIN_AVG_DAILY_VOLUME:
            continue
        if fs.market_cap is not None and fs.market_cap < MIN_MARKET_CAP:
            continue
        if fs.ebit is None or fs.ebit <= 0:
            continue

        ey, roc = _compute_ey_roc(fs)
        filtered.append((idx, asset, fs, ey, roc))
        idx += 1

    if not filtered:
        return []

    ey_ranks = _rank_descending([(i, ey) for i, _, _, ey, _ in filtered])
    roc_ranks = _rank_descending([(i, roc) for i, _, _, _, roc in filtered])

    results: list[RankedAsset] = []
    for i, asset, _fs, ey, roc in filtered:
        combined = ey_ranks[i] + roc_ranks[i]
        results.append(RankedAsset(
            ticker=asset.ticker,
            name=asset.name,
            sector=asset.sector,
            earnings_yield=ey,
            return_on_capital=roc,
            combined_rank=combined,
            score_details={
                "ey_rank": ey_ranks[i],
                "roc_rank": roc_ranks[i],
            },
        ))

    results.sort(key=lambda r: r.combined_rank)
    for final_rank, r in enumerate(results, 1):
        r.combined_rank = final_rank

    return results


def _rank_percentile(ranks: dict[int, int], n: int) -> dict[int, float]:
    """Convert ordinal ranks to percentiles in [0, 1]. Lower percentile = better."""
    return {idx: rank / n for idx, rank in ranks.items()}


def run_magic_formula_hybrid(
    session: Session,
    tenant_id: uuid.UUID,
) -> list[RankedAsset]:
    """Magic Formula + Quality Overlay.

    Core (75% of score, equal weight within):
      - Value: EY rank percentile (descending)
      - Profitability: ROC rank percentile (descending)

    Quality overlay (25% of score, equal weight within):
      - Leverage: debt_to_ebitda rank (ascending = lower is better)
      - Cash conversion: CFO/NI rank (descending = higher is better)

    If no quality signals available for an asset: final_score = core_score.

    Brazil gates (filters, not factors):
      - Exclude financials & utilities
      - Min avg daily volume R$1M
      - Min market cap R$500M
      - EBIT > 0
    """
    data = _fetch_data(session, tenant_id)
    if not data:
        return []

    # 1. Apply Brazil gates
    filtered: list[tuple[int, _CompatAsset | Asset, _CompatFS | FinancialStatement, float | None, float | None]] = []
    fs_map: dict[int, _CompatFS | FinancialStatement] = {}
    idx = 0
    for asset, fs in data:
        if asset.sector and asset.sector.lower() in EXCLUDED_SECTORS:
            continue
        if fs.avg_daily_volume is not None and fs.avg_daily_volume < MIN_AVG_DAILY_VOLUME:
            continue
        if fs.market_cap is not None and fs.market_cap < MIN_MARKET_CAP:
            continue
        if fs.ebit is None or fs.ebit <= 0:
            continue

        ey, roc = _compute_ey_roc(fs)
        filtered.append((idx, asset, fs, ey, roc))
        fs_map[idx] = fs
        idx += 1

    if not filtered:
        return []

    n = len(filtered)

    # 2. Core ranks (descending = higher is better)
    ey_ranks = _rank_descending([(i, ey) for i, _, _, ey, _ in filtered])
    roc_ranks = _rank_descending([(i, roc) for i, _, _, _, roc in filtered])

    ey_pct = _rank_percentile(ey_ranks, n)
    roc_pct = _rank_percentile(roc_ranks, n)

    # 3. Quality signal ranks
    # debt_to_ebitda: use pre-computed metric if available, else derive from net_debt/ebitda
    debt_ebitda_values: list[tuple[int, float | None]] = []
    for i, _, fs, _, _ in filtered:
        if hasattr(fs, "debt_to_ebitda") and fs.debt_to_ebitda is not None:
            debt_ebitda_values.append((i, float(fs.debt_to_ebitda)))
        else:
            debt_ebitda_values.append((i, _safe_div(fs.net_debt, fs.ebitda)))

    # cash_conversion: pre-computed metric
    cash_conv_values: list[tuple[int, float | None]] = []
    for i, _, fs, _, _ in filtered:
        val = getattr(fs, "cash_conversion", None)
        cash_conv_values.append((i, float(val) if val is not None else None))

    debt_ebitda_ranks = _rank_ascending(debt_ebitda_values)
    cash_conv_ranks = _rank_descending(cash_conv_values)

    debt_ebitda_pct = _rank_percentile(debt_ebitda_ranks, n)
    cash_conv_pct = _rank_percentile(cash_conv_ranks, n)

    # 4. Compute final scores
    results: list[RankedAsset] = []
    for i, asset, _fs, ey, roc in filtered:
        core_score = 0.5 * ey_pct[i] + 0.5 * roc_pct[i]

        # Collect available quality signals per asset
        quality_signals: list[float] = []
        fs_i = fs_map[i]

        # debt_to_ebitda available?
        has_dte = (
            (hasattr(fs_i, "debt_to_ebitda") and fs_i.debt_to_ebitda is not None)
            or (fs_i.net_debt is not None and fs_i.ebitda is not None and fs_i.ebitda != 0)
        )
        if has_dte:
            quality_signals.append(debt_ebitda_pct[i])

        # cash_conversion available?
        if getattr(fs_i, "cash_conversion", None) is not None:
            quality_signals.append(cash_conv_pct[i])

        if quality_signals:
            quality_score = sum(quality_signals) / len(quality_signals)
            final_score = WEIGHT_CORE * core_score + WEIGHT_QUALITY * quality_score
        else:
            final_score = core_score

        results.append(RankedAsset(
            ticker=asset.ticker,
            name=asset.name,
            sector=asset.sector,
            earnings_yield=ey,
            return_on_capital=roc,
            combined_rank=0,
            score_details={
                "ey_rank": ey_ranks[i],
                "roc_rank": roc_ranks[i],
                "core_score": round(core_score, 6),
                "debt_ebitda_rank": debt_ebitda_ranks[i],
                "cash_conv_rank": cash_conv_ranks[i],
                "quality_signals": len(quality_signals),
                "final_score": round(final_score, 6),
            },
        ))

    results.sort(key=lambda r: r.score_details["final_score"])
    for final_rank, r in enumerate(results, 1):
        r.combined_rank = final_rank

    return results


STRATEGY_RUNNERS = {
    "magic_formula_original": run_magic_formula_original,
    "magic_formula_brazil": run_magic_formula_brazil,
    "magic_formula_hybrid": run_magic_formula_hybrid,
}


def run_strategy(
    session: Session,
    tenant_id: uuid.UUID,
    strategy: str,
    as_of_date: date | None = None,
) -> list[dict[str, object]]:
    """Execute a strategy and return serializable results.

    When as_of_date is provided, uses point-in-time data for survivorship-
    bias-free ranking (used by the backtest engine).
    """
    if as_of_date is not None:
        from q3_quant_engine.data.pit_data import (
            fetch_eligible_universe_pit,
            fetch_fundamentals_pit,
        )
        from q3_quant_engine.backtest.engine import _rank_pit_data

        fundamentals = fetch_fundamentals_pit(session, as_of_date)
        universe = fetch_eligible_universe_pit(session, as_of_date)
        fundamentals = [(a, fs) for a, fs in fundamentals if a.ticker in universe]
        ranked = _rank_pit_data(fundamentals, strategy)
    else:
        runner = STRATEGY_RUNNERS.get(strategy)
        if runner is None:
            raise ValueError(f"Unknown strategy: {strategy}")
        ranked = runner(session, tenant_id)

    logger.info("strategy=%s tenant=%s ranked=%d assets as_of=%s", strategy, tenant_id, len(ranked), as_of_date)

    return [
        {
            "rank": r.combined_rank,
            "ticker": r.ticker,
            "name": r.name,
            "sector": r.sector,
            "earningsYield": r.earnings_yield,
            "returnOnCapital": r.return_on_capital,
            "scoreDetails": r.score_details,
        }
        for r in ranked
    ]
