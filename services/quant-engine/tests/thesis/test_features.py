"""Tests for Plan 2 Feature Engineering (MF-F1).

Covers:
  - Sector proxy mapping (direct + indirect)
  - Refinancing stress quantitative computation
  - Draft builder integration
  - Missing data / fallback behavior
  - Provenance correctness
"""

from __future__ import annotations

import pytest

from q3_quant_engine.thesis.features.draft_builder import (
    IssuerFeatureData,
    build_feature_draft,
)
from q3_quant_engine.thesis.features.refinancing_stress import (
    NEUTRAL_FALLBACK_SCORE,
    compute_refinancing_stress_score,
)
from q3_quant_engine.thesis.features.sector_proxy import (
    DEFAULT_PROXY_SCORE,
    DIRECT_COMMODITY_MAP,
    INDIRECT_COMMODITY_MAP,
    SECTOR_PROXY_VERSION,
    lookup_direct_commodity_proxy,
    lookup_indirect_commodity_proxy,
)
from q3_quant_engine.thesis.types import ScoreConfidence, ScoreSourceType


AS_OF = "2026-03-15"


# =====================================================================
# Sector proxy — direct commodity exposure
# =====================================================================


class TestDirectCommodityProxy:
    def test_mineracao_gets_90(self) -> None:
        score, prov = lookup_direct_commodity_proxy("Extração Mineral", None, AS_OF)
        assert score == 90.0

    def test_petroleo_gets_85(self) -> None:
        score, _ = lookup_direct_commodity_proxy("Petróleo e Gás", None, AS_OF)
        assert score == 85.0

    def test_siderurgia_gets_80(self) -> None:
        score, _ = lookup_direct_commodity_proxy("Metalurgia e Siderurgia", None, AS_OF)
        assert score == 80.0

    def test_papel_celulose_gets_75(self) -> None:
        score, _ = lookup_direct_commodity_proxy("Papel e Celulose", None, AS_OF)
        assert score == 75.0

    def test_agropecuaria_gets_70(self) -> None:
        score, _ = lookup_direct_commodity_proxy("Agricultura (Açúcar, Álcool e Cana)", None, AS_OF)
        assert score == 70.0

    def test_unknown_sector_gets_default(self) -> None:
        score, _ = lookup_direct_commodity_proxy("Financeiro", "Bancos", AS_OF)
        assert score == DEFAULT_PROXY_SCORE

    def test_none_sector_gets_default(self) -> None:
        score, _ = lookup_direct_commodity_proxy(None, None, AS_OF)
        assert score == DEFAULT_PROXY_SCORE

    def test_none_subsector_ignored_sector_still_matches(self) -> None:
        """Subsector is ignored; sector-only lookup with None subsector returns the mapped score."""
        score, _ = lookup_direct_commodity_proxy("Extração Mineral", None, AS_OF)
        assert score == 90.0

    def test_provenance_is_sector_proxy(self) -> None:
        _, prov = lookup_direct_commodity_proxy("Extração Mineral", None, AS_OF)
        assert prov.source_type == ScoreSourceType.SECTOR_PROXY
        assert prov.source_version == SECTOR_PROXY_VERSION
        assert prov.confidence == ScoreConfidence.LOW
        assert prov.assessed_at == AS_OF
        assert prov.assessed_by is None

    def test_provenance_evidence_ref_for_known_sector(self) -> None:
        _, prov = lookup_direct_commodity_proxy("Extração Mineral", None, AS_OF)
        assert "Extração Mineral" in (prov.evidence_ref or "")

    def test_provenance_evidence_ref_none_for_unknown(self) -> None:
        _, prov = lookup_direct_commodity_proxy("Financeiro", "Bancos", AS_OF)
        assert prov.evidence_ref is None

    def test_all_map_entries_have_rationale(self) -> None:
        for entry in DIRECT_COMMODITY_MAP:
            assert len(entry.rationale) > 0

    def test_all_map_scores_in_valid_range(self) -> None:
        for entry in DIRECT_COMMODITY_MAP:
            assert 0 <= entry.score <= 100


# =====================================================================
# Sector proxy — indirect commodity exposure
# =====================================================================


