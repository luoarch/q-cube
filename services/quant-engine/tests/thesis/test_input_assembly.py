"""Tests for B2 Input Assembly — Plan2FeatureDraft → Plan2FeatureInput."""

from __future__ import annotations

from q3_quant_engine.thesis.input_assembly import (
    INPUT_ASSEMBLY_VERSION,
    RubricEntry,
    complete_feature_input,
)
from q3_quant_engine.thesis.types import (
    Plan2FeatureDraft,
    ScoreConfidence,
    ScoreProvenance,
    ScoreSourceType,
)


AS_OF = "2026-03-15"


def _make_draft(**overrides: object) -> Plan2FeatureDraft:
    """Create a Plan2FeatureDraft with sensible defaults for testing."""
    defaults = dict(
        issuer_id="test-issuer",
        ticker="TEST3",
        passed_core_screening=True,
        has_valid_financials=True,
        interest_coverage=5.0,
        debt_to_ebitda=2.0,
        core_rank_percentile=70.0,
        direct_commodity_exposure_score=80.0,
        indirect_commodity_exposure_score=40.0,
        export_fx_leverage_score=None,
        refinancing_stress_score=45.0,
        usd_debt_exposure_score=None,
        usd_import_dependence_score=None,
        usd_revenue_offset_score=None,
        provenance={
            "direct_commodity_exposure": ScoreProvenance(
                source_type=ScoreSourceType.SECTOR_PROXY,
                source_version="sector-proxy-v1",
                assessed_at=AS_OF,
            ),
            "indirect_commodity_exposure": ScoreProvenance(
                source_type=ScoreSourceType.SECTOR_PROXY,
                source_version="sector-proxy-v1",
                assessed_at=AS_OF,
            ),
            "refinancing_stress": ScoreProvenance(
                source_type=ScoreSourceType.QUANTITATIVE,
                source_version="quant-v1",
                assessed_at=AS_OF,
                confidence=ScoreConfidence.HIGH,
            ),
        },
    )
    defaults.update(overrides)
    return Plan2FeatureDraft(**defaults)  # type: ignore[arg-type]


class TestCompleteFeatureInput:
    """Tests for complete_feature_input."""

    def test_all_seven_scores_present(self) -> None:
        """Output has all 7 non-None dimension scores."""
        result = complete_feature_input(_make_draft(), AS_OF)
        assert result.direct_commodity_exposure_score is not None
        assert result.indirect_commodity_exposure_score is not None
        assert result.export_fx_leverage_score is not None
        assert result.refinancing_stress_score is not None
        assert result.usd_debt_exposure_score is not None
        assert result.usd_import_dependence_score is not None
        assert result.usd_revenue_offset_score is not None

    def test_preserves_f1_computed_scores(self) -> None:
        """Scores already computed by F1 are preserved as-is."""
        draft = _make_draft(
            direct_commodity_exposure_score=90.0,
            indirect_commodity_exposure_score=55.0,
            refinancing_stress_score=30.0,
        )
        result = complete_feature_input(draft, AS_OF)
        assert result.direct_commodity_exposure_score == 90.0
        assert result.indirect_commodity_exposure_score == 55.0
        assert result.refinancing_stress_score == 30.0

    def test_preserves_f1_provenance(self) -> None:
        """Provenance from F1 is preserved for dimensions F1 computed."""
        draft = _make_draft()
        result = complete_feature_input(draft, AS_OF)
        assert result.provenance["direct_commodity_exposure"].source_type == ScoreSourceType.SECTOR_PROXY
        assert result.provenance["direct_commodity_exposure"].source_version == "sector-proxy-v1"
        assert result.provenance["refinancing_stress"].source_type == ScoreSourceType.QUANTITATIVE
        assert result.provenance["refinancing_stress"].confidence == ScoreConfidence.HIGH


