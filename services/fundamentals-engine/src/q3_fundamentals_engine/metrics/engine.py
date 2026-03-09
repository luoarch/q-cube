from __future__ import annotations

import logging
import uuid
from datetime import date

from q3_shared_models.entities import (
    ComputedMetric,
    Filing,
    FilingStatus,
    PeriodType,
    StatementLine,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_fundamentals_engine.metrics.base import IndicatorStrategy, MetricResult
from q3_fundamentals_engine.metrics.earnings_yield import EarningsYieldStrategy
from q3_fundamentals_engine.metrics.ebitda import EbitdaStrategy
from q3_fundamentals_engine.metrics.enterprise_value import EvStrategy
from q3_fundamentals_engine.metrics.margins import (
    EbitMarginStrategy,
    GrossMarginStrategy,
    NetMarginStrategy,
)
from q3_fundamentals_engine.metrics.net_debt import NetDebtStrategy
from q3_fundamentals_engine.metrics.roe import RoeStrategy
from q3_fundamentals_engine.metrics.roic import RoicStrategy
from q3_fundamentals_engine.metrics.cash_conversion import CashConversionStrategy
from q3_fundamentals_engine.metrics.debt_to_ebitda import DebtToEbitdaStrategy
from q3_fundamentals_engine.metrics.interest_coverage import InterestCoverageStrategy

logger = logging.getLogger(__name__)


class MetricsEngine:
    """Orchestrates derived-metric computation for a single issuer + reference date."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._strategies: list[IndicatorStrategy] = [
            EbitdaStrategy(),
            NetDebtStrategy(),
            RoicStrategy(),
            RoeStrategy(),
            EarningsYieldStrategy(),
            GrossMarginStrategy(),
            EbitMarginStrategy(),
            NetMarginStrategy(),
            EvStrategy(),
            CashConversionStrategy(),
            DebtToEbitdaStrategy(),
            InterestCoverageStrategy(),
        ]

    # Strategies that depend on market_cap (market data, not CVM filings)
    _MARKET_DEPENDENT_CODES = {"enterprise_value", "earnings_yield"}

    def compute_for_issuer(
        self,
        issuer_id: uuid.UUID,
        reference_date: date,
        *,
        market_cap: float | None = None,
        only_market_dependent: bool = False,
    ) -> list[ComputedMetric]:
        """Load statement lines, run all strategies, persist ComputedMetric rows.

        Args:
            only_market_dependent: When True, only run strategies that depend on
                market_cap (EV, earnings yield). Useful when only market data updated.
        """
        values, filing_ids = self._load_statement_values(issuer_id, reference_date)

        if not values:
            logger.info(
                "No statement values for issuer=%s date=%s; skipping",
                issuer_id,
                reference_date,
            )
            return []

        available_keys = set(values.keys())
        results: list[MetricResult] = []

        strategies = self._strategies
        if only_market_dependent:
            strategies = [
                s for s in self._strategies
                if isinstance(s, (EvStrategy, EarningsYieldStrategy))
            ]

        for strategy in strategies:
            if not strategy.supports(available_keys):
                continue
            result = strategy.compute(values, filing_ids, market_cap=market_cap)
            if result is not None:
                results.append(result)

        persisted: list[ComputedMetric] = []
        for r in results:
            metric = self._upsert_metric(
                issuer_id=issuer_id,
                metric_code=r.metric_code,
                reference_date=reference_date,
                value=r.value,
                formula_version=r.formula_version,
                inputs_snapshot=r.inputs_snapshot,
                source_filing_ids=r.source_filing_ids,
            )
            persisted.append(metric)

        self._session.flush()
        logger.info(
            "Computed %d metrics for issuer=%s date=%s",
            len(persisted),
            issuer_id,
            reference_date,
        )
        return persisted

    def _upsert_metric(
        self,
        *,
        issuer_id: uuid.UUID,
        metric_code: str,
        reference_date: date,
        value: float | None,
        formula_version: int,
        inputs_snapshot: dict,
        source_filing_ids: list[str],
    ) -> ComputedMetric:
        """Upsert a computed metric by natural key.

        Uses SELECT FOR UPDATE + UPDATE/INSERT — works cleanly with
        SQLAlchemy's identity map and is safe under concurrency
        (the unique index uq_computed_metrics_issuer_code_period_date
        is the final safety net against duplicate INSERTs).
        """
        existing = self._session.execute(
            select(ComputedMetric)
            .where(
                ComputedMetric.issuer_id == issuer_id,
                ComputedMetric.metric_code == metric_code,
                ComputedMetric.period_type == PeriodType.annual,
                ComputedMetric.reference_date == reference_date,
            )
            .with_for_update()
        ).scalar_one_or_none()

        if existing is not None:
            existing.value = value
            existing.formula_version = formula_version
            existing.inputs_snapshot_json = inputs_snapshot
            existing.source_filing_ids_json = source_filing_ids
            return existing

        metric = ComputedMetric(
            id=uuid.uuid4(),
            issuer_id=issuer_id,
            metric_code=metric_code,
            period_type=PeriodType.annual,
            reference_date=reference_date,
            value=value,
            formula_version=formula_version,
            inputs_snapshot_json=inputs_snapshot,
            source_filing_ids_json=source_filing_ids,
        )
        self._session.add(metric)
        return metric

    def _load_statement_values(
        self,
        issuer_id: uuid.UUID,
        reference_date: date,
    ) -> tuple[dict[str, float | None], list[str]]:
        """Query statement_lines from the latest completed filing for this issuer+date.

        Uses consolidated scope (con) when available; falls back to individual (ind).
        Returns (canonical_key -> normalized_value, list of filing_id strings).
        """
        stmt = (
            select(StatementLine, Filing.id.label("filing_id"))
            .join(Filing, StatementLine.filing_id == Filing.id)
            .where(
                Filing.issuer_id == issuer_id,
                Filing.reference_date == reference_date,
                Filing.status == FilingStatus.completed,
                StatementLine.canonical_key.isnot(None),
            )
            .order_by(
                # Prefer consolidated over individual
                StatementLine.scope.asc(),
                # Prefer latest version
                Filing.version_number.desc(),
            )
        )

        rows = self._session.execute(stmt).all()

        values: dict[str, float | None] = {}
        filing_ids_set: set[str] = set()
        seen_keys: set[str] = set()

        for row in rows:
            line: StatementLine = row[0]
            fid: uuid.UUID = row[1]

            key = line.canonical_key
            if key is None or key in seen_keys:
                continue

            seen_keys.add(key)
            values[key] = float(line.normalized_value) if line.normalized_value is not None else None
            filing_ids_set.add(str(fid))

        return values, sorted(filing_ids_set)
