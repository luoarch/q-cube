"""Split-Model Ranking API — SSOT (Plan 6).

GET /ranking returns two separate rankings:
  primaryRanking: NPY+ROC (fully_evaluated)
  secondaryRanking: EY+ROC (partially_evaluated)

No fallback. No cross-model ranking. No pagination (D1).
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter

from fastapi import APIRouter
from sqlalchemy import text

from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.strategies.ranking import (
    _fetch_data,
    _compute_ey_roc,
    _rank_descending,
    _rank_ascending,
    _rank_percentile,
    _safe_div,
    RankedAsset,
    WEIGHT_CORE,
    WEIGHT_QUALITY,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_GLOBAL_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _classify_missing(fs: object) -> list[str]:
    """Return cause-based missingData list. No redundant missing_npy (D3)."""
    missing = []
    if getattr(fs, "net_payout_yield", None) is None:
        # Determine root cause
        dy = getattr(fs, "dividend_yield", None)
        nby = getattr(fs, "net_buyback_yield", None)
        if dy is None:
            missing.append("missing_dividend_yield")
        if nby is None:
            missing.append("missing_nby")
        # If both DY and NBY exist but NPY still null — partial_financials
        if dy is not None and nby is not None:
            missing.append("partial_financials")
    return missing


def _rank_group(
    items: list[tuple[int, object, object, float | None, float | None]],
    fs_map: dict[int, object],
    *,
    use_npy: bool,
) -> list[dict]:
    """Rank a group of assets with a single model. No cross-model contamination."""
    if not items:
        return []

    n = len(items)

    # Value factor: NPY or EY depending on model
    if use_npy:
        value_values = [(i, float(getattr(fs_map[i], "net_payout_yield"))) for i, _, _, _, _ in items]
    else:
        value_values = [(i, ey) for i, _, _, ey, _ in items]

    roc_values = [(i, roc) for i, _, _, _, roc in items]

    value_ranks = _rank_descending(value_values)
    roc_ranks = _rank_descending(roc_values)
    value_pct = _rank_percentile(value_ranks, n)
    roc_pct = _rank_percentile(roc_ranks, n)

    # Quality: debt + cash
    debt_ebitda_values = []
    cash_conv_values = []
    for i, _, fs, _, _ in items:
        if hasattr(fs, "debt_to_ebitda") and fs.debt_to_ebitda is not None:
            debt_ebitda_values.append((i, float(fs.debt_to_ebitda)))
        else:
            debt_ebitda_values.append((i, _safe_div(fs.net_debt, fs.ebitda)))
        val = getattr(fs, "cash_conversion", None)
        cash_conv_values.append((i, float(val) if val is not None else None))

    debt_ebitda_ranks = _rank_ascending(debt_ebitda_values)
    cash_conv_ranks = _rank_descending(cash_conv_values)
    debt_ebitda_pct = _rank_percentile(debt_ebitda_ranks, n)
    cash_conv_pct = _rank_percentile(cash_conv_ranks, n)

    ranked: list[tuple[float, int, object, float | None, float | None]] = []
    for i, asset, fs, ey, roc in items:
        core_score = 0.5 * value_pct[i] + 0.5 * roc_pct[i]

        quality_signals: list[float] = []
        has_dte = (
            (hasattr(fs, "debt_to_ebitda") and fs.debt_to_ebitda is not None)
            or (fs.net_debt is not None and fs.ebitda is not None and fs.ebitda != 0)
        )
        if has_dte:
            quality_signals.append(debt_ebitda_pct[i])
        if getattr(fs, "cash_conversion", None) is not None:
            quality_signals.append(cash_conv_pct[i])

        if quality_signals:
            quality_score = sum(quality_signals) / len(quality_signals)
            final_score = WEIGHT_CORE * core_score + WEIGHT_QUALITY * quality_score
        else:
            final_score = core_score

        ranked.append((final_score, i, asset, ey, roc))

    ranked.sort(key=lambda x: x[0])

    return [
        {
            "idx": i,
            "asset": asset,
            "ey": ey,
            "roc": roc,
            "score": round(score, 6),
            "rank": pos,
        }
        for pos, (score, i, asset, ey, roc) in enumerate(ranked, 1)
    ]


@router.get("/ranking")
def get_ranking() -> dict:
    """Split-model ranking. Two first-class outputs, no fallback."""
    with SessionLocal() as session:
        data = _fetch_data(session, _GLOBAL_TENANT)

        # Classify into primary (NPY) vs secondary (EY)
        primary_items = []
        secondary_items = []
        fs_map: dict[int, object] = {}
        missing_counter: Counter[str] = Counter()
        idx = 0

        for asset, fs in data:
            ey, roc = _compute_ey_roc(fs)
            npy = getattr(fs, "net_payout_yield", None)

            fs_map[idx] = fs

            if npy is not None:
                primary_items.append((idx, asset, fs, ey, roc))
            else:
                secondary_items.append((idx, asset, fs, ey, roc))
                for reason in _classify_missing(fs):
                    missing_counter[reason] += 1

            idx += 1

        # Rank each group independently
        primary_ranked = _rank_group(primary_items, fs_map, use_npy=True)
        secondary_ranked = _rank_group(secondary_items, fs_map, use_npy=False)

        # Build price map
        price_rows = session.execute(text("""
            SELECT DISTINCT ON (s.ticker)
                   s.ticker, ms.price, ms.market_cap, ms.volume
            FROM market_snapshots ms
            JOIN securities s ON s.id = ms.security_id
                AND s.is_primary = true AND s.valid_to IS NULL
            WHERE ms.market_cap IS NOT NULL AND ms.market_cap > 0
            ORDER BY s.ticker, ms.fetched_at DESC
        """)).fetchall()
        price_map = {
            r[0]: {"price": float(r[1]) if r[1] else None,
                   "mcap": float(r[2]) if r[2] else 0,
                   "vol": float(r[3]) if r[3] else 0}
            for r in price_rows
        }

    def _to_item(r: dict, model: str, status: str, missing: list[str]) -> dict:
        asset = r["asset"]
        ey = r["ey"] or 0
        roc = r["roc"] or 0
        npy_val = float(getattr(fs_map[r["idx"]], "net_payout_yield")) if model == "NPY_ROC" else None
        pm = price_map.get(asset.ticker, {})
        vol = pm.get("vol", 0)
        return {
            "ticker": asset.ticker,
            "name": asset.name,
            "sector": asset.sector or "Sem Setor",
            "modelFamily": model,
            "investabilityStatus": status,
            "rankWithinModel": r["rank"],
            "missingData": missing,
            "earningsYield": round(ey, 6),
            "returnOnCapital": round(roc, 6),
            "netPayoutYield": round(npy_val, 6) if npy_val is not None else None,
            "marketCap": pm.get("mcap", 0),
            "price": pm.get("price"),
            "change": None,
            "quality": "high" if roc >= 0.15 else "medium" if roc >= 0.08 else "low",
            "liquidity": "high" if vol >= 1_000_000 else "medium" if vol >= 100_000 else "low",
            "compositeScore": r["score"],
        }

    primary_out = [
        _to_item(r, "NPY_ROC", "fully_evaluated", [])
        for r in primary_ranked
    ]
    secondary_out = [
        _to_item(r, "EY_ROC", "partially_evaluated", _classify_missing(fs_map[r["idx"]]))
        for r in secondary_ranked
    ]

    logger.info("Split ranking: %d primary, %d secondary", len(primary_out), len(secondary_out))

    return {
        "primaryRanking": primary_out,
        "secondaryRanking": secondary_out,
        "summary": {
            "primaryCount": len(primary_out),
            "secondaryCount": len(secondary_out),
            "totalUniverse": len(primary_out) + len(secondary_out),
            "missingDataBreakdown": dict(missing_counter),
        },
    }
