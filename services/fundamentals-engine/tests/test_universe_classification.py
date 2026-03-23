"""Tests for the investable universe classification engine (Plan 4)."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from q3_fundamentals_engine.universe.types import (
    ClassificationRuleCode,
    DedicatedStrategyType,
    PermanentExclusionReason,
    UniverseClass,
)
from q3_fundamentals_engine.universe.policy import (
    ISSUER_OVERRIDES,
    POLICY_VERSION,
    SECTOR_UNIVERSE_MAP,
    NullSectorWithoutOverrideError,
    SectorPolicy,
    UnmatchedSectorError,
    lookup_policy,
    normalize_sector,
)


# ---------------------------------------------------------------------------
# Policy module tests
# ---------------------------------------------------------------------------


class TestSectorUniverseMap:
    def test_has_56_entries(self):
        assert len(SECTOR_UNIVERSE_MAP) == 56

    def test_all_core_eligible_have_no_dedicated_or_exclusion(self):
        for sector, policy in SECTOR_UNIVERSE_MAP.items():
            if policy.universe_class == UniverseClass.CORE_ELIGIBLE:
                assert policy.dedicated_strategy_type is None, f"{sector} CORE but has dedicated_strategy_type"
                assert policy.permanent_exclusion_reason is None, f"{sector} CORE but has exclusion reason"

    def test_all_dedicated_have_strategy_type(self):
        for sector, policy in SECTOR_UNIVERSE_MAP.items():
            if policy.universe_class == UniverseClass.DEDICATED_STRATEGY_ONLY:
                assert policy.dedicated_strategy_type is not None, f"{sector} DEDICATED but no strategy type"
                assert policy.permanent_exclusion_reason is None, f"{sector} DEDICATED but has exclusion reason"

    def test_all_excluded_have_exclusion_reason(self):
        for sector, policy in SECTOR_UNIVERSE_MAP.items():
            if policy.universe_class == UniverseClass.PERMANENTLY_EXCLUDED:
                assert policy.permanent_exclusion_reason is not None, f"{sector} EXCLUDED but no exclusion reason"
                assert policy.dedicated_strategy_type is None, f"{sector} EXCLUDED but has dedicated type"

    def test_all_have_reason_text(self):
        for sector, policy in SECTOR_UNIVERSE_MAP.items():
            assert policy.reason, f"{sector} has empty reason"

    def test_core_count(self):
        core = [s for s, p in SECTOR_UNIVERSE_MAP.items() if p.universe_class == UniverseClass.CORE_ELIGIBLE]
        assert len(core) == 37

    def test_financial_count(self):
        fin = [s for s, p in SECTOR_UNIVERSE_MAP.items()
               if p.dedicated_strategy_type == DedicatedStrategyType.FINANCIAL]
        assert len(fin) == 12

    def test_real_estate_count(self):
        re = [s for s, p in SECTOR_UNIVERSE_MAP.items()
              if p.dedicated_strategy_type == DedicatedStrategyType.REAL_ESTATE_DEVELOPMENT]
        assert len(re) == 2

    def test_unclassified_holding_count(self):
        uc = [s for s, p in SECTOR_UNIVERSE_MAP.items()
              if p.dedicated_strategy_type == DedicatedStrategyType.UNCLASSIFIED_HOLDING]
        assert len(uc) == 1

    def test_excluded_count(self):
        excl = [s for s, p in SECTOR_UNIVERSE_MAP.items()
                if p.universe_class == UniverseClass.PERMANENTLY_EXCLUDED]
        assert len(excl) == 4


class TestIssuerOverrides:
    def test_gol_is_excluded_airline(self):
        p = ISSUER_OVERRIDES["019569"]
        assert p.universe_class == UniverseClass.PERMANENTLY_EXCLUDED
        assert p.permanent_exclusion_reason == PermanentExclusionReason.AIRLINE

    def test_azul_is_excluded_airline(self):
        p = ISSUER_OVERRIDES["024112"]
        assert p.universe_class == UniverseClass.PERMANENTLY_EXCLUDED
        assert p.permanent_exclusion_reason == PermanentExclusionReason.AIRLINE

    def test_ibov_is_excluded_not_a_company(self):
        p = ISSUER_OVERRIDES["IBOV"]
        assert p.universe_class == UniverseClass.PERMANENTLY_EXCLUDED
        assert p.permanent_exclusion_reason == PermanentExclusionReason.NOT_A_COMPANY

    def test_exito_is_excluded_foreign_retail(self):
        p = ISSUER_OVERRIDES["080225"]
        assert p.universe_class == UniverseClass.PERMANENTLY_EXCLUDED
        assert p.permanent_exclusion_reason == PermanentExclusionReason.FOREIGN_RETAIL

    def test_aura_minerals_is_core(self):
        p = ISSUER_OVERRIDES["080187"]
        assert p.universe_class == UniverseClass.CORE_ELIGIBLE

    def test_jbs_nv_is_core(self):
        p = ISSUER_OVERRIDES["080233"]
        assert p.universe_class == UniverseClass.CORE_ELIGIBLE

    def test_dexco_construction_override_is_core(self):
        p = ISSUER_OVERRIDES["021091"]
        assert p.universe_class == UniverseClass.CORE_ELIGIBLE

    def test_csu_digital_sem_setor_override_is_core(self):
        p = ISSUER_OVERRIDES["020044"]
        assert p.universe_class == UniverseClass.CORE_ELIGIBLE

    def test_inter_co_is_dedicated_financial(self):
        p = ISSUER_OVERRIDES["080217"]
        assert p.universe_class == UniverseClass.DEDICATED_STRATEGY_ONLY
        assert p.dedicated_strategy_type == DedicatedStrategyType.FINANCIAL


class TestNormalizeSector:
    def test_strips_whitespace(self):
        assert normalize_sector("  Bancos  ") == "Bancos"

    def test_none_returns_none(self):
        assert normalize_sector(None) is None

    def test_preserves_accents(self):
        assert normalize_sector("Petróleo e Gás") == "Petróleo e Gás"


class TestLookupPolicy:
    def test_override_takes_priority_over_sector_map(self):
        # GOL is in "Serviços Transporte e Logística" (CORE), but override says EXCLUDED
        policy, rule = lookup_policy("019569", "Serviços Transporte e Logística")
        assert policy.universe_class == UniverseClass.PERMANENTLY_EXCLUDED
        assert rule == ClassificationRuleCode.ISSUER_OVERRIDE

    def test_sector_map_lookup(self):
        policy, rule = lookup_policy("999999", "Bancos")
        assert policy.universe_class == UniverseClass.DEDICATED_STRATEGY_ONLY
        assert policy.dedicated_strategy_type == DedicatedStrategyType.FINANCIAL
        assert rule == ClassificationRuleCode.SECTOR_MAP

    def test_unmatched_sector_raises(self):
        with pytest.raises(UnmatchedSectorError) as exc_info:
            lookup_policy("999999", "Setor Imaginário")
        assert exc_info.value.sector == "Setor Imaginário"
        assert exc_info.value.cvm_code == "999999"

    def test_null_sector_without_override_raises(self):
        with pytest.raises(NullSectorWithoutOverrideError) as exc_info:
            lookup_policy("999999", None)
        assert exc_info.value.cvm_code == "999999"

    def test_null_sector_with_override_works(self):
        policy, rule = lookup_policy("IBOV", None)
        assert policy.universe_class == UniverseClass.PERMANENTLY_EXCLUDED
        assert rule == ClassificationRuleCode.ISSUER_OVERRIDE

    def test_construction_default_is_real_estate(self):
        policy, rule = lookup_policy("999999", "Construção Civil, Mat. Constr. e Decoração")
        assert policy.universe_class == UniverseClass.DEDICATED_STRATEGY_ONLY
        assert policy.dedicated_strategy_type == DedicatedStrategyType.REAL_ESTATE_DEVELOPMENT

    def test_construction_override_is_core(self):
        # Dexco is overridden to CORE_ELIGIBLE
        policy, rule = lookup_policy("021091", "Construção Civil, Mat. Constr. e Decoração")
        assert policy.universe_class == UniverseClass.CORE_ELIGIBLE
        assert rule == ClassificationRuleCode.ISSUER_OVERRIDE

    def test_sem_setor_default_is_unclassified_holding(self):
        policy, rule = lookup_policy("999999", "Emp. Adm. Part. - Sem Setor Principal")
        assert policy.universe_class == UniverseClass.DEDICATED_STRATEGY_ONLY
        assert policy.dedicated_strategy_type == DedicatedStrategyType.UNCLASSIFIED_HOLDING

    def test_whitespace_in_sector_is_normalized(self):
        policy, rule = lookup_policy("999999", "  Bancos  ")
        assert policy.universe_class == UniverseClass.DEDICATED_STRATEGY_ONLY


class TestPolicyVersion:
    def test_version_is_v1(self):
        assert POLICY_VERSION == "v1"
