from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class DownloadedFile:
    """Represents a downloaded raw file with integrity metadata."""

    filename: str
    url: str
    content: bytes
    sha256_hash: str
    size_bytes: int


class FundamentalsProviderAdapter(abc.ABC):
    """Abstract adapter for fundamentals data providers (CVM, brapi, etc.)."""

    @abc.abstractmethod
    async def download_filings(
        self, year: int, doc_types: list[str]
    ) -> list[DownloadedFile]: ...

    @abc.abstractmethod
    async def download_cadastro(self) -> list[dict[str, str]]: ...