class TestIndirectCommodityProxy:
    def test_transporte_gets_55(self) -> None:
        score, _ = lookup_indirect_commodity_proxy("Serviços Transporte e Logística", None, AS_OF)
        assert score == 55.0

    def test_maquinas_gets_50(self) -> None:
        score, _ = lookup_indirect_commodity_proxy("Máquinas, Equipamentos, Veículos e Peças", None, AS_OF)
        assert score == 50.0

    def test_embalagens_gets_35(self) -> None:
        """Embalagens is a real CVM sector in the indirect map."""
        score, _ = lookup_indirect_commodity_proxy("Embalagens", None, AS_OF)
        assert score == 35.0

    def test_unknown_sector_gets_default(self) -> None:
        score, _ = lookup_indirect_commodity_proxy("Saude", "Medicamentos", AS_OF)
        assert score == DEFAULT_PROXY_SCORE

    def test_none_sector_gets_default(self) -> None:
        score, _ = lookup_indirect_commodity_proxy(None, None, AS_OF)
        assert score == DEFAULT_PROXY_SCORE

    def test_direct_commodity_sector_gets_default_in_indirect(self) -> None:
        """Extração Mineral has direct exposure, not indirect."""
        score, _ = lookup_indirect_commodity_proxy("Extração Mineral", None, AS_OF)
        assert score == DEFAULT_PROXY_SCORE

    def test_all_map_entries_have_rationale(self) -> None:
        for entry in INDIRECT_COMMODITY_MAP:
            assert len(entry.rationale) > 0

    def test_all_map_scores_in_valid_range(self) -> None:
        for entry in INDIRECT_COMMODITY_MAP:
            assert 0 <= entry.score <= 100


# =====================================================================
# Refinancing stress — quantitative
# =====================================================================


