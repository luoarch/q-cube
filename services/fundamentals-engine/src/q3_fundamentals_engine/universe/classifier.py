"""Universe classifier — classifies all issuers and persists results.

Implements fail-closed semantics and idempotent supersede pattern.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from q3_shared_models.entities import Issuer, UniverseClassification

from .policy import (
    POLICY_VERSION,
    NullSectorWithoutOverrideError,
    SectorPolicy,
    UnmatchedSectorError,
    lookup_policy,
)
from .types import ClassificationRuleCode

logger = logging.getLogger(__name__)


class UnmatchedSectorBatchError(Exception):
    """Raised when the batch has unmatched sectors."""

    def __init__(self, unmatched: list[tuple[str, str]]) -> None:
        self.unmatched = unmatched
        sectors = ", ".join(f"{s!r} (cvm={c})" for s, c in unmatched)
        super().__init__(f"Unmatched sectors: {sectors}")


class MissingOverrideBatchError(Exception):
    """Raised when null-sector issuers lack overrides."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"NULL-sector issuers without override: {', '.join(missing)}")


# The 6 fields that form the identity tuple for idempotency comparison.
_IDENTITY_FIELDS = (
    "universe_class",
    "dedicated_strategy_type",
    "permanent_exclusion_reason",
    "classification_rule_code",
    "matched_sector_key",
    "policy_version",
)


@dataclass
class ClassificationResult:
    total: int = 0
    inserted: int = 0
    superseded: int = 0
    unchanged: int = 0
    errors_unmatched: list[tuple[str, str]] | None = None
    errors_null_sector: list[str] | None = None


def _build_row(
    issuer_id: uuid.UUID,
    policy: SectorPolicy,
    rule_code: ClassificationRuleCode,
    matched_sector_key: str | None,
    policy_version: str,
) -> UniverseClassification:
    return UniverseClassification(
        id=uuid.uuid4(),
        issuer_id=issuer_id,
        universe_class=policy.universe_class.value,
        dedicated_strategy_type=policy.dedicated_strategy_type.value if policy.dedicated_strategy_type else None,
        permanent_exclusion_reason=policy.permanent_exclusion_reason.value if policy.permanent_exclusion_reason else None,
        classification_rule_code=rule_code.value,
        classification_reason=policy.reason,
        matched_sector_key=matched_sector_key,
        policy_version=policy_version,
    )


def _identity_tuple(row: UniverseClassification) -> tuple:
    return tuple(getattr(row, f) for f in _IDENTITY_FIELDS)


def classify_all(
    session: Session,
    policy_version: str = POLICY_VERSION,
) -> ClassificationResult:
    """Classify all issuers. Fail-closed, idempotent, transactional.

    - Unmatched sectors → collected, batch fails at end
    - NULL sector without override → collected, batch fails at end
    - Identical active classification → no-op
    - Changed classification → supersede old, insert new
    """
    result = ClassificationResult()
    unmatched: list[tuple[str, str]] = []
    null_missing: list[str] = []

    # Load all issuers
    issuers = session.execute(select(Issuer)).scalars().all()
    result.total = len(issuers)

    # Load active classifications into lookup
    active_rows = session.execute(
        select(UniverseClassification).where(UniverseClassification.superseded_at.is_(None))
    ).scalars().all()
    active_by_issuer: dict[uuid.UUID, UniverseClassification] = {
        row.issuer_id: row for row in active_rows
    }

    # Classify each issuer
    new_rows: list[UniverseClassification] = []
    supersede_ids: list[uuid.UUID] = []

    for issuer in issuers:
        try:
            policy, rule_code = lookup_policy(issuer.cvm_code, issuer.sector)
        except UnmatchedSectorError as e:
            unmatched.append((e.sector, e.cvm_code))
            continue
        except NullSectorWithoutOverrideError as e:
            null_missing.append(e.cvm_code)
            continue

        matched_key = issuer.sector if rule_code == ClassificationRuleCode.SECTOR_MAP else None
        new_row = _build_row(issuer.id, policy, rule_code, matched_key, policy_version)

        existing = active_by_issuer.get(issuer.id)
        if existing is not None:
            if _identity_tuple(existing) == _identity_tuple(new_row):
                result.unchanged += 1
                continue
            # Supersede
            supersede_ids.append(existing.id)
            result.superseded += 1

        new_rows.append(new_row)
        result.inserted += 1

    # Fail-closed: check for errors before committing
    if unmatched:
        result.errors_unmatched = unmatched
        raise UnmatchedSectorBatchError(unmatched)
    if null_missing:
        result.errors_null_sector = null_missing
        raise MissingOverrideBatchError(null_missing)

    # Apply changes
    now = datetime.now(timezone.utc)
    if supersede_ids:
        session.execute(
            update(UniverseClassification)
            .where(UniverseClassification.id.in_(supersede_ids))
            .values(superseded_at=now)
        )

    for row in new_rows:
        session.add(row)

    session.flush()
    logger.info(
        "classify_all: total=%d inserted=%d superseded=%d unchanged=%d",
        result.total, result.inserted, result.superseded, result.unchanged,
    )
    return result
