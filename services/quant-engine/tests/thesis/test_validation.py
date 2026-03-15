"""Tests for Plan 2 Validation Framework (MF-G).

Covers all 5 validation blocks:
1. Face validity
2. Distribution sanity
3. Sensitivity analysis
4. Evidence-weight sanity
5. Regression fixtures
"""

from __future__ import annotations

from q3_quant_engine.thesis.features.draft_builder import IssuerFeatureData, build_feature_draft
from q3_quant_engine.thesis.input_assembly import complete_feature_input
from q3_quant_engine.thesis.eligibility import check_base_eligibility
from q3_quant_engine.thesis.scoring import (
    assign_thesis_bucket,
    compute_final_commodity_affinity_score,
    compute_final_dollar_fragility_score,
    compute_thesis_rank_score,
    generate_explanation,
    sort_plan2_rank,
)
from q3_quant_engine.thesis.types import (
    BaseEligibility,
    EvidenceQuality,
    FragilityVector,
    OpportunityVector,
    Plan2FeatureInput,
    Plan2RankingSnapshot,
    ScoreConfidence,
    ScoreProvenance,
    ScoreSourceType,
    ThesisBucket,
)
from q3_quant_engine.thesis.validation.face_validity import (
    FaceValidityResult,
    GoldenCase,
    check_face_validity,
)
from q3_quant_engine.thesis.validation.distribution import (
    DistributionAlert,
    check_distribution_sanity,
)
from q3_quant_engine.thesis.validation.sensitivity import (
    SensitivityResult,
    run_sensitivity_analysis,
)
from q3_quant_engine.thesis.validation.evidence_sanity import (
    EvidenceSanityResult,
    check_evidence_sanity,
)


AS_OF = "2026-03-15"


# =====================================================================
# Helpers
# =====================================================================


def _make_snapshot(
    ticker: str,
    bucket: ThesisBucket | None = None,
    eligible: bool = True,
    thesis_rank_score: float | None = None,
    thesis_rank: int | None = None,
    provenance: dict[str, ScoreProvenance] | None = None,
) -> Plan2RankingSnapshot:
    return Plan2RankingSnapshot(
        issuer_id=f"id-{ticker}",
        ticker=ticker,
        company_name=f"Company {ticker}",
        sector=None,
        eligible=eligible,
        eligibility=BaseEligibility(eligible_for_plan2=eligible),
        bucket=bucket,
        thesis_rank_score=thesis_rank_score,
        thesis_rank=thesis_rank,
        provenance=provenance or {},
    )


def _make_input(
    ticker: str,
    direct: float = 50.0,
    indirect: float = 30.0,
    export_fx: float = 30.0,
    refinancing: float = 40.0,
    usd_debt: float = 30.0,
    usd_import: float = 20.0,
    usd_revenue: float = 40.0,
    core_rank: float = 60.0,
) -> Plan2FeatureInput:
    return Plan2FeatureInput(
        issuer_id=f"id-{ticker}",
        ticker=ticker,
        passed_core_screening=True,
        has_valid_financials=True,
        interest_coverage=5.0,
        debt_to_ebitda=2.0,
        core_rank_percentile=core_rank,
        direct_commodity_exposure_score=direct,
        indirect_commodity_exposure_score=indirect,
        export_fx_leverage_score=export_fx,
        refinancing_stress_score=refinancing,
        usd_debt_exposure_score=usd_debt,
        usd_import_dependence_score=usd_import,
        usd_revenue_offset_score=usd_revenue,
    )


def _prov(source_type: ScoreSourceType) -> ScoreProvenance:
    return ScoreProvenance(
        source_type=source_type,
        source_version="test-v1",
        assessed_at=AS_OF,
    )


