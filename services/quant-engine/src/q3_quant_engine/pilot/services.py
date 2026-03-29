"""Pilot services — snapshot persistence + forward return computation.

SnapshotService: ranking data injected explicitly (no fetch, no HTTP).
ForwardReturnService: prices from market_snapshots via session (no external fetch).
Both idempotent via unique constraints + upsert.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_shared_models.entities import ForwardReturn, MarketSnapshot, RankingSnapshot, Security

from q3_quant_engine.pilot.returns import calculate_forward_return, resolve_horizon_date
from q3_quant_engine.pilot.snapshot import RankingItemInput, SnapshotRow, map_ranking_to_snapshot_rows

logger = logging.getLogger(__name__)


@dataclass
class CreateResult:
    inserted: int = 0
    updated: int = 0
    total: int = 0


@dataclass
class ComputeResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    total: int = 0


class SnapshotService:
    """Persist ranking snapshot. Ranking injected — no fetch, no HTTP."""

    def create_daily_snapshot(
        self,
        session: Session,
        snapshot_date: date,
        ranking_items: list[RankingItemInput],
    ) -> CreateResult:
        """Persist ranking items as snapshot rows. Idempotent (upsert)."""
        rows = map_ranking_to_snapshot_rows(ranking_items, snapshot_date)
        result = CreateResult(total=len(rows))

        for row in rows:
            existing = session.execute(
                select(RankingSnapshot).where(
                    RankingSnapshot.snapshot_date == row.snapshot_date,
                    RankingSnapshot.ticker == row.ticker,
                ).with_for_update()
            ).scalar_one_or_none()

            if existing is not None:
                existing.model_family = row.model_family
                existing.rank_within_model = row.rank_within_model
                existing.composite_score = row.composite_score
                existing.investability_status = row.investability_status
                existing.earnings_yield = row.earnings_yield
                existing.return_on_capital = row.return_on_capital
                existing.net_payout_yield = row.net_payout_yield
                result.updated += 1
            else:
                session.add(RankingSnapshot(
                    id=uuid.uuid4(),
                    snapshot_date=row.snapshot_date,
                    ticker=row.ticker,
                    model_family=row.model_family,
                    rank_within_model=row.rank_within_model,
                    composite_score=row.composite_score,
                    investability_status=row.investability_status,
                    earnings_yield=row.earnings_yield,
                    return_on_capital=row.return_on_capital,
                    net_payout_yield=row.net_payout_yield,
                ))
                result.inserted += 1

        session.flush()
        logger.info(
            "Snapshot %s: inserted=%d updated=%d total=%d",
            snapshot_date, result.inserted, result.updated, result.total,
        )
        return result


class ForwardReturnService:
    """Compute forward returns from market_snapshots prices. No external fetch."""

    def compute_forward_returns(
        self,
        session: Session,
        snapshot_date: date,
        horizon: str,
    ) -> ComputeResult:
        """Compute forward returns for all tickers in a snapshot. Idempotent."""
        target_date = resolve_horizon_date(snapshot_date, horizon)

        # Get all tickers from this snapshot
        snapshots = session.execute(
            select(RankingSnapshot).where(
                RankingSnapshot.snapshot_date == snapshot_date,
            )
        ).scalars().all()

        if not snapshots:
            logger.warning("No snapshots found for %s", snapshot_date)
            return ComputeResult()

        # Build ticker → security_id map
        tickers = [s.ticker for s in snapshots]
        sec_rows = session.execute(
            select(Security.ticker, Security.id).where(
                Security.ticker.in_(tickers),
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).all()
        sec_map = {r[0]: r[1] for r in sec_rows}

        result = ComputeResult(total=len(snapshots))

        for snap in snapshots:
            sec_id = sec_map.get(snap.ticker)
            if sec_id is None:
                result.skipped += 1
                continue

            # Get price at t0 (closest to snapshot_date)
            price_t0 = self._get_price(session, sec_id, snapshot_date)
            # Get price at tn (closest to target_date)
            price_tn = self._get_price(session, sec_id, target_date)

            ret = calculate_forward_return(price_t0, price_tn)
            if ret is None:
                result.skipped += 1
                continue

            # Upsert
            existing = session.execute(
                select(ForwardReturn).where(
                    ForwardReturn.snapshot_date == snapshot_date,
                    ForwardReturn.ticker == snap.ticker,
                    ForwardReturn.horizon == horizon,
                ).with_for_update()
            ).scalar_one_or_none()

            if existing is not None:
                existing.price_t0 = price_t0
                existing.price_tn = price_tn
                existing.return_value = ret
                result.updated += 1
            else:
                session.add(ForwardReturn(
                    id=uuid.uuid4(),
                    snapshot_date=snapshot_date,
                    ticker=snap.ticker,
                    horizon=horizon,
                    price_t0=price_t0,
                    price_tn=price_tn,
                    return_value=ret,
                ))
                result.inserted += 1

        session.flush()
        logger.info(
            "Forward returns %s/%s: inserted=%d skipped=%d total=%d",
            snapshot_date, horizon, result.inserted, result.skipped, result.total,
        )
        return result

    # Window for price lookup — covers weekends + minor gaps.
    # Not related to snapshot_anchor (30d) or cvm_shares (exact match).
    PRICE_WINDOW_DAYS = 5

    @staticmethod
    def _get_price(session: Session, security_id: uuid.UUID, target_date: date) -> float | None:
        """Get closing price closest to target_date from market_snapshots.

        Searches +/- PRICE_WINDOW_DAYS window using fetched_at::date cast
        to avoid date/timestamptz comparison issues.
        """
        from sqlalchemy import func, cast, Date
        from datetime import timedelta

        window_days = ForwardReturnService.PRICE_WINDOW_DAYS
        window_start = target_date - timedelta(days=window_days)
        window_end = target_date + timedelta(days=window_days)

        rows = session.execute(
            select(
                MarketSnapshot.price,
                cast(MarketSnapshot.fetched_at, Date).label("fetched_date"),
            ).where(
                MarketSnapshot.security_id == security_id,
                MarketSnapshot.price.is_not(None),
                cast(MarketSnapshot.fetched_at, Date) >= window_start,
                cast(MarketSnapshot.fetched_at, Date) <= window_end,
            )
        ).all()

        if not rows:
            return None

        # Pick closest to target_date (date-safe comparison)
        best = min(rows, key=lambda r: abs(r[1] - target_date))
        return float(best[0])