class TestRefinancingStress:
    def test_low_stress_healthy_company(self) -> None:
        """Low debt, high coverage => low stress."""
        score, prov, result = compute_refinancing_stress_score(
            short_term_debt=50_000,
            long_term_debt=200_000,
            debt_to_ebitda=1.5,
            interest_coverage=8.0,
            as_of_date=AS_OF,
        )
        assert score < 30.0
        assert result.is_complete is True
        assert prov.confidence == ScoreConfidence.HIGH

    def test_high_stress_distressed_company(self) -> None:
        """High short-term debt, high leverage, low coverage => high stress."""
        score, _, result = compute_refinancing_stress_score(
            short_term_debt=180_000,
            long_term_debt=20_000,
            debt_to_ebitda=5.5,
            interest_coverage=1.0,
            as_of_date=AS_OF,
        )
        assert score > 70.0
        assert result.is_complete is True

    def test_moderate_stress(self) -> None:
        """Balanced metrics => moderate stress."""
        score, _, _ = compute_refinancing_stress_score(
            short_term_debt=100_000,
            long_term_debt=100_000,
            debt_to_ebitda=3.0,
            interest_coverage=5.0,
            as_of_date=AS_OF,
        )
        assert 30.0 <= score <= 70.0

    def test_zero_debt_zero_stress(self) -> None:
        """No debt at all => minimal stress."""
        score, _, result = compute_refinancing_stress_score(
            short_term_debt=0,
            long_term_debt=0,
            debt_to_ebitda=0.0,
            interest_coverage=10.0,
            as_of_date=AS_OF,
        )
        assert score == 0.0
        assert result.short_term_debt_ratio_norm == 0.0
        assert result.leverage_component == 0.0
        assert result.coverage_component == 0.0

    def test_extreme_leverage_capped_at_100(self) -> None:
        """debt_to_ebitda > 6 should cap leverage component at 100."""
        _, _, result = compute_refinancing_stress_score(
            short_term_debt=0,
            long_term_debt=100_000,
            debt_to_ebitda=12.0,
            interest_coverage=10.0,
            as_of_date=AS_OF,
        )
        assert result.leverage_component == 100.0

    def test_excellent_coverage_gives_zero_component(self) -> None:
        """interest_coverage >= 10 => coverage component = 0."""
        _, _, result = compute_refinancing_stress_score(
            short_term_debt=0,
            long_term_debt=100_000,
            debt_to_ebitda=0.0,
            interest_coverage=15.0,
            as_of_date=AS_OF,
        )
        assert result.coverage_component == 0.0

    def test_zero_coverage_gives_max_component(self) -> None:
        """interest_coverage = 0 => coverage component = 100."""
        _, _, result = compute_refinancing_stress_score(
            short_term_debt=0,
            long_term_debt=100_000,
            debt_to_ebitda=0.0,
            interest_coverage=0.0,
            as_of_date=AS_OF,
        )
        assert result.coverage_component == 100.0

    def test_all_short_term_debt_gives_max_ratio(self) -> None:
        """100% short-term debt => ratio norm = 100."""
        _, _, result = compute_refinancing_stress_score(
            short_term_debt=100_000,
            long_term_debt=0,
            debt_to_ebitda=0.0,
            interest_coverage=10.0,
            as_of_date=AS_OF,
        )
        assert result.short_term_debt_ratio_norm == 100.0

    def test_known_value_computation(self) -> None:
        """Verify exact formula: 0.35 * 50 + 0.35 * 50 + 0.30 * 50 = 50.0"""
        # short_term_debt_ratio = 100_000 / 200_000 = 0.5 => norm = 50
        # leverage = 3.0 / 6.0 * 100 = 50
        # coverage = (1 - 5.0/10.0) * 100 = 50
        score, _, result = compute_refinancing_stress_score(
            short_term_debt=100_000,
            long_term_debt=100_000,
            debt_to_ebitda=3.0,
            interest_coverage=5.0,
            as_of_date=AS_OF,
        )
        assert result.short_term_debt_ratio_norm == 50.0
        assert result.leverage_component == 50.0
        assert result.coverage_component == 50.0
        assert score == 50.0

    def test_score_always_clamped_0_100(self) -> None:
        """Even with extreme inputs, score stays in [0, 100]."""
        score, _, _ = compute_refinancing_stress_score(
            short_term_debt=1_000_000,
            long_term_debt=0,
            debt_to_ebitda=20.0,
            interest_coverage=0.0,
            as_of_date=AS_OF,
        )
        assert 0 <= score <= 100

    # -- Missing data fallback --

    def test_missing_short_term_debt_returns_neutral(self) -> None:
        score, prov, result = compute_refinancing_stress_score(
            short_term_debt=None,
            long_term_debt=100_000,
            debt_to_ebitda=3.0,
            interest_coverage=5.0,
            as_of_date=AS_OF,
        )
        assert score == NEUTRAL_FALLBACK_SCORE
        assert result.is_complete is False
        assert prov.confidence == ScoreConfidence.LOW

    def test_missing_long_term_debt_returns_neutral(self) -> None:
        score, _, result = compute_refinancing_stress_score(
            short_term_debt=100_000,
            long_term_debt=None,
            debt_to_ebitda=3.0,
            interest_coverage=5.0,
            as_of_date=AS_OF,
        )
        assert score == NEUTRAL_FALLBACK_SCORE
        assert result.is_complete is False

    def test_missing_debt_to_ebitda_returns_neutral(self) -> None:
        score, _, result = compute_refinancing_stress_score(
            short_term_debt=100_000,
            long_term_debt=100_000,
            debt_to_ebitda=None,
            interest_coverage=5.0,
            as_of_date=AS_OF,
        )
        assert score == NEUTRAL_FALLBACK_SCORE
        assert result.is_complete is False

    def test_missing_interest_coverage_returns_neutral(self) -> None:
        score, _, result = compute_refinancing_stress_score(
            short_term_debt=100_000,
            long_term_debt=100_000,
            debt_to_ebitda=3.0,
            interest_coverage=None,
            as_of_date=AS_OF,
        )
        assert score == NEUTRAL_FALLBACK_SCORE
        assert result.is_complete is False

    def test_all_missing_returns_neutral(self) -> None:
        score, prov, result = compute_refinancing_stress_score(
            short_term_debt=None,
            long_term_debt=None,
            debt_to_ebitda=None,
            interest_coverage=None,
            as_of_date=AS_OF,
        )
        assert score == NEUTRAL_FALLBACK_SCORE
        assert result.is_complete is False
        assert "INCOMPLETE" in (prov.evidence_ref or "")

    # -- Provenance --

    def test_complete_provenance_is_quantitative_high(self) -> None:
        _, prov, _ = compute_refinancing_stress_score(
            short_term_debt=100_000,
            long_term_debt=100_000,
            debt_to_ebitda=3.0,
            interest_coverage=5.0,
            as_of_date=AS_OF,
        )
        assert prov.source_type == ScoreSourceType.QUANTITATIVE
        assert prov.confidence == ScoreConfidence.HIGH
        assert prov.assessed_at == AS_OF

    def test_incomplete_provenance_is_quantitative_low(self) -> None:
        _, prov, _ = compute_refinancing_stress_score(
            short_term_debt=None,
            long_term_debt=None,
            debt_to_ebitda=None,
            interest_coverage=None,
            as_of_date=AS_OF,
        )
        assert prov.source_type == ScoreSourceType.QUANTITATIVE
        assert prov.confidence == ScoreConfidence.LOW


# =====================================================================
# Draft builder integration
# =====================================================================


def _make_data(**overrides: object) -> IssuerFeatureData:
    defaults = dict(
        issuer_id="test-issuer-1",
        ticker="VALE3",
        sector="Extração Mineral",
        subsector=None,
        passed_core_screening=True,
        has_valid_financials=True,
        interest_coverage=5.0,
        debt_to_ebitda=2.0,
        core_rank_percentile=80.0,
        short_term_debt=50_000.0,
        long_term_debt=150_000.0,
    )
    defaults.update(overrides)
    return IssuerFeatureData(**defaults)  # type: ignore[arg-type]