def _mvp_provenance() -> dict[str, ScoreProvenance]:
    """Typical MVP provenance: 1 QUANTITATIVE + 2 PROXY + 4 DEFAULT/DERIVED."""
    return {
        "refinancing_stress": _prov(ScoreSourceType.QUANTITATIVE),
        "direct_commodity_exposure": _prov(ScoreSourceType.SECTOR_PROXY),
        "indirect_commodity_exposure": _prov(ScoreSourceType.SECTOR_PROXY),
        "export_fx_leverage": _prov(ScoreSourceType.DERIVED),
        "usd_debt_exposure": _prov(ScoreSourceType.DEFAULT),
        "usd_import_dependence": _prov(ScoreSourceType.DEFAULT),
        "usd_revenue_offset": _prov(ScoreSourceType.DERIVED),
    }


def _high_evidence_provenance() -> dict[str, ScoreProvenance]:
    """Provenance with majority hard evidence."""
    return {
        "refinancing_stress": _prov(ScoreSourceType.QUANTITATIVE),
        "direct_commodity_exposure": _prov(ScoreSourceType.RUBRIC_MANUAL),
        "indirect_commodity_exposure": _prov(ScoreSourceType.RUBRIC_MANUAL),
        "export_fx_leverage": _prov(ScoreSourceType.RUBRIC_MANUAL),
        "usd_debt_exposure": _prov(ScoreSourceType.RUBRIC_MANUAL),
        "usd_import_dependence": _prov(ScoreSourceType.DEFAULT),
        "usd_revenue_offset": _prov(ScoreSourceType.DEFAULT),
    }


# =====================================================================
# 1. Face Validity
# =====================================================================


class TestFaceValidity:
    def test_all_match(self) -> None:
        golden = [
            GoldenCase("VALE3", ThesisBucket.A_DIRECT, "mining"),
            GoldenCase("ITUB4", ThesisBucket.C_NEUTRAL, "bank"),
        ]
        snapshots = [
            _make_snapshot("VALE3", bucket=ThesisBucket.A_DIRECT),
            _make_snapshot("ITUB4", bucket=ThesisBucket.C_NEUTRAL),
        ]
        result = check_face_validity(snapshots, golden)
        assert result.matched == 2
        assert result.mismatched == 0
        assert result.missing == 0
        assert result.pass_rate == 1.0

    def test_mismatch_detected(self) -> None:
        golden = [
            GoldenCase("VALE3", ThesisBucket.A_DIRECT, "mining"),
        ]
        snapshots = [
            _make_snapshot("VALE3", bucket=ThesisBucket.C_NEUTRAL),
        ]
        result = check_face_validity(snapshots, golden)
        assert result.mismatched == 1
        assert result.pass_rate == 0.0
        assert result.details[0]["status"] == "MISMATCH"

    def test_missing_ticker(self) -> None:
        golden = [
            GoldenCase("VALE3", ThesisBucket.A_DIRECT, "mining"),
        ]
        result = check_face_validity([], golden)
        assert result.missing == 1
        assert result.details[0]["status"] == "MISSING"

    def test_ineligible_counts_as_mismatch(self) -> None:
        golden = [
            GoldenCase("VALE3", ThesisBucket.A_DIRECT, "mining"),
        ]
        snapshots = [
            _make_snapshot("VALE3", eligible=False),
        ]
        result = check_face_validity(snapshots, golden)
        assert result.mismatched == 1
        assert result.details[0]["status"] == "INELIGIBLE"

    def test_mixed_results(self) -> None:
        golden = [
            GoldenCase("VALE3", ThesisBucket.A_DIRECT, "mining"),
            GoldenCase("ITUB4", ThesisBucket.C_NEUTRAL, "bank"),
            GoldenCase("XXXX3", ThesisBucket.A_DIRECT, "unknown"),
        ]
        snapshots = [
            _make_snapshot("VALE3", bucket=ThesisBucket.A_DIRECT),
            _make_snapshot("ITUB4", bucket=ThesisBucket.A_DIRECT),  # wrong
        ]
        result = check_face_validity(snapshots, golden)
        assert result.matched == 1
        assert result.mismatched == 1
        assert result.missing == 1
        assert 0 < result.pass_rate < 1.0

    def test_empty_golden_set(self) -> None:
        result = check_face_validity([], [])
        assert result.total_cases == 0
        assert result.pass_rate == 0.0


