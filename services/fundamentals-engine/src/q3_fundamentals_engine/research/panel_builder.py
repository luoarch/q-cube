"""NPY Research Panel builder.

Reads approved computed_metrics, applies source-tier rules and quality flags,
and persists a versioned research panel. Does NOT recompute any metrics.

Usage:
    from q3_fundamentals_engine.research.panel_builder import build_npy_research_panel

    with SessionLocal() as session:
        rows = build_npy_research_panel(
            session,
            reference_date=date(2024, 12, 31),
            dataset_version="npy_panel_2024q4_v1",
        )
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from q3_shared_models.entities import (
    ComputedMetric,
    Filing,
    Issuer,
    NpyDatasetVersion,
    NpyResearchPanel,
    Security,
)

from q3_fundamentals_engine.research.quality_flags import assign_quality_flag
from q3_fundamentals_engine.research.source_tiers import (
    SourceTier,
    derive_dy_tiers,
    derive_nby_tiers,
    derive_npy_tier,
)

logger = logging.getLogger(__name__)

FORMULA_VERSION = "npy_v1_dy_plus_nby"


def build_npy_research_panel(
    session: Session,
    reference_date: date,
    dataset_version: str,
    *,
    knowledge_date: date | None = None,
) -> list[NpyResearchPanel]:
    """Build the NPY research panel for a given reference_date.

    Idempotent: deletes existing rows for this (reference_date, dataset_version)
    before inserting. Same inputs produce identical output.

    Args:
        knowledge_date: If provided, enables PIT mode. Each row is checked for
            whether all source filings have publication_date <= knowledge_date
            and all source snapshots have fetched_at <= knowledge_date.
            Rows that fail are marked pit_compliant=False but still included.
    """
    # Check if this dataset version is frozen
    existing_version = session.get(NpyDatasetVersion, dataset_version)
    if existing_version is not None and existing_version.frozen_at is not None:
        raise ValueError(
            f"Dataset version '{dataset_version}' is frozen (frozen_at={existing_version.frozen_at}). "
            "Cannot rebuild a frozen version."
        )

    pit_mode = "strict" if knowledge_date is not None else "relaxed"

    # Delete existing rows for this dataset version + date
    session.execute(
        delete(NpyResearchPanel).where(
            NpyResearchPanel.reference_date == reference_date,
            NpyResearchPanel.dataset_version == dataset_version,
        )
    )
    session.flush()

    # Get all issuers with current securities
    issuer_rows = session.execute(
        select(Issuer.id).where(
            Issuer.id.in_(
                select(Security.issuer_id).where(Security.valid_to.is_(None))
            )
        ).order_by(Issuer.id)
    ).scalars().all()

    logger.info(
        "Building NPY research panel: reference_date=%s, dataset_version=%s, "
        "pit_mode=%s, knowledge_date=%s, issuers=%d",
        reference_date, dataset_version, pit_mode, knowledge_date, len(issuer_rows),
    )

    # Pre-load all relevant computed metrics for this reference_date
    dy_metrics = _load_metrics_by_code(session, "dividend_yield", reference_date)
    nby_metrics = _load_metrics_by_code(session, "net_buyback_yield", reference_date)
    npy_metrics = _load_metrics_by_code(session, "net_payout_yield", reference_date)

    # Pre-load primary security IDs
    primaries = _load_primary_securities(session)

    # Pre-load filing publication dates for PIT check
    filing_pub_dates: dict[uuid.UUID, date | None] = {}
    if knowledge_date is not None:
        filing_pub_dates = _load_filing_publication_dates(session)

    rows: list[NpyResearchPanel] = []
    for issuer_id in issuer_rows:
        row = _build_row(
            issuer_id=issuer_id,
            reference_date=reference_date,
            dataset_version=dataset_version,
            primary_security_id=primaries.get(issuer_id),
            dy_metric=dy_metrics.get(issuer_id),
            nby_metric=nby_metrics.get(issuer_id),
            npy_metric=npy_metrics.get(issuer_id),
            knowledge_date=knowledge_date,
            filing_pub_dates=filing_pub_dates,
        )
        session.add(row)
        rows.append(row)

    session.flush()

    # Upsert dataset version record
    quality_dist = dict(Counter(r.quality_flag for r in rows))
    if existing_version is not None:
        existing_version.reference_date = reference_date
        existing_version.knowledge_date = knowledge_date
        existing_version.pit_mode = pit_mode
        existing_version.formula_version = FORMULA_VERSION
        existing_version.row_count = len(rows)
        existing_version.quality_distribution = quality_dist
    else:
        session.add(NpyDatasetVersion(
            dataset_version=dataset_version,
            reference_date=reference_date,
            knowledge_date=knowledge_date,
            pit_mode=pit_mode,
            formula_version=FORMULA_VERSION,
            row_count=len(rows),
            quality_distribution=quality_dist,
        ))

    session.flush()
    logger.info("Built %d research panel rows (pit_mode=%s)", len(rows), pit_mode)
    return rows


def _build_row(
    *,
    issuer_id: uuid.UUID,
    reference_date: date,
    dataset_version: str,
    primary_security_id: uuid.UUID | None,
    dy_metric: ComputedMetric | None,
    nby_metric: ComputedMetric | None,
    npy_metric: ComputedMetric | None,
    knowledge_date: date | None,
    filing_pub_dates: dict[uuid.UUID, date | None],
) -> NpyResearchPanel:
    """Build a single research panel row with tier, quality, and PIT derivation."""
    # Extract values
    dy_value = float(dy_metric.value) if dy_metric is not None and dy_metric.value is not None else None
    nby_value = float(nby_metric.value) if nby_metric is not None and nby_metric.value is not None else None
    npy_value = float(npy_metric.value) if npy_metric is not None and npy_metric.value is not None else None

    # Derive source tiers
    dy_inputs = dy_metric.inputs_snapshot_json if dy_metric else None
    dy_filings = dy_metric.source_filing_ids_json if dy_metric else None
    nby_inputs = nby_metric.inputs_snapshot_json if nby_metric else None

    dy_tier, mcap_tier = derive_dy_tiers(dy_inputs, dy_filings)
    nby_tier, shares_tier = derive_nby_tiers(nby_inputs)

    if dy_value is not None and nby_value is not None:
        npy_tier = derive_npy_tier(dy_tier, nby_tier)
    elif dy_value is None and nby_value is None:
        npy_tier = SourceTier.D
    else:
        npy_tier = SourceTier.D

    # Assign quality flag
    quality = assign_quality_flag(npy_value, dy_tier, nby_tier, npy_tier)

    # PIT compliance check
    pit_compliant: bool | None = None
    if knowledge_date is not None:
        pit_compliant = _check_pit_compliance(
            dy_metric, nby_metric, knowledge_date, filing_pub_dates,
        )

    return NpyResearchPanel(
        id=uuid.uuid4(),
        issuer_id=issuer_id,
        reference_date=reference_date,
        primary_security_id=primary_security_id,
        dividend_yield=dy_value,
        net_buyback_yield=nby_value,
        net_payout_yield=npy_value,
        dy_source_tier=dy_tier.value,
        nby_source_tier=nby_tier.value,
        market_cap_source_tier=mcap_tier.value,
        shares_source_tier=shares_tier.value,
        npy_source_tier=npy_tier.value,
        quality_flag=quality.value,
        formula_version=FORMULA_VERSION,
        dataset_version=dataset_version,
        dy_metric_id=dy_metric.id if dy_metric else None,
        nby_metric_id=nby_metric.id if nby_metric else None,
        npy_metric_id=npy_metric.id if npy_metric else None,
        pit_compliant=pit_compliant,
        knowledge_date=knowledge_date,
    )


def _check_pit_compliance(
    dy_metric: ComputedMetric | None,
    nby_metric: ComputedMetric | None,
    knowledge_date: date,
    filing_pub_dates: dict[uuid.UUID, date | None],
) -> bool:
    """Check if all source inputs were available by knowledge_date.

    DY compliance: all source filing publication_dates <= knowledge_date.
    NBY compliance: snapshot fetched_at <= knowledge_date (checked via inputs_snapshot).
    """
    # Check DY filings
    if dy_metric is not None:
        filing_ids = dy_metric.source_filing_ids_json or []
        for fid_str in filing_ids:
            try:
                fid = uuid.UUID(fid_str)
            except (ValueError, TypeError):
                continue
            pub_date = filing_pub_dates.get(fid)
            if pub_date is not None and pub_date > knowledge_date:
                return False

    # Check NBY snapshot timestamps
    if nby_metric is not None:
        inputs = nby_metric.inputs_snapshot_json or {}
        for key in ("t_snapshot_fetched_at", "t4_snapshot_fetched_at"):
            fetched_str = inputs.get(key)
            if fetched_str:
                try:
                    fetched_date = date.fromisoformat(fetched_str[:10])
                    if fetched_date > knowledge_date:
                        return False
                except (ValueError, TypeError):
                    pass

    return True


def _load_metrics_by_code(
    session: Session,
    metric_code: str,
    reference_date: date,
) -> dict[uuid.UUID, ComputedMetric]:
    """Load computed metrics for a given code + date, keyed by issuer_id."""
    metrics = session.execute(
        select(ComputedMetric).where(
            ComputedMetric.metric_code == metric_code,
            ComputedMetric.reference_date == reference_date,
        )
    ).scalars().all()
    return {m.issuer_id: m for m in metrics}


def _load_primary_securities(session: Session) -> dict[uuid.UUID, uuid.UUID]:
    """Load primary security IDs keyed by issuer_id."""
    rows = session.execute(
        select(Security.issuer_id, Security.id).where(
            Security.is_primary.is_(True),
            Security.valid_to.is_(None),
        )
    ).all()
    return {r[0]: r[1] for r in rows}


def _load_filing_publication_dates(session: Session) -> dict[uuid.UUID, date | None]:
    """Load all filing publication dates, keyed by filing ID."""
    rows = session.execute(
        select(Filing.id, Filing.publication_date)
    ).all()
    return {r[0]: r[1] for r in rows}
