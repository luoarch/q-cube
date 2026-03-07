from __future__ import annotations

import logging
import uuid
from datetime import date

from q3_shared_models.entities import Security
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages security (ticker) records for issuers."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_securities(
        self,
        issuer_id: uuid.UUID,
        tickers: list[str],
    ) -> list[Security]:
        """Create or update securities for an issuer.

        The first ticker in the list is marked as primary (typically the ON
        stock ending in '3'). Subsequent tickers are marked as non-primary.
        """
        if not tickers:
            return []

        today = date.today()
        securities: list[Security] = []

        for idx, ticker in enumerate(tickers):
            is_primary = idx == 0

            stmt = pg_insert(Security).values(
                id=uuid.uuid4(),
                issuer_id=issuer_id,
                ticker=ticker,
                is_primary=is_primary,
                valid_from=today,
            )

            stmt = stmt.on_conflict_do_update(
                constraint="uq_securities_issuer_ticker_valid",
                set_={
                    "is_primary": is_primary,
                },
            ).returning(Security)

            result = self._session.execute(stmt)
            security = result.scalars().one()
            securities.append(security)

        self._session.flush()
        logger.info(
            "Upserted %d securities for issuer_id=%s: %s",
            len(securities),
            issuer_id,
            tickers,
        )
        return securities

    def deactivate_security(self, security_id: uuid.UUID, end_date: date) -> None:
        """Deactivate a security by setting its valid_to date."""
        security = (
            self._session.query(Security)
            .filter(Security.id == security_id)
            .first()
        )
        if security is None:
            logger.warning("Security %s not found for deactivation", security_id)
            return

        security.valid_to = end_date  # type: ignore[assignment]
        self._session.flush()
        logger.info("Deactivated security %s (valid_to=%s)", security_id, end_date)
