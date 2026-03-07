"""Factory for creating filing parsers based on document type."""

from __future__ import annotations

from q3_fundamentals_engine.parsers.base import BaseFilingParser
from q3_fundamentals_engine.parsers.dfp import DfpParser
from q3_fundamentals_engine.parsers.itr import ItrParser


class FilingParserFactory:
    """Factory Method for creating the appropriate parser for a CVM document type."""

    @staticmethod
    def create(doc_type: str) -> BaseFilingParser:
        """Create a parser instance for the given document type.

        Args:
            doc_type: CVM document type — "DFP" or "ITR".

        Returns:
            A BaseFilingParser subclass instance.

        Raises:
            ValueError: If doc_type is not recognized.

        Note:
            FCA is handled separately via FcaParser since it returns
            FcaCompanyInfo instead of ParsedRow.
        """
        match doc_type.upper():
            case "DFP":
                return DfpParser()
            case "ITR":
                return ItrParser()
            case _:
                raise ValueError(
                    f"Unknown document type: {doc_type}. "
                    f"Supported types: DFP, ITR. "
                    f"For FCA, use FcaParser directly."
                )