# =====================================================================
# 2. Distribution Sanity
# =====================================================================


class TestDistributionSanity:
    def test_healthy_distribution_no_alerts(self) -> None:
        snapshots = [
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=80),
            _make_snapshot("A2", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=75),
            _make_snapshot("B1", bucket=ThesisBucket.B_INDIRECT, thesis_rank_score=65),
            _make_snapshot("C1", bucket=ThesisBucket.C_NEUTRAL, thesis_rank_score=50),
            _make_snapshot("C2", bucket=ThesisBucket.C_NEUTRAL, thesis_rank_score=45),
        ]
        alerts = check_distribution_sanity(snapshots)
        assert len(alerts) == 0

    def test_no_eligible_is_critical(self) -> None:
        alerts = check_distribution_sanity([])
        assert any(a.code == "NO_ELIGIBLE" for a in alerts)
        assert any(a.severity == "CRITICAL" for a in alerts)

    def test_few_eligible_warning(self) -> None:
        snapshots = [
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=80),
            _make_snapshot("A2", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=75),
        ]
        alerts = check_distribution_sanity(snapshots)
        assert any(a.code == "FEW_ELIGIBLE" for a in alerts)

    def test_no_a_direct_warning(self) -> None:
        snapshots = [
            _make_snapshot("B1", bucket=ThesisBucket.B_INDIRECT, thesis_rank_score=70),
            _make_snapshot("C1", bucket=ThesisBucket.C_NEUTRAL, thesis_rank_score=60),
            _make_snapshot("C2", bucket=ThesisBucket.C_NEUTRAL, thesis_rank_score=50),
        ]
        alerts = check_distribution_sanity(snapshots)
        assert any(a.code == "NO_A_DIRECT" for a in alerts)

    def test_high_fragile_concentration(self) -> None:
        snapshots = [
            _make_snapshot("D1", bucket=ThesisBucket.D_FRAGILE, thesis_rank_score=30),
            _make_snapshot("D2", bucket=ThesisBucket.D_FRAGILE, thesis_rank_score=25),
            _make_snapshot("D3", bucket=ThesisBucket.D_FRAGILE, thesis_rank_score=20),
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=80),
        ]
        alerts = check_distribution_sanity(snapshots)
        assert any(a.code == "HIGH_FRAGILE_PCT" for a in alerts)

    def test_bucket_concentration(self) -> None:
        snapshots = [
            _make_snapshot(f"C{i}", bucket=ThesisBucket.C_NEUTRAL, thesis_rank_score=50 + i)
            for i in range(9)
        ] + [
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=80),
        ]
        alerts = check_distribution_sanity(snapshots)
        assert any(a.code == "BUCKET_CONCENTRATION" for a in alerts)

    def test_narrow_score_spread(self) -> None:
        snapshots = [
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=50.0),
            _make_snapshot("A2", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=50.5),
            _make_snapshot("A3", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=51.0),
        ]
        alerts = check_distribution_sanity(snapshots)
        assert any(a.code == "NARROW_SCORE_SPREAD" for a in alerts)


# =====================================================================
# 3. Sensitivity Analysis
# =====================================================================


