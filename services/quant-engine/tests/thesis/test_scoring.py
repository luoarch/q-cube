"""Tests for Plan 2 thesis scoring engine."""

from __future__ import annotations

import pytest

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
    Plan2RankingSnapshot,
    ThesisBucket,
)


class TestComputeFinalCommodityAffinityScore:
    def test_known_values(self) -> None:
        # 0.50*80 + 0.30*60 + 0.20*40 = 40+18+8 = 66.0
        assert compute_final_commodity_affinity_score(80, 60, 40) == 66.0

    def test_all_zeros(self) -> None:
        assert compute_final_commodity_affinity_score(0, 0, 0) == 0.0

    def test_all_100s(self) -> None:
        assert compute_final_commodity_affinity_score(100, 100, 100) == 100.0

    def test_clamp_upper(self) -> None:
        # Inputs above 100 could push result above 100
        result = compute_final_commodity_affinity_score(200, 200, 200)
        assert result == 100.0


class TestComputeFinalDollarFragilityScore:
    def test_known_values(self) -> None:
        # 0.30*50 + 0.30*60 + 0.20*40 + 0.20*(100-70) = 15+18+8+6 = 47.0
        assert compute_final_dollar_fragility_score(50, 60, 40, 70) == 47.0

    def test_all_zeros_offset_zero(self) -> None:
        # 0.30*0 + 0.30*0 + 0.20*0 + 0.20*(100-0) = 0+0+0+20 = 20.0
        assert compute_final_dollar_fragility_score(0, 0, 0, 0) == 20.0

    def test_all_100s_offset_100(self) -> None:
        # 0.30*100 + 0.30*100 + 0.20*100 + 0.20*(100-100) = 30+30+20+0 = 80.0
        assert compute_final_dollar_fragility_score(100, 100, 100, 100) == 80.0

    def test_high_offset_reduces_fragility(self) -> None:
        low_offset = compute_final_dollar_fragility_score(50, 50, 50, 10)
        high_offset = compute_final_dollar_fragility_score(50, 50, 50, 90)
        assert high_offset < low_offset


class TestAssignThesisBucket:
    def test_a_direct(self) -> None:
        assert assign_thesis_bucket(70, 50, 60) == ThesisBucket.A_DIRECT

    def test_a_direct_boundary(self) -> None:
        assert assign_thesis_bucket(70, 50, 60) == ThesisBucket.A_DIRECT

    def test_not_a_direct_low_commodity(self) -> None:
        result = assign_thesis_bucket(69, 50, 60)
        assert result != ThesisBucket.A_DIRECT

    def test_not_a_direct_high_fragility(self) -> None:
        result = assign_thesis_bucket(70, 50, 61)
        assert result != ThesisBucket.A_DIRECT

    def test_b_indirect(self) -> None:
        assert assign_thesis_bucket(50, 60, 65) == ThesisBucket.B_INDIRECT

    def test_b_indirect_boundary(self) -> None:
        assert assign_thesis_bucket(50, 50, 65) == ThesisBucket.B_INDIRECT

    def test_not_b_indirect_low_indirect(self) -> None:
        result = assign_thesis_bucket(50, 49, 65)
        assert result != ThesisBucket.B_INDIRECT

    def test_d_fragile(self) -> None:
        assert assign_thesis_bucket(30, 30, 75) == ThesisBucket.D_FRAGILE

    def test_d_fragile_boundary(self) -> None:
        assert assign_thesis_bucket(30, 30, 75) == ThesisBucket.D_FRAGILE

    def test_c_neutral_default(self) -> None:
        assert assign_thesis_bucket(30, 30, 50) == ThesisBucket.C_NEUTRAL

    def test_priority_a_over_b(self) -> None:
        # direct=70, indirect=60, fragility=55 qualifies for both A and B
        assert assign_thesis_bucket(70, 60, 55) == ThesisBucket.A_DIRECT


class TestComputeThesisRankScore:
    def test_known_values(self) -> None:
        # 0.60*80 + 0.25*(100-40) + 0.15*60 = 48+15+9 = 72.0
        assert compute_thesis_rank_score(80, 40, 60) == 72.0

    def test_all_zeros(self) -> None:
        # 0.60*0 + 0.25*(100-0) + 0.15*0 = 0+25+0 = 25.0
        assert compute_thesis_rank_score(0, 0, 0) == 25.0

    def test_all_100s(self) -> None:
        # 0.60*100 + 0.25*(100-100) + 0.15*100 = 60+0+15 = 75.0
        assert compute_thesis_rank_score(100, 100, 100) == 75.0