class TestBuildFeatureDraft:
    def test_produces_three_automatic_scores(self) -> None:
        draft = build_feature_draft(_make_data(), AS_OF)
        assert draft.direct_commodity_exposure_score is not None
        assert draft.indirect_commodity_exposure_score is not None
        assert draft.refinancing_stress_score is not None

    def test_leaves_four_dimensions_none(self) -> None:
        draft = build_feature_draft(_make_data(), AS_OF)
        assert draft.export_fx_leverage_score is None
        assert draft.usd_debt_exposure_score is None
        assert draft.usd_import_dependence_score is None
        assert draft.usd_revenue_offset_score is None

    def test_direct_commodity_uses_sector_proxy(self) -> None:
        draft = build_feature_draft(
            _make_data(sector="Extração Mineral", subsector=None),
            AS_OF,
        )
        assert draft.direct_commodity_exposure_score == 90.0

    def test_indirect_commodity_for_transport(self) -> None:
        draft = build_feature_draft(
            _make_data(sector="Serviços Transporte e Logística", subsector=None),
            AS_OF,
        )
        assert draft.indirect_commodity_exposure_score == 55.0

    def test_refinancing_stress_is_computed(self) -> None:
        draft = build_feature_draft(
            _make_data(
                short_term_debt=100_000,
                long_term_debt=100_000,
                debt_to_ebitda=3.0,
                interest_coverage=5.0,
            ),
            AS_OF,
        )
        assert draft.refinancing_stress_score == 50.0

    def test_refinancing_stress_fallback_on_missing_data(self) -> None:
        draft = build_feature_draft(
            _make_data(short_term_debt=None, long_term_debt=None),
            AS_OF,
        )
        assert draft.refinancing_stress_score == NEUTRAL_FALLBACK_SCORE

    def test_eligibility_inputs_passed_through(self) -> None:
        draft = build_feature_draft(
            _make_data(
                passed_core_screening=True,
                has_valid_financials=True,
                interest_coverage=5.5,
                debt_to_ebitda=2.5,
                core_rank_percentile=75.0,
            ),
            AS_OF,
        )
        assert draft.passed_core_screening is True
        assert draft.has_valid_financials is True
        assert draft.interest_coverage == 5.5
        assert draft.debt_to_ebitda == 2.5
        assert draft.core_rank_percentile == 75.0

    def test_provenance_has_three_dimensions(self) -> None:
        draft = build_feature_draft(_make_data(), AS_OF)
        assert "direct_commodity_exposure" in draft.provenance
        assert "indirect_commodity_exposure" in draft.provenance
        assert "refinancing_stress" in draft.provenance
        assert len(draft.provenance) == 3

    def test_provenance_types_correct(self) -> None:
        draft = build_feature_draft(_make_data(), AS_OF)
        assert draft.provenance["direct_commodity_exposure"].source_type == ScoreSourceType.SECTOR_PROXY
        assert draft.provenance["indirect_commodity_exposure"].source_type == ScoreSourceType.SECTOR_PROXY
        assert draft.provenance["refinancing_stress"].source_type == ScoreSourceType.QUANTITATIVE

    def test_provenance_all_have_assessed_at(self) -> None:
        draft = build_feature_draft(_make_data(), AS_OF)
        for key, prov in draft.provenance.items():
            assert prov.assessed_at == AS_OF, f"Missing assessed_at for {key}"

    def test_unknown_sector_still_produces_draft(self) -> None:
        draft = build_feature_draft(
            _make_data(sector="Financeiro", subsector="Bancos"),
            AS_OF,
        )
        assert draft.direct_commodity_exposure_score == DEFAULT_PROXY_SCORE
        assert draft.indirect_commodity_exposure_score == DEFAULT_PROXY_SCORE

    def test_none_sector_still_produces_draft(self) -> None:
        draft = build_feature_draft(
            _make_data(sector=None, subsector=None),
            AS_OF,
        )
        assert draft.direct_commodity_exposure_score == DEFAULT_PROXY_SCORE
        assert draft.indirect_commodity_exposure_score == DEFAULT_PROXY_SCORE

    def test_issuer_id_and_ticker_passed_through(self) -> None:
        draft = build_feature_draft(
            _make_data(issuer_id="abc-123", ticker="PETR4"),
            AS_OF,
        )
        assert draft.issuer_id == "abc-123"
        assert draft.ticker == "PETR4"
