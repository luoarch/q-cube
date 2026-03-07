"""Dados de Mercado API client — primary source for fundamentals.

API docs: https://www.dadosdemercado.com.br/api/docs
Issuer-centric model: endpoints keyed by cvm_code.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from q3_market_ingestion.config import DADOS_MERCADO_BASE_URL, DADOS_MERCADO_TOKEN

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {DADOS_MERCADO_TOKEN}"}


async def list_companies() -> list[dict[str, Any]]:
    """GET /companies — list all companies with cvm_code, name, sector."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{DADOS_MERCADO_BASE_URL}/companies",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def get_company_tickers(cvm_code: int) -> list[dict[str, Any]]:
    """GET /companies/:cvm_code/tickers — tickers associated with an issuer."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{DADOS_MERCADO_BASE_URL}/companies/{cvm_code}/tickers",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def get_balances(
    cvm_code: int,
    *,
    statement_type: str = "con",
) -> list[dict[str, Any]]:
    """GET /companies/:cvm_code/balances — BPA+BPP data.

    Fields: current_assets, fixed_assets, current_liabilities, equity, loans, etc.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{DADOS_MERCADO_BASE_URL}/companies/{cvm_code}/balances",
            headers=_headers(),
            params={"statement_type": statement_type},
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def get_income_statements(
    cvm_code: int,
    *,
    statement_type: str = "con",
) -> list[dict[str, Any]]:
    """GET /companies/:cvm_code/income_statements — DRE data.

    Fields: revenue, gross_profit, ebit, net_income, etc.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{DADOS_MERCADO_BASE_URL}/companies/{cvm_code}/income_statements",
            headers=_headers(),
            params={"statement_type": statement_type},
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def get_ratios(
    cvm_code: int,
    *,
    statement_type: str = "con",
) -> list[dict[str, Any]]:
    """GET /companies/:cvm_code/ratios — financial indicators.

    Fields: working_capital, net_debt, ebitda, ebit_margin, gross_margin,
            net_margin, return_on_equity, return_on_assets, etc.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{DADOS_MERCADO_BASE_URL}/companies/{cvm_code}/ratios",
            headers=_headers(),
            params={"statement_type": statement_type},
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def get_market_ratios(
    cvm_code: int,
    *,
    statement_type: str = "con",
) -> list[dict[str, Any]]:
    """GET /companies/:cvm_code/market_ratios — market indicators.

    Fields: price_earnings, price_to_book, price_to_ebit,
            earnings_per_share, equity_per_share, price, shares, etc.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{DADOS_MERCADO_BASE_URL}/companies/{cvm_code}/market_ratios",
            headers=_headers(),
            params={"statement_type": statement_type},
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def get_shares(cvm_code: int) -> list[dict[str, Any]]:
    """GET /companies/:cvm_code/shares — shares outstanding history."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{DADOS_MERCADO_BASE_URL}/companies/{cvm_code}/shares",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