class TestExportFxLeverageDefault:
    """exportFxLeverage: derive from directCommodityExposure * 0.6."""

    def test_derived_from_direct_commodity(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=80.0, export_fx_leverage_score=None),
            AS_OF,
        )
        assert result.export_fx_leverage_score == 80.0 * 0.6  # 48.0

    def test_derived_provenance_is_derived(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=80.0, export_fx_leverage_score=None),
            AS_OF,
        )
        prov = result.provenance["export_fx_leverage"]
        assert prov.source_type == ScoreSourceType.DERIVED
        assert prov.confidence == ScoreConfidence.LOW
        assert "direct_commodity_exposure" in (prov.evidence_ref or "")

    def test_preserves_explicit_value(self) -> None:
        result = complete_feature_input(
            _make_draft(export_fx_leverage_score=65.0),
            AS_OF,
        )
        assert result.export_fx_leverage_score == 65.0

    def test_zero_direct_gives_zero_export_fx(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=0.0, export_fx_leverage_score=None),
            AS_OF,
        )
        assert result.export_fx_leverage_score == 0.0


class TestUsdDebtExposureDefault:
    """usdDebtExposure: default 30 (moderado)."""

    def test_default_is_30(self) -> None:
        result = complete_feature_input(
            _make_draft(usd_debt_exposure_score=None),
            AS_OF,
        )
        assert result.usd_debt_exposure_score == 30.0

    def test_default_provenance(self) -> None:
        result = complete_feature_input(
            _make_draft(usd_debt_exposure_score=None),
            AS_OF,
        )
        prov = result.provenance["usd_debt_exposure"]
        assert prov.source_type == ScoreSourceType.DEFAULT
        assert prov.confidence == ScoreConfidence.LOW

    def test_preserves_explicit_value(self) -> None:
        result = complete_feature_input(
            _make_draft(usd_debt_exposure_score=70.0),
            AS_OF,
        )
        assert result.usd_debt_exposure_score == 70.0


class TestUsdImportDependenceDefault:
    """usdImportDependence: default 20 (conservador)."""

    def test_default_is_20(self) -> None:
        result = complete_feature_input(
            _make_draft(usd_import_dependence_score=None),
            AS_OF,
        )
        assert result.usd_import_dependence_score == 20.0

    def test_default_provenance(self) -> None:
        result = complete_feature_input(
            _make_draft(usd_import_dependence_score=None),
            AS_OF,
        )
        prov = result.provenance["usd_import_dependence"]
        assert prov.source_type == ScoreSourceType.DEFAULT
        assert prov.confidence == ScoreConfidence.LOW

    def test_preserves_explicit_value(self) -> None:
        result = complete_feature_input(
            _make_draft(usd_import_dependence_score=55.0),
            AS_OF,
        )
        assert result.usd_import_dependence_score == 55.0


class TestUsdRevenueOffsetDefault:
    """usdRevenueOffset: if directCommodity >= 70 → derived, else default 10."""

    def test_derived_when_high_direct_commodity(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=90.0, usd_revenue_offset_score=None),
            AS_OF,
        )
        assert result.usd_revenue_offset_score == 90.0 * 0.7  # 63.0

    def test_derived_provenance(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=90.0, usd_revenue_offset_score=None),
            AS_OF,
        )
        prov = result.provenance["usd_revenue_offset"]
        assert prov.source_type == ScoreSourceType.DERIVED
        assert "direct_commodity_exposure" in (prov.evidence_ref or "")

    def test_default_when_low_direct_commodity(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=50.0, usd_revenue_offset_score=None),
            AS_OF,
        )
        assert result.usd_revenue_offset_score == 10.0

    def test_default_provenance_when_low_direct(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=50.0, usd_revenue_offset_score=None),
            AS_OF,
        )
        prov = result.provenance["usd_revenue_offset"]
        assert prov.source_type == ScoreSourceType.DEFAULT
        assert prov.confidence == ScoreConfidence.LOW

    def test_boundary_exactly_70_triggers_derivation(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=70.0, usd_revenue_offset_score=None),
            AS_OF,
        )
        assert result.usd_revenue_offset_score == 70.0 * 0.7  # 49.0

    def test_boundary_69_triggers_default(self) -> None:
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=69.0, usd_revenue_offset_score=None),
            AS_OF,
        )
        assert result.usd_revenue_offset_score == 10.0

    def test_preserves_explicit_value(self) -> None:
        result = complete_feature_input(
            _make_draft(usd_revenue_offset_score=80.0),
            AS_OF,
        )
        assert result.usd_revenue_offset_score == 80.0