def _make_snapshot(
    ticker: str,
    eligible: bool = True,
    bucket: ThesisBucket | None = None,
    thesis_rank_score: float | None = None,
) -> Plan2RankingSnapshot:
    return Plan2RankingSnapshot(
        issuer_id="test-id",
        ticker=ticker,
        company_name=f"Company {ticker}",
        sector=None,
        eligible=eligible,
        eligibility=BaseEligibility(eligible_for_plan2=eligible),
        bucket=bucket,
        thesis_rank_score=thesis_rank_score,
    )


class TestSortPlan2Rank:
    def test_bucket_precedence(self) -> None:
        snapshots = [
            _make_snapshot("D1", bucket=ThesisBucket.D_FRAGILE, thesis_rank_score=90),
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=50),
            _make_snapshot("C1", bucket=ThesisBucket.C_NEUTRAL, thesis_rank_score=95),
            _make_snapshot("B1", bucket=ThesisBucket.B_INDIRECT, thesis_rank_score=70),
        ]
        result = sort_plan2_rank(snapshots)
        assert [s.ticker for s in result] == ["A1", "B1", "C1", "D1"]

    def test_within_bucket_higher_score_first(self) -> None:
        snapshots = [
            _make_snapshot("A2", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=60),
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=80),
        ]
        result = sort_plan2_rank(snapshots)
        assert [s.ticker for s in result] == ["A1", "A2"]

    def test_stable_sort_same_score(self) -> None:
        snapshots = [
            _make_snapshot("BBBB", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=70),
            _make_snapshot("AAAA", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=70),
        ]
        result = sort_plan2_rank(snapshots)
        assert [s.ticker for s in result] == ["AAAA", "BBBB"]

    def test_ineligible_at_end(self) -> None:
        snapshots = [
            _make_snapshot("INELIG", eligible=False),
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=80),
        ]
        result = sort_plan2_rank(snapshots)
        assert result[0].ticker == "A1"
        assert result[1].ticker == "INELIG"

    def test_thesis_rank_assigned_1_based(self) -> None:
        snapshots = [
            _make_snapshot("B1", bucket=ThesisBucket.B_INDIRECT, thesis_rank_score=60),
            _make_snapshot("A1", bucket=ThesisBucket.A_DIRECT, thesis_rank_score=80),
            _make_snapshot("INELIG", eligible=False),
        ]
        result = sort_plan2_rank(snapshots)
        assert result[0].thesis_rank == 1
        assert result[1].thesis_rank == 2
        assert result[2].thesis_rank is None


class TestGenerateExplanation:
    def test_a_direct_high_commodity_low_fragility(self) -> None:
        exp = generate_explanation(
            ticker="VALE3",
            bucket=ThesisBucket.A_DIRECT,
            thesis_rank_score=85.0,
            commodity_affinity=90.0,
            fragility=30.0,
            base_core=75.0,
            direct_commodity=90.0,
            indirect_commodity=40.0,
            export_fx=70.0,
            refinancing_stress=20.0,
            usd_debt=15.0,
            usd_import=10.0,
            usd_revenue_offset=80.0,
        )
        assert exp.ticker == "VALE3"
        assert exp.bucket == ThesisBucket.A_DIRECT
        assert len(exp.positives) > 0
        assert any("commodities" in p.lower() for p in exp.positives)
        assert "diretamente alavancada" in exp.summary

    def test_d_fragile_high_fragility(self) -> None:
        exp = generate_explanation(
            ticker="FRAGILE3",
            bucket=ThesisBucket.D_FRAGILE,
            thesis_rank_score=25.0,
            commodity_affinity=20.0,
            fragility=85.0,
            base_core=30.0,
            direct_commodity=10.0,
            indirect_commodity=15.0,
            export_fx=5.0,
            refinancing_stress=80.0,
            usd_debt=75.0,
            usd_import=80.0,
            usd_revenue_offset=10.0,
        )
        assert exp.ticker == "FRAGILE3"
        assert exp.bucket == ThesisBucket.D_FRAGILE
        assert len(exp.negatives) > 0
        assert any("fragilidade" in n.lower() for n in exp.negatives)
        assert "fragilidade relevante" in exp.summary

    def test_explanation_fields_are_correct_types(self) -> None:
        exp = generate_explanation(
            ticker="TEST3",
            bucket=ThesisBucket.C_NEUTRAL,
            thesis_rank_score=50.0,
            commodity_affinity=50.0,
            fragility=50.0,
            base_core=50.0,
            direct_commodity=50.0,
            indirect_commodity=50.0,
            export_fx=50.0,
            refinancing_stress=50.0,
            usd_debt=50.0,
            usd_import=50.0,
            usd_revenue_offset=50.0,
        )
        assert isinstance(exp.positives, list)
        assert isinstance(exp.negatives, list)
        assert isinstance(exp.summary, str)
        assert len(exp.summary) > 0
