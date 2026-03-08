"""Tests for council agent profiles — SSOT and type safety."""

from __future__ import annotations

from q3_ai_assistant.council.profiles import ALL_PROFILES
from q3_ai_assistant.council.profiles.barsi_profile import BARSI_PROFILE
from q3_ai_assistant.council.profiles.buffett_profile import BUFFETT_PROFILE
from q3_ai_assistant.council.profiles.graham_profile import GRAHAM_PROFILE
from q3_ai_assistant.council.profiles.greenblatt_profile import GREENBLATT_PROFILE
from q3_ai_assistant.council.profiles.base import StrategyProfile


EXPECTED_AGENTS = {"barsi", "graham", "greenblatt", "buffett"}


class TestAllProfiles:
    def test_all_four_profiles_registered(self):
        assert set(ALL_PROFILES.keys()) == EXPECTED_AGENTS

    def test_all_profiles_are_strategy_profiles(self):
        for name, profile in ALL_PROFILES.items():
            assert isinstance(profile, StrategyProfile), f"{name} is not a StrategyProfile"

    def test_agent_id_matches_key(self):
        for key, profile in ALL_PROFILES.items():
            assert profile.agent_id == key, f"Profile key '{key}' != agent_id '{profile.agent_id}'"

    def test_all_profiles_frozen(self):
        for name, profile in ALL_PROFILES.items():
            try:
                profile.agent_id = "hacked"  # type: ignore[misc]
                assert False, f"Profile {name} is not frozen"
            except AttributeError:
                pass

    def test_all_profiles_have_hard_rejects(self):
        for name, profile in ALL_PROFILES.items():
            assert len(profile.hard_rejects) >= 1, f"{name} has no hard rejects"

    def test_all_profiles_have_core_metrics(self):
        for name, profile in ALL_PROFILES.items():
            assert len(profile.core_metrics) >= 3, f"{name} has too few core metrics"

    def test_all_profiles_have_soft_preferences(self):
        for name, profile in ALL_PROFILES.items():
            assert len(profile.soft_preferences) >= 2, f"{name} has too few soft preferences"

    def test_profile_version_is_positive(self):
        for name, profile in ALL_PROFILES.items():
            assert profile.profile_version >= 1, f"{name} has invalid profile_version"

    def test_hard_reject_codes_unique_per_agent(self):
        for name, profile in ALL_PROFILES.items():
            codes = [r.code for r in profile.hard_rejects]
            assert len(codes) == len(set(codes)), f"{name} has duplicate hard reject codes"

    def test_soft_pref_codes_unique_per_agent(self):
        for name, profile in ALL_PROFILES.items():
            codes = [p.code for p in profile.soft_preferences]
            assert len(codes) == len(set(codes)), f"{name} has duplicate soft pref codes"

    def test_soft_pref_weights_valid(self):
        valid_weights = {"strong", "moderate", "weak"}
        for name, profile in ALL_PROFILES.items():
            for pref in profile.soft_preferences:
                assert pref.weight in valid_weights, (
                    f"{name}/{pref.code} has invalid weight '{pref.weight}'"
                )


class TestBarsiProfile:
    def test_barsi_core_metrics(self):
        assert "earnings_yield" in BARSI_PROFILE.core_metrics
        assert "cash_from_operations" in BARSI_PROFILE.core_metrics

    def test_barsi_hard_rejects(self):
        codes = [r.code for r in BARSI_PROFILE.hard_rejects]
        assert "negative_fcf_3y" in codes
        assert "negative_ni_recurring" in codes

    def test_barsi_sector_exceptions(self):
        assert "bank" in BARSI_PROFILE.sector_exceptions


class TestGrahamProfile:
    def test_graham_core_metrics(self):
        assert "debt_to_ebitda" in GRAHAM_PROFILE.core_metrics

    def test_graham_hard_rejects(self):
        codes = [r.code for r in GRAHAM_PROFILE.hard_rejects]
        assert "high_leverage_expensive" in codes
        assert "negative_equity" in codes


class TestGreenblattProfile:
    def test_greenblatt_core_metrics(self):
        assert "earnings_yield" in GREENBLATT_PROFILE.core_metrics
        assert "roic" in GREENBLATT_PROFILE.core_metrics
        assert "ebit" in GREENBLATT_PROFILE.core_metrics

    def test_greenblatt_hard_rejects(self):
        codes = [r.code for r in GREENBLATT_PROFILE.hard_rejects]
        assert "negative_ebit" in codes
        assert "roic_consistently_low" in codes


class TestBuffettProfile:
    def test_buffett_core_metrics(self):
        assert "roe" in BUFFETT_PROFILE.core_metrics
        assert "gross_margin" in BUFFETT_PROFILE.core_metrics

    def test_buffett_hard_rejects(self):
        codes = [r.code for r in BUFFETT_PROFILE.hard_rejects]
        assert "roe_consistently_low" in codes
        assert "margin_collapse" in codes

    def test_buffett_has_moat_preference(self):
        codes = [p.code for p in BUFFETT_PROFILE.soft_preferences]
        assert "prefers_moat" in codes
