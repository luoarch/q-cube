"""RefinerEngine — orchestrates loading, scoring, flags, and persistence for Top N."""

from __future__ import annotations

import logging
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_quant_engine.refiner.classification import classify_issuer
from q3_quant_engine.refiner.completeness import assess_completeness
from q3_quant_engine.refiner.data_loader import (
    get_issuer_for_ticker,
    load_multi_period_data,
)
from q3_quant_engine.refiner.flags import detect_flags
from q3_quant_engine.refiner.scoring import (
    score_capital_discipline,
    score_earnings_quality,
    score_operating_consistency,
    score_safety,
)
from q3_quant_engine.refiner.types import (
    SCORE_RELIABILITY_UNAVAILABLE,
    DataCompleteness,
    RefinementResult,
)

logger = logging.getLogger(__name__)

FORMULA_VERSION = 1
WEIGHTS_VERSION = 1

# Block weights
W_EARNINGS_QUALITY = 0.25
W_SAFETY = 0.25
W_OPERATING_CONSISTENCY = 0.25
W_CAPITAL_DISCIPLINE = 0.25

# Blending: base vs refinement
W_BASE = 0.85
W_REFINE = 0.15


class RefinerEngine:
    def __init__(self, session: Session) -> None:
        self._session = session

    def refine(
        self,
        run_id: UUID,
        tenant_id: UUID,
        top_n: int = 30,
        ranked_assets: list[dict] | None = None,
    ) -> list[RefinementResult]:
        """Run refinement on top N assets from a strategy run.

        Args:
            run_id: The strategy run ID.
            tenant_id: Tenant ID for scoping.
            top_n: Number of top-ranked assets to refine.
            ranked_assets: Pre-loaded ranked assets list. If None, loaded from strategy_runs.result_json.
        """
        if ranked_assets is None:
            ranked_assets = self._load_ranked_assets(run_id, tenant_id)

        if not ranked_assets:
            logger.warning("No ranked assets for run=%s", run_id)
            return []

        top_assets = ranked_assets[:top_n]
        logger.info("Refining top %d of %d assets for run=%s", len(top_assets), len(ranked_assets), run_id)

        results: list[RefinementResult] = []

        for asset_data in top_assets:
            ticker = asset_data.get("ticker", "")
            base_rank = asset_data.get("rank", 0)

            result = self._refine_single(ticker, base_rank)
            if result is not None:
                results.append(result)

        # Compute adjusted scores and ranks
        results = self._compute_adjusted_ranks(results, len(ranked_assets))

        # Persist
        self._persist_results(run_id, tenant_id, results)

        logger.info("Refined %d assets for run=%s", len(results), run_id)
        return results

    def _load_ranked_assets(self, run_id: UUID, tenant_id: UUID) -> list[dict]:
        from q3_shared_models.entities import StrategyRun

        run = self._session.execute(
            select(StrategyRun).where(
                StrategyRun.id == run_id,
                StrategyRun.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()

        if run is None or run.result_json is None:
            return []

        return run.result_json.get("rankedAssets", [])

    def _refine_single(self, ticker: str, base_rank: int) -> RefinementResult | None:
        issuer_info = get_issuer_for_ticker(self._session, ticker)
        if issuer_info is None:
            logger.debug("Ticker %s not found in securities table, skipping", ticker)
            return None

        issuer_id, sector, subsector = issuer_info
        classification = classify_issuer(sector, subsector)

        data, periods = load_multi_period_data(self._session, issuer_id, n_periods=3, period_type="annual")

        if periods == 0:
            completeness = DataCompleteness(0, 0, 0, 0.0)
            return RefinementResult(
                issuer_id=str(issuer_id),
                ticker=ticker,
                base_rank=base_rank,
                earnings_quality_score=0.5,
                safety_score=0.5,
                operating_consistency_score=0.5,
                capital_discipline_score=0.5,
                refinement_score=0.5,
                adjusted_score=0.0,
                adjusted_rank=0,
                flags={"red": [], "strength": []},
                trend_data={},
                scoring_details={"note": "no_data"},
                data_completeness=completeness,
                score_reliability=SCORE_RELIABILITY_UNAVAILABLE,
                issuer_classification=classification,
            )

        # Flatten data for completeness check
        flat: dict[str, list[float | None]] = {}
        for key, pvs in data.items():
            flat[key] = [pv.value for pv in pvs]

        completeness, reliability = assess_completeness(flat, periods, classification)

        # Score all blocks
        eq_block = score_earnings_quality(data)
        safety_block = score_safety(data, classification)
        oc_block = score_operating_consistency(data)
        cd_block = score_capital_discipline(data)

        refinement_score = (
            W_EARNINGS_QUALITY * eq_block.score
            + W_SAFETY * safety_block.score
            + W_OPERATING_CONSISTENCY * oc_block.score
            + W_CAPITAL_DISCIPLINE * cd_block.score
        )

        # Detect flags
        flag_list = detect_flags(data, classification)
        flags = {
            "red": [f.code for f in flag_list if f.category == "red"],
            "strength": [f.code for f in flag_list if f.category == "strength"],
        }

        # Serialize trend data (keep only the keys with actual data)
        trend_data = {k: v for k, v in data.items() if v}

        scoring_details = {
            "earnings_quality": eq_block.components,
            "safety": safety_block.components,
            "operating_consistency": oc_block.components,
            "capital_discipline": cd_block.components,
        }

        return RefinementResult(
            issuer_id=str(issuer_id),
            ticker=ticker,
            base_rank=base_rank,
            earnings_quality_score=eq_block.score,
            safety_score=safety_block.score,
            operating_consistency_score=oc_block.score,
            capital_discipline_score=cd_block.score,
            refinement_score=round(refinement_score, 4),
            adjusted_score=0.0,  # computed later
            adjusted_rank=0,     # computed later
            flags=flags,
            trend_data=trend_data,
            scoring_details=scoring_details,
            data_completeness=completeness,
            score_reliability=reliability,
            issuer_classification=classification,
        )

    def _compute_adjusted_ranks(
        self,
        results: list[RefinementResult],
        total_ranked: int,
    ) -> list[RefinementResult]:
        if not results:
            return results

        n = len(results)

        # Base percentile: rank / total (lower = better, but we invert so higher percentile = better)
        for r in results:
            r_base_pct = 1.0 - (r.base_rank / max(total_ranked, 1))
            # Refinement percentile within the top-N
            r._base_pct = r_base_pct  # type: ignore[attr-defined]

        # Rank refinement scores to get percentiles
        sorted_by_refine = sorted(results, key=lambda r: r.refinement_score, reverse=True)
        for i, r in enumerate(sorted_by_refine):
            r._refine_pct = 1.0 - (i / max(n, 1))  # type: ignore[attr-defined]

        # Adjusted score
        for r in results:
            r.adjusted_score = round(
                W_BASE * r._base_pct + W_REFINE * r._refine_pct, 6  # type: ignore[attr-defined]
            )

        # Rank by adjusted score (descending)
        sorted_by_adjusted = sorted(results, key=lambda r: r.adjusted_score, reverse=True)
        for rank, r in enumerate(sorted_by_adjusted, 1):
            r.adjusted_rank = rank

        # Clean up temp attrs
        for r in results:
            if hasattr(r, "_base_pct"):
                del r._base_pct  # type: ignore[attr-defined]
            if hasattr(r, "_refine_pct"):
                del r._refine_pct  # type: ignore[attr-defined]

        return results

    def _persist_results(
        self,
        run_id: UUID,
        tenant_id: UUID,
        results: list[RefinementResult],
    ) -> None:
        """Persist refinement results to the database."""
        from q3_shared_models.entities import RefinementResultModel

        for r in results:
            # Serialize trend data to JSON-safe format
            trend_json: dict = {}
            for key, pvs in r.trend_data.items():
                trend_json[key] = [
                    {"referenceDate": str(pv.reference_date), "value": pv.value}
                    for pv in pvs
                ]

            completeness_json = {
                "periodsAvailable": r.data_completeness.periods_available,
                "metricsAvailable": r.data_completeness.metrics_available,
                "metricsExpected": r.data_completeness.metrics_expected,
                "completenessRatio": r.data_completeness.completeness_ratio,
                "missingCritical": r.data_completeness.missing_critical,
                "proxyUsed": r.data_completeness.proxy_used,
            }

            row = RefinementResultModel(
                id=uuid.uuid4(),
                strategy_run_id=run_id,
                tenant_id=tenant_id,
                issuer_id=UUID(r.issuer_id),
                ticker=r.ticker,
                base_rank=r.base_rank,
                earnings_quality_score=r.earnings_quality_score,
                safety_score=r.safety_score,
                operating_consistency_score=r.operating_consistency_score,
                capital_discipline_score=r.capital_discipline_score,
                refinement_score=r.refinement_score,
                adjusted_score=r.adjusted_score,
                adjusted_rank=r.adjusted_rank,
                flags_json=r.flags,
                trend_data_json=trend_json,
                scoring_details_json=r.scoring_details,
                data_completeness_json=completeness_json,
                score_reliability=r.score_reliability,
                issuer_classification=r.issuer_classification,
                formula_version=r.formula_version,
                weights_version=r.weights_version,
            )
            self._session.add(row)

        self._session.flush()
        logger.info("Persisted %d refinement results for run=%s", len(results), run_id)
