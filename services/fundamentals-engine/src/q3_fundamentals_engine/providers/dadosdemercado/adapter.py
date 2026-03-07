"""Dados de Mercado provider adapter — primary for fundamentals (issuer-centric)."""

from __future__ import annotations

import logging

import httpx

from q3_fundamentals_engine.config import DADOS_MERCADO_BASE_URL, DADOS_MERCADO_TOKEN
from q3_fundamentals_engine.providers.base import (
    DownloadedFile,
    FundamentalsProviderAdapter,
)

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class DadosDeMercadoProviderAdapter(FundamentalsProviderAdapter):
    """Adapter for Dados de Mercado API.

    Issuer-centric API keyed by cvm_code. Provides fundamentals data
    but does not provide raw filing downloads.
    """

    async def download_filings(self, year: int, doc_types: list[str]) -> list[DownloadedFile]:
        raise NotImplementedError("Dados de Mercado does not provide filing downloads")

    async def download_cadastro(self) -> list[dict[str, str]]:
        raise NotImplementedError("Dados de Mercado does not provide cadastro CSV")

    async def get_company(self, cvm_code: str) -> dict | None:
        """Fetch company info from Dados de Mercado."""
        if not DADOS_MERCADO_TOKEN:
            logger.warning("DADOS_MERCADO_TOKEN not set")
            return None

        url = f"{DADOS_MERCADO_BASE_URL}/companies/{cvm_code}"
        headers = {"Authorization": f"Bearer {DADOS_MERCADO_TOKEN}"}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning("DM company failed for %s: %d", cvm_code, resp.status_code)
                return None
            return resp.json()

    async def get_financials(self, cvm_code: str, year: int | None = None) -> dict | None:
        """Fetch financial data from Dados de Mercado."""
        if not DADOS_MERCADO_TOKEN:
            logger.warning("DADOS_MERCADO_TOKEN not set")
            return None

        url = f"{DADOS_MERCADO_BASE_URL}/companies/{cvm_code}/financials"
        headers = {"Authorization": f"Bearer {DADOS_MERCADO_TOKEN}"}
        params: dict[str, str] = {}
        if year:
            params["year"] = str(year)

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.warning("DM financials failed for %s: %d", cvm_code, resp.status_code)
                return None
            return resp.json()