class TestSensitivityAnalysis:
    def _make_diverse_inputs(self) -> list[Plan2FeatureInput]:
        return [
            _make_input("VALE3", direct=90, indirect=10, refinancing=20, core_rank=85),
            _make_input("RUMO3", direct=20, indirect=55, refinancing=30, core_rank=70),
            _make_input("ITUB4", direct=10, indirect=10, refinancing=40, core_rank=60),
            _make_input("FRAG3", direct=10, indirect=10, refinancing=80, usd_debt=80, core_rank=40),
        ]

    def _make_baseline_snapshots(self, inputs: list[Plan2FeatureInput]) -> list[Plan2RankingSnapshot]:
        snapshots = []
        for inp in inputs:
            commodity = compute_final_commodity_affinity_score(
                inp.direct_commodity_exposure_score,
                inp.indirect_commodity_exposure_score,
                inp.export_fx_leverage_score,
            )
            fragility = compute_final_dollar_fragility_score(
                inp.refinancing_stress_score,
                inp.usd_debt_exposure_score,
                inp.usd_import_dependence_score,
                inp.usd_revenue_offset_score,
            )
            bucket = assign_thesis_bucket(
                inp.direct_commodity_exposure_score,
                inp.indirect_commodity_exposure_score,
                fragility,
            )
            rank_score = compute_thesis_rank_score(commodity, fragility, inp.core_rank_percentile)
            snapshots.append(_make_snapshot(
                inp.ticker,
                bucket=bucket,
                thesis_rank_score=rank_score,
            ))
        sorted_snaps = sort_plan2_rank(snapshots)
        return sorted_snaps

    def test_default_perturbations_run(self) -> None:
        inputs = self._make_diverse_inputs()
        baseline = self._make_baseline_snapshots(inputs)
        results = run_sensitivity_analysis(inputs, baseline)
        assert len(results) == 6  # 6 default perturbations
        for r in results:
            assert r.total_eligible == 4
            assert r.bucket_change_pct >= 0

    def test_no_change_with_identity_perturbation(self) -> None:
        inputs = self._make_diverse_inputs()
        baseline = self._make_baseline_snapshots(inputs)
        # No override = identity
        results = run_sensitivity_analysis(inputs, baseline, [("identity", {})])
        assert results[0].bucket_changes == 0

    def test_large_perturbation_causes_changes(self) -> None:
        inputs = self._make_diverse_inputs()
        baseline = self._make_baseline_snapshots(inputs)
        # Extreme: set A_DIRECT threshold to 200 (impossible to reach)
        results = run_sensitivity_analysis(
            inputs, baseline,
            [("extreme_A", {"a_direct_min_direct_commodity": 200.0})],
        )
        # VALE3 should lose A_DIRECT
        assert results[0].bucket_changes >= 1

    def test_result_has_details(self) -> None:
        inputs = self._make_diverse_inputs()
        baseline = self._make_baseline_snapshots(inputs)
        results = run_sensitivity_analysis(
            inputs, baseline,
            [("extreme_A", {"a_direct_min_direct_commodity": 200.0})],
        )
        if results[0].bucket_changes > 0:
            assert len(results[0].details) > 0
            assert "ticker" in results[0].details[0]


# =====================================================================
# 4. Evidence-Weight Sanity
# =====================================================================


