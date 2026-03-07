"""CVM provider adapter — implements FundamentalsProviderAdapter for CVM data."""

from __future__ import annotations

import logging

from q3_fundamentals_engine.providers.base import (
    DownloadedFile,
    FundamentalsProviderAdapter,
)
from q3_fundamentals_engine.providers.cvm.downloader import (
    download_cadastro,
    download_dfp,
    download_fca,
    download_itr,
)

logger = logging.getLogger(__name__)

_DOWNLOADERS: dict[str, object] = {
    "DFP": download_dfp,
    "ITR": download_itr,
    "FCA": download_fca,
}


class CvmProviderAdapter(FundamentalsProviderAdapter):
    """Adapter for CVM (Comissao de Valores Mobiliarios) open data portal."""

    async def download_filings(
        self, year: int, doc_types: list[str]
    ) -> list[DownloadedFile]:
        """Download filing ZIPs for the requested document types and year.

        Args:
            year: Fiscal year to download.
            doc_types: List of document types, e.g. ["DFP", "ITR", "FCA"].

        Returns:
            List of DownloadedFile instances with raw ZIP content.
        """
        results: list[DownloadedFile] = []
        for doc_type in doc_types:
            doc_upper = doc_type.upper()
            if doc_upper == "DFP":
                results.append(await download_dfp(year))
            elif doc_upper == "ITR":
                results.append(await download_itr(year))
            elif doc_upper == "FCA":
                results.append(await download_fca(year))
            else:
                logger.warning("unknown CVM document type: %s, skipping", doc_type)
        return results

    async def download_cadastro(self) -> list[dict[str, str]]:
        """Download CVM company cadastro."""
        return await download_cadastro()
