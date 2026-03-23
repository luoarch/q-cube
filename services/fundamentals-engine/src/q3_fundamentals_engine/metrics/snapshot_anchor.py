"""Snapshot temporal anchoring for quarter-end alignment.

Finds the closest market snapshot within a +/- 30 day window of a quarter-end
date. Used by Net Buyback Yield and other metrics that need shares_outstanding
or market_cap anchored to specific quarter dates.

See Plan 3A §6.5.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_shared_models.entities import MarketSnapshot, Security

logger = logging.getLogger(__name__)

ANCHOR_WINDOW_DAYS = 30


def find_anchored_snapshot(
    session: Session,
    issuer_id: uuid.UUID,
    anchor_date: date,
    *,
    window_days: int = ANCHOR_WINDOW_DAYS,
    knowledge_date: date | None = None,
) -> MarketSnapshot | None:
    """Find the snapshot closest to anchor_date within the tolerance window.

    Uses the issuer's primary security. Returns None if no snapshot exists
    within the window.

    Ordering: snapshots after anchor_date first (closest), then before.
    This gives preference to the nearest snapshot regardless of direction.
    """
    security_id = _get_primary_security_id(session, issuer_id)
    if security_id is None:
        return None

    window_start = anchor_date - timedelta(days=window_days)
    # PIT enforcement: cap window_end at knowledge_date if provided
    window_end = anchor_date + timedelta(days=window_days)
    if knowledge_date is not None and window_end > knowledge_date:
        window_end = knowledge_date

    # Fetch all snapshots in the window, then pick the closest in Python.
    # The window is small (max ~60 days), so this is efficient.
    snapshots = session.execute(
        select(MarketSnapshot)
        .where(
            MarketSnapshot.security_id == security_id,
            MarketSnapshot.fetched_at >= window_start,
            MarketSnapshot.fetched_at <= window_end,
        )
        .order_by(MarketSnapshot.fetched_at)
    ).scalars().all()

    if not snapshots:
        return None

    # Pick the snapshot closest to anchor_date
    return min(
        snapshots,
        key=lambda s: abs((s.fetched_at.date() if hasattr(s.fetched_at, 'date') else s.fetched_at) - anchor_date),
    )


def _get_primary_security_id(session: Session, issuer_id: uuid.UUID) -> uuid.UUID | None:
    """Get the primary security ID for an issuer."""
    return session.execute(
        select(Security.id).where(
            Security.issuer_id == issuer_id,
            Security.is_primary.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()