class TestEvidenceSanity:
    def test_all_high_evidence_is_acceptable(self) -> None:
        snapshots = [
            _make_snapshot(
                f"T{i}", bucket=ThesisBucket.A_DIRECT,
                thesis_rank_score=90 - i, thesis_rank=i + 1,
                provenance=_high_evidence_provenance(),
            )
            for i in range(5)
        ]
        result = check_evidence_sanity(snapshots, top_n=5)
        assert result.high_evidence_count == 5
        assert result.low_evidence_count == 0
        assert result.is_acceptable is True

    def test_all_low_evidence_is_not_acceptable(self) -> None:
        low_prov = {
            "dim1": _prov(ScoreSourceType.DEFAULT),
            "dim2": _prov(ScoreSourceType.DERIVED),
            "dim3": _prov(ScoreSourceType.SECTOR_PROXY),
        }
        snapshots = [
            _make_snapshot(
                f"T{i}", bucket=ThesisBucket.C_NEUTRAL,
                thesis_rank_score=50 - i, thesis_rank=i + 1,
                provenance=low_prov,
            )
            for i in range(5)
        ]
        result = check_evidence_sanity(snapshots, top_n=5)
        assert result.low_evidence_count == 5
        assert result.is_acceptable is False

    def test_mixed_evidence_acceptable(self) -> None:
        snapshots = []
        for i in range(10):
            if i < 3:
                prov = _high_evidence_provenance()
            elif i < 7:
                prov = _mvp_provenance()  # MIXED
            else:
                prov = {"d": _prov(ScoreSourceType.DEFAULT)}  # LOW
            snapshots.append(_make_snapshot(
                f"T{i}", bucket=ThesisBucket.A_DIRECT,
                thesis_rank_score=90 - i, thesis_rank=i + 1,
                provenance=prov,
            ))
        result = check_evidence_sanity(snapshots, top_n=10)
        # 3 LOW out of 10 = 30% < 70% threshold → acceptable
        assert result.is_acceptable is True

    def test_mvp_typical_is_acceptable(self) -> None:
        """In MVP, most issuers have MIXED evidence. This should be acceptable."""
        snapshots = [
            _make_snapshot(
                f"T{i}", bucket=ThesisBucket.A_DIRECT,
                thesis_rank_score=80 - i, thesis_rank=i + 1,
                provenance=_mvp_provenance(),
            )
            for i in range(10)
        ]
        result = check_evidence_sanity(snapshots, top_n=10)
        # All MIXED → 0 LOW → acceptable
        assert result.low_evidence_count == 0
        assert result.is_acceptable is True

    def test_empty_snapshots(self) -> None:
        result = check_evidence_sanity([], top_n=10)
        assert result.top_n == 10
        assert result.is_acceptable is True  # no data = no violation

    def test_details_include_evidence_quality(self) -> None:
        snapshots = [
            _make_snapshot(
                "VALE3", bucket=ThesisBucket.A_DIRECT,
                thesis_rank_score=85, thesis_rank=1,
                provenance=_mvp_provenance(),
            )
        ]
        result = check_evidence_sanity(snapshots, top_n=1)
        assert len(result.details) == 1
        assert result.details[0]["evidence_quality"] == "MIXED_EVIDENCE"


# =====================================================================
# 5. Regression Fixtures
# =====================================================================


