"""Tests for Plan 2 coverage and evidence quality assessment."""

from __future__ import annotations

from q3_quant_engine.thesis.coverage import compute_coverage_summary
from q3_quant_engine.thesis.types import (
    CoverageSummary,
    EvidenceQuality,
    ScoreConfidence,
    ScoreProvenance,
    ScoreSourceType,
)


def _prov(source_type: ScoreSourceType) -> ScoreProvenance:
    return ScoreProvenance(
        source_type=source_type,
        source_version="test-v1",
        assessed_at="2026-03-15",
    )


class TestComputeCoverageSummary:
    def test_empty_provenance(self) -> None:
        result = compute_coverage_summary({})
        assert result.total_dimensions == 0
        assert result.evidence_quality == EvidenceQuality.LOW_EVIDENCE

    def test_all_quantitative_is_high_evidence(self) -> None:
        prov = {
            "dim1": _prov(ScoreSourceType.QUANTITATIVE),
            "dim2": _prov(ScoreSourceType.QUANTITATIVE),
            "dim3": _prov(ScoreSourceType.QUANTITATIVE),
        }
        result = compute_coverage_summary(prov)
        assert result.evidence_quality == EvidenceQuality.HIGH_EVIDENCE
        assert result.quantitative_count == 3
        assert result.quantitative_pct == 100.0

    def test_all_default_is_low_evidence(self) -> None:
        prov = {
            "dim1": _prov(ScoreSourceType.DEFAULT),
            "dim2": _prov(ScoreSourceType.DEFAULT),
            "dim3": _prov(ScoreSourceType.DERIVED),
        }
        result = compute_coverage_summary(prov)
        assert result.evidence_quality == EvidenceQuality.LOW_EVIDENCE
        assert result.quantitative_count == 0
        assert result.rubric_manual_count == 0

    def test_all_sector_proxy_is_low_evidence(self) -> None:
        """Sector proxy alone is not hard evidence."""
        prov = {
            "dim1": _prov(ScoreSourceType.SECTOR_PROXY),
            "dim2": _prov(ScoreSourceType.SECTOR_PROXY),
            "dim3": _prov(ScoreSourceType.DERIVED),
        }
        result = compute_coverage_summary(prov)
        assert result.evidence_quality == EvidenceQuality.LOW_EVIDENCE

    def test_majority_hard_evidence_is_high(self) -> None:
        """4/7 QUANTITATIVE + RUBRIC = 57% → HIGH_EVIDENCE."""
        prov = {
            "dim1": _prov(ScoreSourceType.QUANTITATIVE),
            "dim2": _prov(ScoreSourceType.RUBRIC_MANUAL),
            "dim3": _prov(ScoreSourceType.RUBRIC_MANUAL),
            "dim4": _prov(ScoreSourceType.RUBRIC_MANUAL),
            "dim5": _prov(ScoreSourceType.SECTOR_PROXY),
            "dim6": _prov(ScoreSourceType.DERIVED),
            "dim7": _prov(ScoreSourceType.DEFAULT),
        }
        result = compute_coverage_summary(prov)
        assert result.evidence_quality == EvidenceQuality.HIGH_EVIDENCE
        assert result.quantitative_count == 1
        assert result.rubric_manual_count == 3

    def test_minority_hard_evidence_is_mixed(self) -> None:
        """1/7 QUANTITATIVE = 14% → MIXED_EVIDENCE (some but not majority)."""
        prov = {
            "dim1": _prov(ScoreSourceType.QUANTITATIVE),
            "dim2": _prov(ScoreSourceType.SECTOR_PROXY),
            "dim3": _prov(ScoreSourceType.SECTOR_PROXY),
            "dim4": _prov(ScoreSourceType.DERIVED),
            "dim5": _prov(ScoreSourceType.DERIVED),
            "dim6": _prov(ScoreSourceType.DEFAULT),
            "dim7": _prov(ScoreSourceType.DEFAULT),
        }
        result = compute_coverage_summary(prov)
        assert result.evidence_quality == EvidenceQuality.MIXED_EVIDENCE

    def test_realistic_mvp_scenario(self) -> None:
        """MVP typical: 1 QUANTITATIVE (refinancing) + 2 SECTOR_PROXY + 4 defaults/derived."""
        prov = {
            "refinancing_stress": _prov(ScoreSourceType.QUANTITATIVE),
            "direct_commodity_exposure": _prov(ScoreSourceType.SECTOR_PROXY),
            "indirect_commodity_exposure": _prov(ScoreSourceType.SECTOR_PROXY),
            "export_fx_leverage": _prov(ScoreSourceType.DERIVED),
            "usd_debt_exposure": _prov(ScoreSourceType.DEFAULT),
            "usd_import_dependence": _prov(ScoreSourceType.DEFAULT),
            "usd_revenue_offset": _prov(ScoreSourceType.DERIVED),
        }
        result = compute_coverage_summary(prov)
        assert result.total_dimensions == 7
        assert result.quantitative_count == 1
        assert result.sector_proxy_count == 2
        assert result.derived_count == 2
        assert result.default_count == 2
        assert result.evidence_quality == EvidenceQuality.MIXED_EVIDENCE
        # 1/7 = 14.3%
        assert result.quantitative_pct == 14.3

    def test_exactly_50_percent_is_not_high(self) -> None:
        """50% exactly is <=50%, so MIXED not HIGH."""
        prov = {
            "dim1": _prov(ScoreSourceType.QUANTITATIVE),
            "dim2": _prov(ScoreSourceType.DEFAULT),
        }
        result = compute_coverage_summary(prov)
        assert result.evidence_quality == EvidenceQuality.MIXED_EVIDENCE

    def test_51_percent_is_high(self) -> None:
        """Just over 50% → HIGH_EVIDENCE."""
        prov = {
            "dim1": _prov(ScoreSourceType.QUANTITATIVE),
            "dim2": _prov(ScoreSourceType.RUBRIC_MANUAL),
            "dim3": _prov(ScoreSourceType.DEFAULT),
        }
        result = compute_coverage_summary(prov)
        # 2/3 = 66.7% → HIGH
        assert result.evidence_quality == EvidenceQuality.HIGH_EVIDENCE

    def test_rubric_manual_counts_as_hard_evidence(self) -> None:
        prov = {
            "dim1": _prov(ScoreSourceType.RUBRIC_MANUAL),
            "dim2": _prov(ScoreSourceType.RUBRIC_MANUAL),
            "dim3": _prov(ScoreSourceType.DEFAULT),
        }
        result = compute_coverage_summary(prov)
        assert result.evidence_quality == EvidenceQuality.HIGH_EVIDENCE

    def test_percentages_sum_to_100(self) -> None:
        prov = {
            "dim1": _prov(ScoreSourceType.QUANTITATIVE),
            "dim2": _prov(ScoreSourceType.SECTOR_PROXY),
            "dim3": _prov(ScoreSourceType.RUBRIC_MANUAL),
            "dim4": _prov(ScoreSourceType.DERIVED),
            "dim5": _prov(ScoreSourceType.DEFAULT),
        }
        result = compute_coverage_summary(prov)
        total_pct = (
            result.quantitative_pct
            + result.sector_proxy_pct
            + result.rubric_manual_pct
            + result.derived_pct
            + result.default_pct
        )
        assert total_pct == 100.0

    def test_counts_match_total(self) -> None:
        prov = {
            "dim1": _prov(ScoreSourceType.QUANTITATIVE),
            "dim2": _prov(ScoreSourceType.SECTOR_PROXY),
            "dim3": _prov(ScoreSourceType.DEFAULT),
        }
        result = compute_coverage_summary(prov)
        total_counts = (
            result.quantitative_count
            + result.sector_proxy_count
            + result.rubric_manual_count
            + result.derived_count
            + result.default_count
        )
        assert total_counts == result.total_dimensions
