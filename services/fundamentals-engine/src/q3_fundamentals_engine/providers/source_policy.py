"""Source selection policy — determines which adapters to use based on feature flags."""

from __future__ import annotations

import logging

from q3_fundamentals_engine.config import (
    ENABLE_BRAPI,
    ENABLE_CVM,
    ENABLE_DADOS_MERCADO,
    FUNDAMENTALS_SOURCE_ISSUER_MASTER,
    FUNDAMENTALS_SOURCE_MARKET_DATA,
    FUNDAMENTALS_SOURCE_STATEMENTS,
)
from q3_fundamentals_engine.providers.base import FundamentalsProviderAdapter
from q3_fundamentals_engine.providers.brapi.adapter import BrapiProviderAdapter
from q3_fundamentals_engine.providers.cvm.adapter import CvmProviderAdapter
from q3_fundamentals_engine.providers.dadosdemercado.adapter import (
    DadosDeMercadoProviderAdapter,
)

logger = logging.getLogger(__name__)

_ADAPTER_MAP: dict[str, type[FundamentalsProviderAdapter]] = {
    "cvm": CvmProviderAdapter,
    "brapi": BrapiProviderAdapter,
    "dados_de_mercado": DadosDeMercadoProviderAdapter,
}

_FLAG_MAP: dict[str, bool] = {
    "cvm": ENABLE_CVM,
    "brapi": ENABLE_BRAPI,
    "dados_de_mercado": ENABLE_DADOS_MERCADO,
}


class SourceSelectionPolicy:
    """Resolves which provider adapters to use for each data domain."""

    def get_issuer_master_adapter(self) -> FundamentalsProviderAdapter:
        return self._resolve(FUNDAMENTALS_SOURCE_ISSUER_MASTER, "issuer_master")

    def get_statements_adapter(self) -> FundamentalsProviderAdapter:
        return self._resolve(FUNDAMENTALS_SOURCE_STATEMENTS, "statements")

    def get_market_data_adapter(self) -> FundamentalsProviderAdapter | None:
        source = FUNDAMENTALS_SOURCE_MARKET_DATA
        if source not in _ADAPTER_MAP:
            logger.warning("unknown market_data source: %s", source)
            return None
        if not _FLAG_MAP.get(source, False):
            logger.info("market_data source %s is disabled", source)
            return None
        return _ADAPTER_MAP[source]()

    def get_available_adapters(self) -> list[FundamentalsProviderAdapter]:
        """Return all enabled adapters in priority order."""
        result: list[FundamentalsProviderAdapter] = []
        for source, enabled in _FLAG_MAP.items():
            if enabled and source in _ADAPTER_MAP:
                result.append(_ADAPTER_MAP[source]())
        return result

    def _resolve(self, source: str, domain: str) -> FundamentalsProviderAdapter:
        if source not in _ADAPTER_MAP:
            raise ValueError(f"Unknown {domain} source: {source}")
        if not _FLAG_MAP.get(source, False):
            raise ValueError(
                f"{domain} source '{source}' is disabled. "
                f"Set ENABLE_{source.upper()}=true in .env"
            )
        return _ADAPTER_MAP[source]()