class TestRegressionFixtures:
    """Deterministic snapshot tests: same input → same output.

    These tests verify that the scoring engine is deterministic and that
    the full pipeline (F1 → B2 → A) produces expected results for known inputs.
    """

    def test_mining_company_gets_a_direct(self) -> None:
        """VALE-like profile: high direct commodity, low fragility → A_DIRECT."""
        data = IssuerFeatureData(
            issuer_id="fixture-vale",
            ticker="VALE3",
            sector="Extração Mineral",
            subsector=None,
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=8.0,
            debt_to_ebitda=1.5,
            core_rank_percentile=85.0,
            short_term_debt=30_000.0,
            long_term_debt=170_000.0,
        )
        draft = build_feature_draft(data, AS_OF)
        inp = complete_feature_input(draft, AS_OF)

        assert inp.direct_commodity_exposure_score == 90.0

        commodity = compute_final_commodity_affinity_score(
            inp.direct_commodity_exposure_score,
            inp.indirect_commodity_exposure_score,
            inp.export_fx_leverage_score,
        )
        fragility = compute_final_dollar_fragility_score(
            inp.refinancing_stress_score,
            inp.usd_debt_exposure_score,
            inp.usd_import_dependence_score,
            inp.usd_revenue_offset_score,
        )
        bucket = assign_thesis_bucket(
            inp.direct_commodity_exposure_score,
            inp.indirect_commodity_exposure_score,
            fragility,
        )
        assert bucket == ThesisBucket.A_DIRECT

        rank_score = compute_thesis_rank_score(commodity, fragility, inp.core_rank_percentile)
        assert rank_score > 50.0  # should be reasonably high

    def test_bank_gets_c_neutral(self) -> None:
        """ITUB-like profile: no commodity exposure → C_NEUTRAL."""
        data = IssuerFeatureData(
            issuer_id="fixture-itub",
            ticker="ITUB4",
            sector="Financeiro",
            subsector="Bancos",
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=6.0,
            debt_to_ebitda=3.0,
            core_rank_percentile=70.0,
            short_term_debt=500_000.0,
            long_term_debt=500_000.0,
        )
        draft = build_feature_draft(data, AS_OF)
        inp = complete_feature_input(draft, AS_OF)

        assert inp.direct_commodity_exposure_score == 10.0  # default

        commodity = compute_final_commodity_affinity_score(
            inp.direct_commodity_exposure_score,
            inp.indirect_commodity_exposure_score,
            inp.export_fx_leverage_score,
        )
        fragility = compute_final_dollar_fragility_score(
            inp.refinancing_stress_score,
            inp.usd_debt_exposure_score,
            inp.usd_import_dependence_score,
            inp.usd_revenue_offset_score,
        )
        bucket = assign_thesis_bucket(
            inp.direct_commodity_exposure_score,
            inp.indirect_commodity_exposure_score,
            fragility,
        )
        assert bucket == ThesisBucket.C_NEUTRAL

    def test_transport_company_could_be_b_indirect(self) -> None:
        """RUMO-like profile: indirect commodity exposure via logistics."""
        data = IssuerFeatureData(
            issuer_id="fixture-rumo",
            ticker="RUMO3",
            sector="Serviços Transporte e Logística",
            subsector=None,
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=4.0,
            debt_to_ebitda=3.0,
            core_rank_percentile=65.0,
            short_term_debt=80_000.0,
            long_term_debt=120_000.0,
        )
        draft = build_feature_draft(data, AS_OF)
        inp = complete_feature_input(draft, AS_OF)

        assert inp.indirect_commodity_exposure_score == 55.0
        # Note: B_INDIRECT requires indirect >= 50 AND fragility <= 65
        # With indirect=55, this hits B_INDIRECT threshold.
        # This test documents the current threshold behavior.

    def test_deterministic_scoring(self) -> None:
        """Same input twice → identical output."""
        data = IssuerFeatureData(
            issuer_id="fixture-det",
            ticker="DET3",
            sector="Extração Mineral",
            subsector=None,
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=2.0,
            core_rank_percentile=75.0,
            short_term_debt=100_000.0,
            long_term_debt=100_000.0,
        )

        draft1 = build_feature_draft(data, AS_OF)
        inp1 = complete_feature_input(draft1, AS_OF)

        draft2 = build_feature_draft(data, AS_OF)
        inp2 = complete_feature_input(draft2, AS_OF)

        assert inp1.direct_commodity_exposure_score == inp2.direct_commodity_exposure_score
        assert inp1.indirect_commodity_exposure_score == inp2.indirect_commodity_exposure_score
        assert inp1.refinancing_stress_score == inp2.refinancing_stress_score
        assert inp1.export_fx_leverage_score == inp2.export_fx_leverage_score
        assert inp1.usd_debt_exposure_score == inp2.usd_debt_exposure_score
        assert inp1.usd_import_dependence_score == inp2.usd_import_dependence_score
        assert inp1.usd_revenue_offset_score == inp2.usd_revenue_offset_score

    def test_ineligible_company_excluded(self) -> None:
        """Company failing eligibility gets no scoring."""
        data = IssuerFeatureData(
            issuer_id="fixture-bad",
            ticker="BAD3",
            sector="Extração Mineral",
            subsector=None,
            passed_core_screening=True,
            has_valid_financials=True,
            interest_coverage=0.5,  # below 1.5 threshold
            debt_to_ebitda=2.0,
            core_rank_percentile=50.0,
            short_term_debt=100_000.0,
            long_term_debt=100_000.0,
        )
        draft = build_feature_draft(data, AS_OF)
        eligibility = check_base_eligibility(
            draft.passed_core_screening,
            draft.has_valid_financials,
            draft.interest_coverage,
            draft.debt_to_ebitda,
        )
        assert eligibility.eligible_for_plan2 is False

    def test_ranking_order_stable_across_runs(self) -> None:
        """Two runs with same data produce identical ranking order."""
        inputs = [
            IssuerFeatureData(
                issuer_id=f"fixture-{t}",
                ticker=t,
                sector=s,
                subsector=sub,
                passed_core_screening=True,
                has_valid_financials=True,
                interest_coverage=5.0,
                debt_to_ebitda=2.0,
                core_rank_percentile=pct,
                short_term_debt=50_000.0,
                long_term_debt=150_000.0,
            )
            for t, s, sub, pct in [
                ("VALE3", "Extração Mineral", None, 85.0),
                ("ITUB4", "Financeiro", None, 70.0),
                ("PETR4", "Petróleo e Gás", None, 80.0),
            ]
        ]

        def _run_once() -> list[str]:
            snapshots = []
            for data in inputs:
                draft = build_feature_draft(data, AS_OF)
                inp = complete_feature_input(draft, AS_OF)
                eligibility = check_base_eligibility(
                    inp.passed_core_screening, inp.has_valid_financials,
                    inp.interest_coverage, inp.debt_to_ebitda,
                )
                if not eligibility.eligible_for_plan2:
                    continue
                commodity = compute_final_commodity_affinity_score(
                    inp.direct_commodity_exposure_score,
                    inp.indirect_commodity_exposure_score,
                    inp.export_fx_leverage_score,
                )
                fragility = compute_final_dollar_fragility_score(
                    inp.refinancing_stress_score,
                    inp.usd_debt_exposure_score,
                    inp.usd_import_dependence_score,
                    inp.usd_revenue_offset_score,
                )
                bucket = assign_thesis_bucket(
                    inp.direct_commodity_exposure_score,
                    inp.indirect_commodity_exposure_score,
                    fragility,
                )
                rank_score = compute_thesis_rank_score(commodity, fragility, inp.core_rank_percentile)
                snapshots.append(_make_snapshot(
                    inp.ticker, bucket=bucket, thesis_rank_score=rank_score,
                ))
            sorted_snaps = sort_plan2_rank(snapshots)
            return [s.ticker for s in sorted_snaps]

        order1 = _run_once()
        order2 = _run_once()
        assert order1 == order2

    def test_config_change_produces_different_output(self) -> None:
        """Sensitivity: changing a threshold changes the bucket assignment."""
        inp = _make_input("EDGE3", direct=70, indirect=10, refinancing=30)

        commodity = compute_final_commodity_affinity_score(
            inp.direct_commodity_exposure_score,
            inp.indirect_commodity_exposure_score,
            inp.export_fx_leverage_score,
        )
        fragility = compute_final_dollar_fragility_score(
            inp.refinancing_stress_score,
            inp.usd_debt_exposure_score,
            inp.usd_import_dependence_score,
            inp.usd_revenue_offset_score,
        )

        # With default thresholds (direct >= 70, fragility <= 60)
        bucket_default = assign_thesis_bucket(70.0, 10.0, fragility)

        # If we raise the threshold to 75, same input gets different bucket
        # (simulating: the scoring function takes scores, the threshold is in config)
        # For regression: this test documents that 70 is the boundary
        assert bucket_default == ThesisBucket.A_DIRECT  # direct=70 meets threshold
        bucket_69 = assign_thesis_bucket(69.0, 10.0, fragility)
        assert bucket_69 != ThesisBucket.A_DIRECT  # direct=69 does not
