"""Backfill issuer.sector/subsector/segment from CVM cadastro CSV.

Downloads cad_cia_aberta.csv from dados.cvm.gov.br and updates the issuers table.
This is a one-shot fix for the missing sector data that blocks Plan 2 differentiation.

Usage:
    source .venv/bin/activate
    python scripts/backfill_issuer_sectors.py
"""

from __future__ import annotations

import csv
import io
import logging
import sys

import httpx
from sqlalchemy import text, update

from q3_quant_engine.db.session import SessionLocal
from q3_shared_models.entities import Issuer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_sectors")

CVM_CADASTRO_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"


def download_cadastro() -> list[dict[str, str]]:
    """Download CVM cadastro CSV synchronously."""
    logger.info("Downloading cadastro from %s", CVM_CADASTRO_URL)
    resp = httpx.get(CVM_CADASTRO_URL, timeout=120.0)
    resp.raise_for_status()
    content = resp.content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(content), delimiter=";")
    rows = list(reader)
    logger.info("Cadastro downloaded: %d entries", len(rows))
    return rows


def build_sector_map(cadastro: list[dict[str, str]]) -> dict[str, dict[str, str | None]]:
    """Build CD_CVM -> {sector, subsector, segment} map."""
    result: dict[str, dict[str, str | None]] = {}
    for entry in cadastro:
        code = entry.get("CD_CVM", "").strip()
        if code:
            # Zero-pad to 6 digits to match DB format
            padded = code.zfill(6)
            result[padded] = {
                "sector": entry.get("SETOR_ATIV", "").strip() or None,
                "subsector": entry.get("SUBSETOR_ATIV", "").strip() or None,
                "segment": entry.get("SEGMENTO_ATIV", "").strip() or None,
            }
    return result


def main():
    # 1. Download cadastro
    cadastro = download_cadastro()
    sector_map = build_sector_map(cadastro)
    logger.info("Sector map built: %d CVM codes", len(sector_map))

    # 2. Update issuers
    session = SessionLocal()
    try:
        # Get all issuers
        issuers = session.execute(
            text("SELECT id, cvm_code, sector FROM issuers")
        ).fetchall()

        updated = 0
        skipped = 0
        not_found = 0

        for issuer_id, cvm_code, current_sector in issuers:
            info = sector_map.get(cvm_code)
            if not info:
                not_found += 1
                continue

            new_sector = info["sector"]
            new_subsector = info["subsector"]
            new_segment = info["segment"]

            if not new_sector:
                skipped += 1
                continue

            session.execute(
                update(Issuer)
                .where(Issuer.id == issuer_id)
                .values(
                    sector=new_sector,
                    subsector=new_subsector,
                    segment=new_segment,
                )
            )
            updated += 1

        session.commit()

        logger.info(
            "Backfill complete: updated=%d, skipped=%d (no sector in cadastro), not_found=%d (CVM code not in cadastro)",
            updated, skipped, not_found,
        )

        # Verify
        with_sector = session.execute(
            text("SELECT count(*) FROM issuers WHERE sector IS NOT NULL")
        ).scalar()
        total = session.execute(text("SELECT count(*) FROM issuers")).scalar()
        logger.info("Issuers with sector: %d/%d", with_sector, total)

        # Sample
        samples = session.execute(
            text("SELECT cvm_code, legal_name, sector FROM issuers WHERE sector IS NOT NULL LIMIT 10")
        ).fetchall()
        for s in samples:
            print(f"  {s[0]:<8s} {s[1][:40]:<41s} {s[2]}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
