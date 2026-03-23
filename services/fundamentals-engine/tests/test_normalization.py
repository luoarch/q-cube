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


# ---------------------------------------------------------------------------
# DFC label-based mapping tests (shareholder_distributions)
# ---------------------------------------------------------------------------


class TestDFCDistributionMapping:
    """Tests for label-based mapping of DFC 6.03.XX to shareholder_distributions."""

    def test_dividendos_pagos(self) -> None:
        result = CanonicalKeyMapper.map("6.03.04", label="Dividendos pagos", statement_type="DFC_MD")
        assert result == "shareholder_distributions"

    def test_pagamento_de_dividendos(self) -> None:
        result = CanonicalKeyMapper.map("6.03.05", label="Pagamento de dividendos", statement_type="DFC_MI")
        assert result == "shareholder_distributions"

    def test_dividendos_e_jcp_pagos(self) -> None:
        result = CanonicalKeyMapper.map("6.03.03", label="Dividendos e juros sobre capital próprio pagos", statement_type="DFC_MD")
        assert result == "shareholder_distributions"

    def test_jcp_pagos(self) -> None:
        result = CanonicalKeyMapper.map("6.03.02", label="Juros sobre capital próprio pagos", statement_type="DFC_MD")
        assert result == "shareholder_distributions"

    def test_jcp_abbreviation(self) -> None:
        result = CanonicalKeyMapper.map("6.03.01", label="Dividendos e JCP pagos", statement_type="DFC_MD")
        assert result == "shareholder_distributions"

    def test_jscp_abbreviation(self) -> None:
        result = CanonicalKeyMapper.map("6.03.01", label="Dividendos e JSCP pagos", statement_type="DFC_MD")
        assert result == "shareholder_distributions"

    def test_distribuicao_de_lucros(self) -> None:
        result = CanonicalKeyMapper.map("6.03.06", label="Distribuição de lucros", statement_type="DFC_MD")
        assert result == "shareholder_distributions"

    def test_proventos_pagos(self) -> None:
        result = CanonicalKeyMapper.map("6.03.07", label="Proventos pagos aos acionistas", statement_type="DFC_MD")
        assert result == "shareholder_distributions"

    def test_remuneracao_acionistas(self) -> None:
        result = CanonicalKeyMapper.map("6.03.08", label="Remuneração aos acionistas", statement_type="DFC_MD")
        assert result == "shareholder_distributions"

    # --- Exclusions: these are NOT shareholder distributions ---

    def test_dividendos_recebidos_excluded(self) -> None:
        """Dividends RECEIVED are income, not distributions."""
        result = CanonicalKeyMapper.map("6.03.02", label="Dividendos recebidos", statement_type="DFC_MD")
        assert result is None

    def test_jcp_recebido_excluded(self) -> None:
        result = CanonicalKeyMapper.map("6.03.03", label="Juros sobre capital próprio recebido", statement_type="DFC_MD")
        assert result is None

    def test_emprestimos_excluded(self) -> None:
        result = CanonicalKeyMapper.map("6.03.01", label="Captação de empréstimos e financiamentos", statement_type="DFC_MD")
        assert result is None

    def test_aumento_de_capital_excluded(self) -> None:
        result = CanonicalKeyMapper.map("6.03.01", label="Aumento de capital", statement_type="DFC_MD")
        assert result is None

    def test_recompra_acoes_excluded(self) -> None:
        """Share buybacks are tracked separately, not as distributions."""
        result = CanonicalKeyMapper.map("6.03.04", label="Recompra de ações", statement_type="DFC_MD")
        assert result is None

    def test_acoes_tesouraria_excluded(self) -> None:
        result = CanonicalKeyMapper.map("6.03.09", label="Ações em tesouraria", statement_type="DFC_MD")
        assert result is None

    # --- Edge cases ---

    def test_level1_code_not_affected(self) -> None:
        """6.03 (level 1) should still map to cash_from_financing, not distributions."""
        result = CanonicalKeyMapper.map("6.03", label="Caixa líquido atividades de financiamento", statement_type="DFC_MD")
        assert result == "cash_from_financing"

    def test_no_label_returns_none(self) -> None:
        """Without label, sub-accounts can't be mapped."""
        result = CanonicalKeyMapper.map("6.03.04", label="", statement_type="DFC_MD")
        assert result is None

    def test_backward_compat_direct_code_mapping(self) -> None:
        """Existing direct code mappings must still work."""
        assert CanonicalKeyMapper.map("3.05") == "ebit"
        assert CanonicalKeyMapper.map("6.01") == "cash_from_operations"
        assert CanonicalKeyMapper.map("2.03") == "equity"