class TestEligibilityPassthrough:
    """Eligibility inputs are passed through unchanged."""

    def test_passthrough(self) -> None:
        draft = _make_draft(
            passed_core_screening=True,
            has_valid_financials=False,
            interest_coverage=3.5,
            debt_to_ebitda=4.0,
            core_rank_percentile=55.0,
        )
        result = complete_feature_input(draft, AS_OF)
        assert result.passed_core_screening is True
        assert result.has_valid_financials is False
        assert result.interest_coverage == 3.5
        assert result.debt_to_ebitda == 4.0
        assert result.core_rank_percentile == 55.0


class TestProvenanceCoverage:
    """All 7 dimensions must have provenance after B2 completion."""

    def test_all_dimensions_have_provenance(self) -> None:
        """Draft with only 3 F1 dimensions → B2 fills 4 more provenance entries."""
        result = complete_feature_input(_make_draft(), AS_OF)
        expected_keys = {
            "direct_commodity_exposure",
            "indirect_commodity_exposure",
            "export_fx_leverage",
            "refinancing_stress",
            "usd_debt_exposure",
            "usd_import_dependence",
            "usd_revenue_offset",
        }
        assert set(result.provenance.keys()) == expected_keys

    def test_no_provenance_without_key(self) -> None:
        """B2 should not add any provenance key that doesn't correspond to a dimension."""
        result = complete_feature_input(_make_draft(), AS_OF)
        for key in result.provenance:
            assert key in {
                "direct_commodity_exposure",
                "indirect_commodity_exposure",
                "export_fx_leverage",
                "refinancing_stress",
                "usd_debt_exposure",
                "usd_import_dependence",
                "usd_revenue_offset",
            }

    def test_b2_does_not_overwrite_f1_provenance(self) -> None:
        """If F1 already set provenance for a dimension, B2 does not replace it."""
        draft = _make_draft()
        result = complete_feature_input(draft, AS_OF)
        # F1 set these — B2 should not change them
        assert result.provenance["direct_commodity_exposure"].source_version == "sector-proxy-v1"
        assert result.provenance["refinancing_stress"].source_version == "quant-v1"


class TestFullyPopulatedDraft:
    """When F1 provides ALL dimensions, B2 should not touch any scores."""

    def test_no_defaults_applied(self) -> None:
        draft = _make_draft(
            direct_commodity_exposure_score=90.0,
            indirect_commodity_exposure_score=55.0,
            export_fx_leverage_score=60.0,
            refinancing_stress_score=30.0,
            usd_debt_exposure_score=50.0,
            usd_import_dependence_score=40.0,
            usd_revenue_offset_score=70.0,
        )
        result = complete_feature_input(draft, AS_OF)
        assert result.direct_commodity_exposure_score == 90.0
        assert result.indirect_commodity_exposure_score == 55.0
        assert result.export_fx_leverage_score == 60.0
        assert result.refinancing_stress_score == 30.0
        assert result.usd_debt_exposure_score == 50.0
        assert result.usd_import_dependence_score == 40.0
        assert result.usd_revenue_offset_score == 70.0


