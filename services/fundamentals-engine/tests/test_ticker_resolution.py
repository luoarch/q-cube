"""Tests for ticker resolution chain of responsibility."""

from __future__ import annotations

from q3_fundamentals_engine.issuers.ticker_resolver import (
    FcaResolver,
    ManualOverrideResolver,
    build_ticker_resolver_chain,
)


def test_fca_resolver_found() -> None:
    mapping = {"9512": ["PETR3", "PETR4"]}
    resolver = FcaResolver(mapping)
    result = resolver.resolve("33000167000101", "9512")
    assert result == ["PETR3", "PETR4"]


def test_fca_resolver_not_found_chains_to_next() -> None:
    mapping = {"9512": ["PETR3", "PETR4"]}
    resolver = build_ticker_resolver_chain(fca_mapping=mapping)
    result = resolver.resolve("99999999999999", "0000")
    assert result == []


def test_chain_returns_first_match() -> None:
    mapping = {"4170": ["VALE3"]}
    resolver = build_ticker_resolver_chain(fca_mapping=mapping)
    result = resolver.resolve("12345678901234", "4170")
    assert result == ["VALE3"]
