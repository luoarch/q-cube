from __future__ import annotations

import logging
import uuid

from q3_shared_models.entities import Issuer
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class IssuerRegistry:
    """Registry for managing issuer records via upsert semantics."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_issuer(
        self,
        cvm_code: str,
        legal_name: str,
        cnpj: str,
        trade_name: str | None = None,
        sector: str | None = None,
        subsector: str | None = None,
        segment: str | None = None,
    ) -> Issuer:
        """Upsert an issuer by cvm_code. Returns the Issuer."""
        stmt = pg_insert(Issuer).values(
            id=uuid.uuid4(),
            cvm_code=cvm_code,
            legal_name=legal_name,
            cnpj=cnpj,
            trade_name=trade_name,
            sector=sector,
            subsector=subsector,
            segment=segment,
        )

        update_fields = {
            "legal_name": stmt.excluded.legal_name,
            "cnpj": stmt.excluded.cnpj,
            "trade_name": stmt.excluded.trade_name,
            "sector": stmt.excluded.sector,
            "subsector": stmt.excluded.subsector,
            "segment": stmt.excluded.segment,
        }

        stmt = stmt.on_conflict_do_update(
            index_elements=["cvm_code"],
            set_=update_fields,
        ).returning(Issuer)

        result = self._session.execute(stmt)
        issuer = result.scalars().one()
        self._session.flush()

        logger.info("Upserted issuer cvm_code=%s legal_name=%s", cvm_code, legal_name)
        return issuer

    def get_by_cvm_code(self, cvm_code: str) -> Issuer | None:
        """Look up an issuer by CVM code."""
        return (
            self._session.query(Issuer)
            .filter(Issuer.cvm_code == cvm_code)
            .first()
        )

    def get_by_cnpj(self, cnpj: str) -> Issuer | None:
        """Look up an issuer by CNPJ."""
        return (
            self._session.query(Issuer)
            .filter(Issuer.cnpj == cnpj)
            .first()
        )
