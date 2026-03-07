"""CVM data downloader — fetches ZIPs and cadastro from dados.cvm.gov.br.

Migrated from market-ingestion's cvm.py with added SHA-256 integrity checks.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging

import httpx

from q3_fundamentals_engine.config import CVM_BASE_URL, CVM_CADASTRO_URL
from q3_fundamentals_engine.providers.base import DownloadedFile

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(120.0, connect=30.0)

DFP_URL = f"{CVM_BASE_URL}/DFP/DADOS/dfp_cia_aberta_{{year}}.zip"
ITR_URL = f"{CVM_BASE_URL}/ITR/DADOS/itr_cia_aberta_{{year}}.zip"
FCA_URL = f"{CVM_BASE_URL}/FCA/DADOS/fca_cia_aberta_{{year}}.zip"


async def download_zip(url: str) -> bytes:
    """Download a ZIP file from CVM with a 120-second timeout."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        logger.info("downloading %s", url)
        resp = await client.get(url)
        resp.raise_for_status()
        logger.info("downloaded %d bytes from %s", len(resp.content), url)
        return resp.content


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest for the given bytes."""
    return hashlib.sha256(data).hexdigest()


async def download_dfp(year: int) -> DownloadedFile:
    """Download annual DFP filing ZIP for a given year."""
    url = DFP_URL.format(year=year)
    content = await download_zip(url)
    return DownloadedFile(
        filename=f"dfp_cia_aberta_{year}.zip",
        url=url,
        content=content,
        sha256_hash=compute_sha256(content),
        size_bytes=len(content),
    )


async def download_itr(year: int) -> DownloadedFile:
    """Download quarterly ITR filing ZIP for a given year."""
    url = ITR_URL.format(year=year)
    content = await download_zip(url)
    return DownloadedFile(
        filename=f"itr_cia_aberta_{year}.zip",
        url=url,
        content=content,
        sha256_hash=compute_sha256(content),
        size_bytes=len(content),
    )


async def download_fca(year: int) -> DownloadedFile:
    """Download FCA (Formulario Cadastral Ativo) ZIP for a given year."""
    url = FCA_URL.format(year=year)
    content = await download_zip(url)
    return DownloadedFile(
        filename=f"fca_cia_aberta_{year}.zip",
        url=url,
        content=content,
        sha256_hash=compute_sha256(content),
        size_bytes=len(content),
    )


async def download_cadastro() -> list[dict[str, str]]:
    """Download CVM company cadastro (cad_cia_aberta.csv).

    Returns list of dicts with keys: CD_CVM, DENOM_CIA, CNPJ_CIA, SIT_REG, etc.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        logger.info("downloading cadastro from %s", CVM_CADASTRO_URL)
        resp = await client.get(CVM_CADASTRO_URL)
        resp.raise_for_status()
        text = resp.content.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        rows = list(reader)
        logger.info("cadastro: %d companies loaded", len(rows))
        return rows
