"""Tests for normalization pipeline components."""

from __future__ import annotations

from q3_fundamentals_engine.normalization.canonical_mapper import CanonicalKeyMapper
from q3_fundamentals_engine.normalization.sign_normalizer import normalize_sign
from q3_fundamentals_engine.normalization.scope_resolver import resolve_scope


def test_canonical_mapper_ebit() -> None:
    assert CanonicalKeyMapper.map("3.05") == "ebit"


def test_canonical_mapper_revenue() -> None:
    assert CanonicalKeyMapper.map("3.01") == "revenue"


def test_canonical_mapper_unknown() -> None:
    assert CanonicalKeyMapper.map("99.99") is None


def test_canonical_mapper_cash_equivalents() -> None:
    assert CanonicalKeyMapper.map("1.01.01") == "cash_and_equivalents"


def test_sign_normalizer_cost_of_goods_positive() -> None:
    # COGS should be negative; if reported positive, flip it
    result = normalize_sign("cost_of_goods_sold", 100.0)
    assert result == -100.0


def test_sign_normalizer_cost_of_goods_already_negative() -> None:
    result = normalize_sign("cost_of_goods_sold", -100.0)
    assert result == -100.0


def test_sign_normalizer_revenue_stays_positive() -> None:
    result = normalize_sign("revenue", 500.0)
    assert result == 500.0


def test_sign_normalizer_none_value() -> None:
    assert normalize_sign("ebit", None) is None


def test_scope_resolver_prefers_con() -> None:
    scope, rows = resolve_scope({"con": [1, 2, 3], "ind": [4, 5]})
    assert scope == "con"
    assert rows == [1, 2, 3]


def test_scope_resolver_falls_back_to_ind() -> None:
    scope, rows = resolve_scope({"ind": [4, 5]})
    assert scope == "ind"
    assert rows == [4, 5]


def test_scope_resolver_empty() -> None:
    scope, rows = resolve_scope({})
    assert scope == "ind"
    assert rows == []