class TestRubricOverrides:
    """Rubric scores override defaults but not F1 values."""

    def _rubric(self, score: float, source: str = "RUBRIC_MANUAL") -> RubricEntry:
        return RubricEntry(
            score=score,
            source_type=ScoreSourceType(source),
            source_version="rubric-test-v1",
            confidence=ScoreConfidence.MEDIUM,
            evidence_ref="test-evidence",
            assessed_at=AS_OF,
            assessed_by="tester",
        )

    def test_rubric_overrides_default_usd_debt(self) -> None:
        rubrics = {"usd_debt_exposure": self._rubric(75.0)}
        result = complete_feature_input(
            _make_draft(usd_debt_exposure_score=None), AS_OF, rubrics=rubrics,
        )
        assert result.usd_debt_exposure_score == 75.0

    def test_rubric_provenance_recorded(self) -> None:
        rubrics = {"usd_debt_exposure": self._rubric(75.0)}
        result = complete_feature_input(
            _make_draft(usd_debt_exposure_score=None), AS_OF, rubrics=rubrics,
        )
        prov = result.provenance["usd_debt_exposure"]
        assert prov.source_type == ScoreSourceType.RUBRIC_MANUAL
        assert prov.source_version == "rubric-test-v1"
        assert prov.confidence == ScoreConfidence.MEDIUM
        assert prov.evidence_ref == "test-evidence"
        assert prov.assessed_by == "tester"

    def test_rubric_does_not_override_f1(self) -> None:
        """F1 value (not None) takes priority over rubric."""
        rubrics = {"refinancing_stress": self._rubric(99.0)}
        result = complete_feature_input(
            _make_draft(refinancing_stress_score=45.0), AS_OF, rubrics=rubrics,
        )
        assert result.refinancing_stress_score == 45.0

    def test_rubric_overrides_default_usd_import(self) -> None:
        rubrics = {"usd_import_dependence": self._rubric(60.0)}
        result = complete_feature_input(
            _make_draft(usd_import_dependence_score=None), AS_OF, rubrics=rubrics,
        )
        assert result.usd_import_dependence_score == 60.0

    def test_rubric_overrides_derived_usd_revenue(self) -> None:
        """Rubric beats derived (direct >= 70 derivation)."""
        rubrics = {"usd_revenue_offset": self._rubric(85.0)}
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=90.0, usd_revenue_offset_score=None),
            AS_OF, rubrics=rubrics,
        )
        assert result.usd_revenue_offset_score == 85.0

    def test_rubric_overrides_derived_export_fx(self) -> None:
        """Rubric beats derived export_fx_leverage."""
        rubrics = {"export_fx_leverage": self._rubric(50.0)}
        result = complete_feature_input(
            _make_draft(direct_commodity_exposure_score=80.0, export_fx_leverage_score=None),
            AS_OF, rubrics=rubrics,
        )
        assert result.export_fx_leverage_score == 50.0

    def test_multiple_rubrics_applied(self) -> None:
        rubrics = {
            "usd_debt_exposure": self._rubric(70.0),
            "usd_import_dependence": self._rubric(55.0),
            "usd_revenue_offset": self._rubric(40.0),
        }
        result = complete_feature_input(
            _make_draft(
                usd_debt_exposure_score=None,
                usd_import_dependence_score=None,
                usd_revenue_offset_score=None,
            ),
            AS_OF, rubrics=rubrics,
        )
        assert result.usd_debt_exposure_score == 70.0
        assert result.usd_import_dependence_score == 55.0
        assert result.usd_revenue_offset_score == 40.0

    def test_ai_assisted_rubric(self) -> None:
        rubrics = {"usd_debt_exposure": self._rubric(65.0, source="AI_ASSISTED")}
        result = complete_feature_input(
            _make_draft(usd_debt_exposure_score=None), AS_OF, rubrics=rubrics,
        )
        assert result.usd_debt_exposure_score == 65.0
        assert result.provenance["usd_debt_exposure"].source_type == ScoreSourceType.AI_ASSISTED
