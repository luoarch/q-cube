"""Tests for Plan 2 pipeline runner (MF-B2).

Tests the end-to-end flow: draft → complete → score → persist.
Uses mock objects to avoid DB dependency for unit testing.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from q3_quant_engine.thesis.input_assembly import complete_feature_input
from q3_quant_engine.thesis.features.draft_builder import IssuerFeatureData, build_feature_draft
from q3_quant_engine.thesis.eligibility import check_base_eligibility
from q3_quant_engine.thesis.pipeline import (
    PIPELINE_VERSION,
    _score_eligible_issuer,
    _make_ineligible_snapshot,
    _provenance_to_dict,
    run_plan2_pipeline,
)
from q3_quant_engine.thesis.config import THESIS_CONFIG_VERSION
from q3_shared_models.entities import Plan2Run
from q3_quant_engine.thesis.types import (
    BaseEligibility,
    Plan2FeatureDraft,
    Plan2FeatureInput,
    Plan2RankingSnapshot,
    ScoreConfidence,
    ScoreProvenance,
    ScoreSourceType,
    ThesisBucket,
)


AS_OF = "2026-03-15"
AS_OF_DATE = date(2026, 3, 15)


# =====================================================================
# Input Assembly integration (draft → complete → score)
# =====================================================================


def _make_feature_data(**overrides: object) -> IssuerFeatureData:
    defaults = dict(
        issuer_id="issuer-1",
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


class TestDraftToCompleteToScore:
    """Integration: F1 draft → B2 complete → A score."""

    def test_full_pipeline_for_eligible_commodity_issuer(self) -> None:
        """A mining company goes through the full pipeline."""
        data = _make_feature_data()
        draft = build_feature_draft(data, AS_OF)

        # Draft should have 3 scores, 4 None
        assert draft.direct_commodity_exposure_score == 90.0
        assert draft.export_fx_leverage_score is None
        assert draft.usd_debt_exposure_score is None

        # B2 complete
        feature_input = complete_feature_input(draft, AS_OF)

        # All 7 present
        assert feature_input.export_fx_leverage_score is not None
        assert feature_input.usd_debt_exposure_score is not None
        assert feature_input.usd_import_dependence_score is not None
        assert feature_input.usd_revenue_offset_score is not None

        # Provenance for all 7
        assert len(feature_input.provenance) == 7

        # Eligibility
        eligibility = check_base_eligibility(
            feature_input.passed_core_screening,
            feature_input.has_valid_financials,
            feature_input.interest_coverage,
            feature_input.debt_to_ebitda,
        )
        assert eligibility.eligible_for_plan2 is True

        # Score
        snapshot = _score_eligible_issuer(
            feature_input, eligibility, "Vale S.A.", "Extração Mineral",
        )
        assert snapshot.eligible is True
        assert snapshot.bucket == ThesisBucket.A_DIRECT  # mining + low fragility
        assert snapshot.thesis_rank_score is not None
        assert snapshot.thesis_rank_score > 0
        assert snapshot.explanation is not None
        assert snapshot.opportunity_vector is not None
        assert snapshot.fragility_vector is not None

    def test_ineligible_issuer_gets_no_scoring(self) -> None:
        """An ineligible issuer gets no vectors, no bucket, no rank."""
        snapshot = _make_ineligible_snapshot(
            issuer_id="bad-1",
            ticker="BAD3",
            company_name="Bad Corp",
            sector="Financeiro",
            eligibility=BaseEligibility(
                eligible_for_plan2=False,
                failed_reasons=["failed_core_screening"],
            ),
        )
        assert snapshot.eligible is False
        assert snapshot.bucket is None
        assert snapshot.thesis_rank_score is None
        assert snapshot.opportunity_vector is None
        assert snapshot.fragility_vector is None
        assert snapshot.explanation is None

    def test_neutral_sector_gets_low_commodity_scores(self) -> None:
        """A bank gets default proxy scores → likely C_NEUTRAL bucket."""
        data = _make_feature_data(
            ticker="ITUB4",
            sector="Financeiro",
            subsector="Bancos",
            core_rank_percentile=60.0,
        )
        draft = build_feature_draft(data, AS_OF)
        feature_input = complete_feature_input(draft, AS_OF)

        eligibility = check_base_eligibility(
            feature_input.passed_core_screening,
            feature_input.has_valid_financials,
            feature_input.interest_coverage,
            feature_input.debt_to_ebitda,
        )

        snapshot = _score_eligible_issuer(
            feature_input, eligibility, "Itau Unibanco", "Financeiro",
        )
        # Low commodity scores → should be C_NEUTRAL (not A or B)
        assert snapshot.bucket in (ThesisBucket.C_NEUTRAL, ThesisBucket.D_FRAGILE)

    def test_missing_financial_data_still_produces_snapshot(self) -> None:
        """Issuer with missing debt data → refinancing stress gets fallback."""
        data = _make_feature_data(
            short_term_debt=None,
            long_term_debt=None,
        )
        draft = build_feature_draft(data, AS_OF)
        assert draft.refinancing_stress_score == 50.0  # neutral fallback

        feature_input = complete_feature_input(draft, AS_OF)
        eligibility = check_base_eligibility(
            feature_input.passed_core_screening,
            feature_input.has_valid_financials,
            feature_input.interest_coverage,
            feature_input.debt_to_ebitda,
        )

        snapshot = _score_eligible_issuer(
            feature_input, eligibility, "Test Corp", "Extração Mineral",
        )
        assert snapshot.eligible is True
        assert snapshot.thesis_rank_score is not None


class TestProvenancePreservation:
    """B2 must preserve the distinction between F1-computed and B2-defaulted."""

    def test_provenance_types_distinguish_source(self) -> None:
        data = _make_feature_data()
        draft = build_feature_draft(data, AS_OF)
        feature_input = complete_feature_input(draft, AS_OF)

        prov = feature_input.provenance

        # F1 computed dimensions
        assert prov["direct_commodity_exposure"].source_type == ScoreSourceType.SECTOR_PROXY
        assert prov["indirect_commodity_exposure"].source_type == ScoreSourceType.SECTOR_PROXY
        assert prov["refinancing_stress"].source_type == ScoreSourceType.QUANTITATIVE

        # B2 filled dimensions
        assert prov["export_fx_leverage"].source_type == ScoreSourceType.DERIVED
        assert prov["usd_debt_exposure"].source_type == ScoreSourceType.DEFAULT
        assert prov["usd_import_dependence"].source_type == ScoreSourceType.DEFAULT
        # usd_revenue_offset: DERIVED when directCommodity >= 70
        assert prov["usd_revenue_offset"].source_type == ScoreSourceType.DERIVED

    def test_confidence_levels_reflect_quality(self) -> None:
        data = _make_feature_data()
        draft = build_feature_draft(data, AS_OF)
        feature_input = complete_feature_input(draft, AS_OF)

        prov = feature_input.provenance

        # Quantitative → HIGH
        assert prov["refinancing_stress"].confidence == ScoreConfidence.HIGH
        # Sector proxy → LOW
        assert prov["direct_commodity_exposure"].confidence == ScoreConfidence.LOW
        # Defaults/derived → LOW
        assert prov["usd_debt_exposure"].confidence == ScoreConfidence.LOW
        assert prov["export_fx_leverage"].confidence == ScoreConfidence.LOW


class TestProvenanceSerialization:
    """Test that provenance can be serialized for persistence."""

    def test_provenance_to_dict(self) -> None:
        prov = {
            "test": ScoreProvenance(
                source_type=ScoreSourceType.QUANTITATIVE,
                source_version="v1",
                assessed_at=AS_OF,
                confidence=ScoreConfidence.HIGH,
            )
        }
        result = _provenance_to_dict(prov)
        assert isinstance(result["test"], dict)
        assert result["test"]["source_type"] == "QUANTITATIVE"
        assert result["test"]["source_version"] == "v1"


# =====================================================================
# Pipeline runner (with mock session)
# =====================================================================


def _mock_issuer(
    issuer_id: str = "00000000-0000-0000-0000-000000000001",
    cvm_code: str = "1234",
    legal_name: str = "Test Corp S.A.",
    trade_name: str | None = "Test Corp",
    sector: str | None = "Extração Mineral",
    subsector: str | None = None,
) -> SimpleNamespace:
    """Create a mock Issuer object."""
    return SimpleNamespace(
        id=uuid.UUID(issuer_id),
        cvm_code=cvm_code,
        legal_name=legal_name,
        trade_name=trade_name,
        sector=sector,
        subsector=subsector,
    )


class TestRunPlan2Pipeline:
    """Tests for run_plan2_pipeline using a mock session."""

    def _make_mock_session(self) -> MagicMock:
        session = MagicMock()
        session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None),
            all=MagicMock(return_value=[]),
        )
        return session

    @patch("q3_quant_engine.thesis.pipeline._build_issuer_feature_data")
    def test_creates_plan2_run(self, mock_build: MagicMock) -> None:
        """Pipeline creates a plan2_run record."""
        session = self._make_mock_session()

        mock_build.return_value = IssuerFeatureData(
            issuer_id="00000000-0000-0000-0000-000000000001",
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

        issuer = _mock_issuer()
        strategy_run_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        result = run_plan2_pipeline(
            session=session,
            strategy_run_id=strategy_run_id,
            tenant_id=tenant_id,
            issuer_universe=[(issuer, 80.0, True)],
            as_of_date=AS_OF_DATE,
        )

        # Plan2Run was created
        assert result.status == "completed"
        assert result.thesis_config_version == THESIS_CONFIG_VERSION
        assert result.pipeline_version == PIPELINE_VERSION
        assert result.total_eligible == 1
        assert result.total_ineligible == 0
        assert result.completed_at is not None

    @patch("q3_quant_engine.thesis.pipeline._build_issuer_feature_data")
    def test_ineligible_issuer_counted(self, mock_build: MagicMock) -> None:
        """Ineligible issuers are counted but not scored."""
        session = self._make_mock_session()

        mock_build.return_value = IssuerFeatureData(
            issuer_id="00000000-0000-0000-0000-000000000001",
            ticker="BAD3",
            sector="Financeiro",
            subsector="Bancos",
            passed_core_screening=False,  # fails eligibility
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=2.0,
            core_rank_percentile=50.0,
            short_term_debt=50_000.0,
            long_term_debt=150_000.0,
        )

        issuer = _mock_issuer(
            issuer_id="00000000-0000-0000-0000-000000000001",
            sector="Financeiro",
            subsector="Bancos",
        )

        result = run_plan2_pipeline(
            session=session,
            strategy_run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            issuer_universe=[(issuer, 50.0, True)],
            as_of_date=AS_OF_DATE,
        )

        assert result.total_eligible == 0
        assert result.total_ineligible == 1

    @patch("q3_quant_engine.thesis.pipeline._build_issuer_feature_data")
    def test_mixed_universe(self, mock_build: MagicMock) -> None:
        """Mix of eligible and ineligible issuers."""
        session = self._make_mock_session()

        eligible_data = IssuerFeatureData(
            issuer_id="00000000-0000-0000-0000-000000000001",
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

        ineligible_data = IssuerFeatureData(
            issuer_id="00000000-0000-0000-0000-000000000002",
            ticker="BAD3",
            sector="Financeiro",
            subsector="Bancos",
            passed_core_screening=False,
            has_valid_financials=True,
            interest_coverage=5.0,
            debt_to_ebitda=2.0,
            core_rank_percentile=50.0,
            short_term_debt=50_000.0,
            long_term_debt=150_000.0,
        )

        mock_build.side_effect = [eligible_data, ineligible_data]

        issuer1 = _mock_issuer(
            issuer_id="00000000-0000-0000-0000-000000000001",
        )
        issuer2 = _mock_issuer(
            issuer_id="00000000-0000-0000-0000-000000000002",
            sector="Financeiro",
            subsector="Bancos",
        )

        result = run_plan2_pipeline(
            session=session,
            strategy_run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            issuer_universe=[(issuer1, 80.0, True), (issuer2, 50.0, True)],
            as_of_date=AS_OF_DATE,
        )

        assert result.total_eligible == 1
        assert result.total_ineligible == 1

    @patch("q3_quant_engine.thesis.pipeline._build_issuer_feature_data")
    def test_bucket_distribution_recorded(self, mock_build: MagicMock) -> None:
        """Bucket distribution JSON is recorded on the run."""
        session = self._make_mock_session()

        mock_build.return_value = IssuerFeatureData(
            issuer_id="00000000-0000-0000-0000-000000000001",
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

        result = run_plan2_pipeline(
            session=session,
            strategy_run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            issuer_universe=[(_mock_issuer(), 80.0, True)],
            as_of_date=AS_OF_DATE,
        )

        assert isinstance(result.bucket_distribution_json, dict)
        # At least one bucket should have count > 0
        assert sum(result.bucket_distribution_json.values()) == 1

    @patch("q3_quant_engine.thesis.pipeline._build_issuer_feature_data")
    def test_session_add_called_for_run_and_scores(self, mock_build: MagicMock) -> None:
        """Verify persistence: session.add called for Plan2Run + Plan2ThesisScore."""
        session = self._make_mock_session()

        mock_build.return_value = IssuerFeatureData(
            issuer_id="00000000-0000-0000-0000-000000000001",
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

        run_plan2_pipeline(
            session=session,
            strategy_run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            issuer_universe=[(_mock_issuer(), 80.0, True)],
            as_of_date=AS_OF_DATE,
        )

        # session.add called at least twice: 1 Plan2Run + 1 Plan2ThesisScore
        add_calls = session.add.call_args_list
        assert len(add_calls) >= 2

        # First add is the Plan2Run
        first_added = add_calls[0][0][0]
        assert isinstance(first_added, Plan2Run)

    @patch("q3_quant_engine.thesis.pipeline._build_issuer_feature_data")
    def test_rerun_creates_new_run_preserves_history(self, mock_build: MagicMock) -> None:
        """Two pipeline runs create two separate Plan2Run records."""
        session = self._make_mock_session()

        mock_build.return_value = IssuerFeatureData(
            issuer_id="00000000-0000-0000-0000-000000000001",
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

        strategy_run_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        universe = [(_mock_issuer(), 80.0, True)]

        run1 = run_plan2_pipeline(
            session=session,
            strategy_run_id=strategy_run_id,
            tenant_id=tenant_id,
            issuer_universe=universe,
            as_of_date=AS_OF_DATE,
        )

        run2 = run_plan2_pipeline(
            session=session,
            strategy_run_id=strategy_run_id,
            tenant_id=tenant_id,
            issuer_universe=universe,
            as_of_date=AS_OF_DATE,
        )

        # Two different run IDs — history preserved
        assert run1.id != run2.id
        assert run1.status == "completed"
        assert run2.status == "completed"

    @patch("q3_quant_engine.thesis.pipeline._build_issuer_feature_data")
    def test_versioning_recorded(self, mock_build: MagicMock) -> None:
        """Plan2Run records thesis_config_version and pipeline_version."""
        session = self._make_mock_session()

        mock_build.return_value = IssuerFeatureData(
            issuer_id="00000000-0000-0000-0000-000000000001",
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

        result = run_plan2_pipeline(
            session=session,
            strategy_run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            issuer_universe=[(_mock_issuer(), 80.0, True)],
            as_of_date=AS_OF_DATE,
        )

        assert result.thesis_config_version == THESIS_CONFIG_VERSION
        assert result.pipeline_version == PIPELINE_VERSION

    @patch("q3_quant_engine.thesis.pipeline._build_issuer_feature_data")
    def test_empty_universe(self, mock_build: MagicMock) -> None:
        """Empty universe still creates a completed run."""
        session = self._make_mock_session()

        result = run_plan2_pipeline(
            session=session,
            strategy_run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            issuer_universe=[],
            as_of_date=AS_OF_DATE,
        )

        assert result.status == "completed"
        assert result.total_eligible == 0
        assert result.total_ineligible == 0
        assert result.bucket_distribution_json == {}
