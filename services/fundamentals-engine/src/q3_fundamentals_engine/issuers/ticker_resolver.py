from __future__ import annotations

import abc
import logging

logger = logging.getLogger(__name__)


class TickerResolverHandler(abc.ABC):
    """Base handler for the Chain of Responsibility ticker resolution."""

    def __init__(self) -> None:
        self._next: TickerResolverHandler | None = None

    def set_next(self, handler: TickerResolverHandler) -> TickerResolverHandler:
        """Set the next handler in the chain. Returns the handler for fluent chaining."""
        self._next = handler
        return handler

    @abc.abstractmethod
    def resolve(self, cnpj: str, cvm_code: str) -> list[str]:
        """Resolve tickers for a given CNPJ / CVM code.

        Returns a list of ticker strings, or delegates to the next handler
        if this handler cannot resolve.
        """

    def _delegate(self, cnpj: str, cvm_code: str) -> list[str]:
        """Delegate to the next handler in the chain, or return empty list."""
        if self._next is not None:
            return self._next.resolve(cnpj, cvm_code)
        return []


class FcaResolver(TickerResolverHandler):
    """Resolve tickers from FCA valor_mobiliario data.

    The fca_mapping is keyed by cvm_code, with values being lists of ticker strings.
    """

    def __init__(self, fca_mapping: dict[str, list[str]]) -> None:
        super().__init__()
        self._fca_mapping = fca_mapping

    def resolve(self, cnpj: str, cvm_code: str) -> list[str]:
        tickers = self._fca_mapping.get(cvm_code, [])
        if tickers:
            logger.debug("FcaResolver found tickers for cvm_code=%s: %s", cvm_code, tickers)
            return tickers
        return self._delegate(cnpj, cvm_code)


class CadastroResolver(TickerResolverHandler):
    """Fallback: resolve from CVM cadastro data.

    cadastro_data is a list of dicts with at least 'cnpj' and 'ticker' keys.
    """

    def __init__(self, cadastro_data: list[dict[str, str]]) -> None:
        super().__init__()
        # Build a lookup: cnpj -> list of tickers
        self._cnpj_to_tickers: dict[str, list[str]] = {}
        for entry in cadastro_data:
            entry_cnpj = entry.get("cnpj", "")
            ticker = entry.get("ticker", "")
            if entry_cnpj and ticker:
                self._cnpj_to_tickers.setdefault(entry_cnpj, []).append(ticker)

    def resolve(self, cnpj: str, cvm_code: str) -> list[str]:
        tickers = self._cnpj_to_tickers.get(cnpj, [])
        if tickers:
            logger.debug("CadastroResolver found tickers for cnpj=%s: %s", cnpj, tickers)
            return tickers
        return self._delegate(cnpj, cvm_code)


class ManualOverrideResolver(TickerResolverHandler):
    """Last resort: hardcoded overrides for known edge cases.

    Keyed by cvm_code.
    """

    OVERRIDES: dict[str, list[str]] = {}

    def resolve(self, cnpj: str, cvm_code: str) -> list[str]:
        tickers = self.OVERRIDES.get(cvm_code, [])
        if tickers:
            logger.debug("ManualOverrideResolver found tickers for cvm_code=%s: %s", cvm_code, tickers)
            return tickers
        return self._delegate(cnpj, cvm_code)


def build_ticker_resolver_chain(
    fca_mapping: dict[str, list[str]] | None = None,
    cadastro_data: list[dict[str, str]] | None = None,
) -> TickerResolverHandler:
    """Build the ticker resolver chain: FCA -> Cadastro -> ManualOverride."""
    fca = FcaResolver(fca_mapping or {})
    cadastro = CadastroResolver(cadastro_data or [])
    manual = ManualOverrideResolver()
    fca.set_next(cadastro).set_next(manual)
    return fca
