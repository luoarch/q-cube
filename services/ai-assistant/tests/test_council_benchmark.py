"""Benchmark test suite for council agent quality evaluation.

Tests invariants that must hold for ALL council outputs:
- Hard reject -> verdict must be 'avoid'
- Verdict-reason alignment (buy has reasonsFor, avoid has reasonsAgainst)
- No contradictions between reasonsFor and reasonsAgainst
- Regulatory compliance (no banned phrases)
- Metrics grounded in packet data
- Disclaimer always present
- Framework adherence (agents cite their school's core metrics)
- Confidence calibration (sensible confidence per scenario)

Benchmark cases (10 archetypes):
- Strong company: easy consensus, all agents buy/watch
- Value trap: high yield but deteriorating fundamentals
- Bank: financial classification, safety block skipped
- Insufficient data: minimal data, agents acknowledge uncertainty
- Artificial dividend: payout > earnings, unsustainable
- Turnaround: recovering from losses, mixed signals
- Utility: regulated, stable — Barsi archetype
- Cyclical: volatile margins, lower confidence expected
- Deep value: cheap but ugly — Greenblatt/Graham like it
- Quality premium: expensive but excellent — Buffett likes, Greenblatt skeptical
"""

from __future__ import annotations

import pytest

from q3_ai_assistant.council.agents.barsi import _negative_fcf_3_years, _negative_net_income_recurring
from q3_ai_assistant.council.agents.buffett import _margin_collapse, _roe_consistently_low
from q3_ai_assistant.council.agents.graham import _high_leverage_and_expensive, _negative_equity
from q3_ai_assistant.council.agents.greenblatt import _negative_ebit, _roic_consistently_low
from q3_ai_assistant.council.packet import AssetAnalysisPacket, PeriodValue
from q3_ai_assistant.evaluation.benchmark import (
    ALL_BENCHMARK_CASES,
    ARTIFICIAL_DIVIDEND,
    BANK,
    BENCHMARK_CASE_IDS,
    CYCLICAL,
    DEEP_VALUE,
    INSUFFICIENT_DATA,
    QUALITY_PREMIUM,
    STRONG_COMPANY,
    TURNAROUND,
    UTILITY,
    VALUE_TRAP,
    BenchmarkCase,
    RegressionBaseline,
)
from q3_ai_assistant.evaluation.quality import (
    AGENT_CORE_METRICS,
    BANNED_PHRASES,
    VALID_METRICS,
    ConfidenceExpectation,
    evaluate_council_result,
    evaluate_cross_agent_consistency,
    evaluate_opinion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pv(val: float | None, d: str = "2024-12-31") -> PeriodValue:
    return PeriodValue(reference_date=d, value=val)


def _make_packet(**overrides: object) -> AssetAnalysisPacket:
    defaults: dict[str, object] = dict(
        issuer_id="bench-id",
        ticker="BENCH3",
        sector="Bens Industriais",
        subsector="Maquinas e Equipamentos",
        classification="non_financial",
        fundamentals={},
        trends={},
        refiner_scores=None,
        flags=None,
        market_cap=None,
        avg_daily_volume=None,
    )
    defaults.update(overrides)
    return AssetAnalysisPacket(**defaults)  # type: ignore[arg-type]


def _complete_opinion(agent_id: str = "greenblatt", **overrides: object) -> dict:
    base: dict[str, object] = {
        "agentId": agent_id,
        "profileVersion": 1,
        "promptVersion": 1,
        "verdict": "buy",
        "confidence": 75,
        "dataReliability": "high",
        "thesis": "Strong ROIC and earnings yield indicate a quality company at a fair price.",
        "reasonsFor": ["High ROIC", "Attractive earnings yield"],
        "reasonsAgainst": ["Moderate debt levels"],
        "keyMetricsUsed": ["roic", "earnings_yield"],
        "hardRejectsTriggered": [],
        "unknowns": ["Future capex plans"],
        "whatWouldChangeMyMind": ["ROIC drops below 10%"],
        "investorFit": ["Quantitative value investors"],
    }
    base.update(overrides)
    return base


def _council_result(opinions: list[dict], **overrides: object) -> dict:
    base: dict[str, object] = {
        "opinions": opinions,
        "disclaimer": "Este conteudo e meramente educacional e nao constitui recomendacao de investimento.",
        "scoreboard": {"entries": [], "consensus": None, "consensus_strength": None},
        "conflict_matrix": [],
        "moderator_synthesis": {
            "convergences": [],
            "divergences": [],
            "biggest_risk": "Market risk",
            "entry_conditions": [],
            "exit_conditions": [],
            "overall_assessment": "Analysis complete.",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Hard Reject Functions (for parametrized testing)
# ---------------------------------------------------------------------------

_REJECT_FUNCTIONS = {
    "negative_fcf_3y": _negative_fcf_3_years,
    "negative_ni_recurring": _negative_net_income_recurring,
    "high_leverage_expensive": _high_leverage_and_expensive,
    "negative_equity": _negative_equity,
    "negative_ebit": _negative_ebit,
    "roic_consistently_low": _roic_consistently_low,
    "roe_consistently_low": _roe_consistently_low,
    "margin_collapse": _margin_collapse,
}


# ===========================================================================
# SECTION 1: Archetype Hard Reject Tests (parametrized)
# ===========================================================================

class TestArchetypeHardRejects:
    """Verify expected hard reject outcomes for each benchmark archetype."""

    @pytest.mark.parametrize("case", ALL_BENCHMARK_CASES, ids=BENCHMARK_CASE_IDS)
    def test_expected_hard_rejects_fire(self, case: BenchmarkCase):
        """Hard rejects listed in expected_hard_rejects should trigger."""
        for agent_id, expected_codes in case.expected_hard_rejects.items():
            for code in expected_codes:
                fn = _REJECT_FUNCTIONS.get(code)
                assert fn is not None, f"Unknown reject code: {code}"
                result = fn(case.packet)
                assert result is True, (
                    f"[{case.name}] {agent_id} reject '{code}' should fire but didn't"
                )

    @pytest.mark.parametrize("case", ALL_BENCHMARK_CASES, ids=BENCHMARK_CASE_IDS)
    def test_expected_no_hard_rejects(self, case: BenchmarkCase):
        """Hard rejects listed in expected_no_hard_rejects should NOT trigger."""
        for agent_id, not_expected_codes in case.expected_no_hard_rejects.items():
            for code in not_expected_codes:
                fn = _REJECT_FUNCTIONS.get(code)
                assert fn is not None, f"Unknown reject code: {code}"
                result = fn(case.packet)
                assert result is False, (
                    f"[{case.name}] {agent_id} reject '{code}' should NOT fire but did"
                )


# ===========================================================================
# SECTION 2: Individual Archetype Deep Tests
# ===========================================================================

class TestStrongCompany:
    """Strong company — all agents should agree, no rejects."""

    def test_no_rejects_for_any_agent(self):
        pkt = STRONG_COMPANY.packet
        for code, fn in _REJECT_FUNCTIONS.items():
            assert fn(pkt) is False, f"Reject '{code}' should not fire for strong company"

    def test_consensus_council_quality(self):
        opinions = [
            _complete_opinion("greenblatt", verdict="buy", confidence=85,
                              keyMetricsUsed=["roic", "earnings_yield", "ebit"]),
            _complete_opinion("buffett", verdict="buy", confidence=80,
                              keyMetricsUsed=["roe", "gross_margin", "cash_from_operations"]),
            _complete_opinion("graham", verdict="watch", confidence=70,
                              thesis="Solid fundamentals but valuation at fair value, not a deep discount.",
                              keyMetricsUsed=["earnings_yield", "debt_to_ebitda", "net_margin"]),
            _complete_opinion("barsi", verdict="buy", confidence=75,
                              keyMetricsUsed=["net_income", "cash_from_operations", "earnings_yield"]),
        ]
        result = _council_result(opinions)
        scores = evaluate_council_result(result)
        assert scores["overall"] >= 0.8
        assert len(scores["issues"]) == 0

    def test_cross_agent_consistency(self):
        opinions = [
            _complete_opinion("greenblatt", verdict="buy", confidence=85),
            _complete_opinion("buffett", verdict="buy", confidence=80),
            _complete_opinion("graham", verdict="watch", confidence=70),
            _complete_opinion("barsi", verdict="buy", confidence=75),
        ]
        consistency = evaluate_cross_agent_consistency(opinions)
        assert consistency["verdict_agreement"] >= 0.5
        assert len(consistency["issues"]) == 0


class TestValueTrap:
    """Value trap — Buffett should hard-reject, others cautious."""

    def test_buffett_hard_reject(self):
        assert _margin_collapse(VALUE_TRAP.packet) is True

    def test_graham_no_hard_reject(self):
        # D/E = 4.5 (< 5.0) so Graham doesn't reject
        assert _high_leverage_and_expensive(VALUE_TRAP.packet) is False

    def test_value_trap_opinion_quality(self):
        opinion = _complete_opinion(
            agent_id="buffett",
            verdict="avoid",
            confidence=80,
            thesis="Despite attractive valuation, margin collapse and rising leverage signal fundamental deterioration.",
            reasonsFor=["High earnings yield"],
            reasonsAgainst=["Margin collapse (30% to 18%)", "Rising debt/EBITDA", "Declining ROIC"],
            keyMetricsUsed=["earnings_yield", "gross_margin", "debt_to_ebitda", "roic"],
            hardRejectsTriggered=["margin_collapse"],
        )
        score = evaluate_opinion(
            opinion,
            confidence_expectation=VALUE_TRAP.expected_confidence.get("buffett"),
        )
        assert score.completeness == 1.0
        assert score.consistency == 1.0
        assert score.framework_adherence > 0.0
        assert score.overall >= 0.8


class TestBank:
    """Bank — leverage rules skipped."""

    def test_graham_skips_leverage(self):
        assert _high_leverage_and_expensive(BANK.packet) is False

    def test_buffett_roe_ok(self):
        assert _roe_consistently_low(BANK.packet) is False


class TestInsufficientData:
    """Minimal data — all should return insufficient_data or very low confidence."""

    def test_no_hard_rejects_fire(self):
        for code, fn in _REJECT_FUNCTIONS.items():
            assert fn(INSUFFICIENT_DATA.packet) is False, (
                f"Reject '{code}' should not fire on empty data"
            )

    def test_opinion_quality_for_insufficient(self):
        opinion = _complete_opinion(
            verdict="insufficient_data",
            confidence=10,
            thesis="Insufficient financial data to form a meaningful opinion. No periods available.",
            reasonsFor=[],
            reasonsAgainst=[],
            keyMetricsUsed=[],
            unknowns=["All fundamental metrics", "Revenue trend", "Profitability"],
        )
        score = evaluate_opinion(
            opinion,
            confidence_expectation=INSUFFICIENT_DATA.expected_confidence.get("greenblatt"),
        )
        assert score.completeness == 1.0
        assert score.confidence_calibration == 1.0


class TestArtificialDividend:
    """Payout exceeds earnings — Barsi should be cautious."""

    def test_no_hard_rejects_but_warning(self):
        # FCF is positive in all 3 years: (90-40)=50, (70-50)=20, (50-60)=-10
        # Not all 3 negative, so no hard reject for Barsi
        pkt = ARTIFICIAL_DIVIDEND.packet
        assert _negative_fcf_3_years(pkt) is False
        assert _negative_net_income_recurring(pkt) is False

    def test_barsi_opinion_should_flag_sustainability(self):
        """A well-crafted Barsi opinion should mention dividend sustainability concerns."""
        opinion = _complete_opinion(
            agent_id="barsi",
            verdict="watch",
            confidence=45,
            thesis="Dividends appear funded partially by debt. CFO declining and financing outflows exceed net income. Sustainability questionable.",
            reasonsFor=["Decent earnings yield"],
            reasonsAgainst=["Dividends exceed earnings", "Rising debt", "Declining CFO"],
            keyMetricsUsed=["earnings_yield", "net_income", "cash_from_operations", "cash_from_financing", "debt_to_ebitda"],
        )
        score = evaluate_opinion(opinion)
        assert score.framework_adherence > 0.5
        assert score.consistency == 1.0


class TestTurnaround:
    """Recent recovery — Barsi should hard-reject (2 negative NI years)."""

    def test_barsi_rejects_recurring_losses(self):
        assert _negative_net_income_recurring(TURNAROUND.packet) is True

    def test_greenblatt_no_reject(self):
        # Current EBIT = 80 > 0
        assert _negative_ebit(TURNAROUND.packet) is False

    def test_roic_not_consistently_low(self):
        # ROIC: -0.03, 0.02, 0.07 — _roic_consistently_low uses all(),
        # so 0.07 >= 0.05 means not all are low -> False
        assert _roic_consistently_low(TURNAROUND.packet) is False


class TestUtility:
    """Regulated utility — stable, no rejects, Barsi should favor."""

    def test_no_hard_rejects(self):
        for code, fn in _REJECT_FUNCTIONS.items():
            assert fn(UTILITY.packet) is False, f"Reject '{code}' should not fire for utility"

    def test_barsi_opinion_quality(self):
        opinion = _complete_opinion(
            agent_id="barsi",
            verdict="buy",
            confidence=80,
            thesis="Utility with stable margins, predictable cash flows, and consistent dividend coverage. Classic perennial business.",
            reasonsFor=["Stable margins", "Consistent FCF", "Regulated revenue"],
            reasonsAgainst=["Moderate growth ceiling"],
            keyMetricsUsed=["earnings_yield", "net_income", "cash_from_operations", "net_margin"],
        )
        score = evaluate_opinion(opinion)
        assert score.framework_adherence > 0.5
        assert score.overall >= 0.85


class TestCyclical:
    """Cyclical — volatile margins, agents should have moderate confidence."""

    def test_no_hard_rejects(self):
        pkt = CYCLICAL.packet
        assert _margin_collapse(pkt) is False  # not 30%+ decline — recovered
        assert _negative_ebit(pkt) is False

    def test_confidence_calibration(self):
        opinion = _complete_opinion(
            agent_id="buffett",
            verdict="watch",
            confidence=55,
            thesis="Strong current fundamentals but volatile margin history raises concerns about sustainability.",
            reasonsFor=["High current ROIC", "Low leverage"],
            reasonsAgainst=["Margin volatility", "Cyclical exposure"],
            keyMetricsUsed=["roe", "gross_margin", "roic", "cash_from_operations"],
        )
        score = evaluate_opinion(
            opinion,
            confidence_expectation=CYCLICAL.expected_confidence.get("buffett"),
        )
        assert score.confidence_calibration == 1.0

    def test_overconfident_penalized(self):
        opinion = _complete_opinion(
            agent_id="buffett",
            verdict="buy",
            confidence=95,
            thesis="Strong current fundamentals justify high confidence buy recommendation.",
            keyMetricsUsed=["roe", "gross_margin"],
        )
        score = evaluate_opinion(
            opinion,
            confidence_expectation=CYCLICAL.expected_confidence.get("buffett"),
        )
        assert score.confidence_calibration < 1.0


class TestDeepValue:
    """Cheap but low margins — Greenblatt should like high EY + ROIC."""

    def test_no_greenblatt_rejects(self):
        assert _negative_ebit(DEEP_VALUE.packet) is False
        assert _roic_consistently_low(DEEP_VALUE.packet) is False

    def test_greenblatt_framework_adherence(self):
        opinion = _complete_opinion(
            agent_id="greenblatt",
            verdict="buy",
            confidence=80,
            thesis="High earnings yield of 20% combined with improving ROIC of 15% represents a classic Magic Formula candidate.",
            reasonsFor=["High EY at 20%", "ROIC of 15% and improving", "Growing EBIT"],
            reasonsAgainst=["Low gross margin"],
            keyMetricsUsed=["earnings_yield", "roic", "ebit", "ebit_margin"],
        )
        score = evaluate_opinion(
            opinion,
            confidence_expectation=DEEP_VALUE.expected_confidence.get("greenblatt"),
        )
        assert score.framework_adherence == 1.0
        assert score.confidence_calibration == 1.0


class TestQualityPremium:
    """Expensive but excellent quality — expected divergence between agents."""

    def test_no_hard_rejects(self):
        for code, fn in _REJECT_FUNCTIONS.items():
            assert fn(QUALITY_PREMIUM.packet) is False

    def test_expected_divergence(self):
        """Buffett buy + Greenblatt watch/avoid = legitimate divergence."""
        opinions = [
            _complete_opinion("buffett", verdict="buy", confidence=80,
                              thesis="Exceptional quality business with wide moat. High ROE, expanding margins, and strong FCF justify premium valuation.",
                              keyMetricsUsed=["roe", "gross_margin", "cash_from_operations", "net_margin"]),
            _complete_opinion("greenblatt", verdict="watch", confidence=55,
                              thesis="Quality is undeniable but EY of 4% is too low for Magic Formula criteria. Current price offers insufficient return.",
                              reasonsFor=["High ROIC of 30%"],
                              reasonsAgainst=["EY only 4%", "Overvalued by Magic Formula standards"],
                              keyMetricsUsed=["earnings_yield", "roic", "ebit"]),
            _complete_opinion("graham", verdict="avoid", confidence=60,
                              thesis="No margin of safety at current valuations. Despite quality, price is too high for conservative investors.",
                              reasonsFor=["Low debt"],
                              reasonsAgainst=["EY only 4%", "Premium to intrinsic value"],
                              keyMetricsUsed=["earnings_yield", "debt_to_ebitda", "gross_margin"]),
        ]
        result = _council_result(opinions)
        scores = evaluate_council_result(result)
        assert scores["overall"] >= 0.7

        consistency = evaluate_cross_agent_consistency(opinions)
        assert len(consistency["unique_verdicts"]) >= 2  # divergence expected


# ===========================================================================
# SECTION 3: Universal Invariant Tests
# ===========================================================================

class TestHardRejectImpliesAvoid:
    """When a hard reject triggers, the opinion verdict MUST be 'avoid'."""

    @pytest.mark.parametrize("agent_id,reject_name", [
        ("barsi", "negative_fcf_3y"),
        ("barsi", "negative_ni_recurring"),
        ("graham", "high_leverage_expensive"),
        ("graham", "negative_equity"),
        ("greenblatt", "negative_ebit"),
        ("greenblatt", "roic_consistently_low"),
        ("buffett", "roe_consistently_low"),
        ("buffett", "margin_collapse"),
    ])
    def test_hard_reject_forces_avoid(self, agent_id: str, reject_name: str):
        # Correct: hard reject + avoid
        opinion = _complete_opinion(
            agent_id=agent_id,
            verdict="avoid",
            hardRejectsTriggered=[reject_name],
            reasonsAgainst=[f"Hard reject: {reject_name}"],
            reasonsFor=[],
        )
        score = evaluate_opinion(opinion)
        assert score.consistency == 1.0
        assert score.contradiction_free == 1.0

        # Wrong: hard reject + buy — should be flagged
        bad_opinion = _complete_opinion(
            agent_id=agent_id,
            verdict="buy",
            hardRejectsTriggered=[reject_name],
        )
        bad_score = evaluate_opinion(bad_opinion)
        assert bad_score.contradiction_free == 0.0


class TestRegulatoryInvariants:
    """All council outputs must pass regulatory compliance."""

    @pytest.mark.parametrize("phrase", BANNED_PHRASES)
    def test_banned_phrase_detected(self, phrase: str):
        opinion = _complete_opinion(thesis=f"This company is great. {phrase}!")
        score = evaluate_opinion(opinion)
        assert score.regulatory_compliance == 0.0, f"Missed banned phrase: {phrase}"

    def test_disclaimer_required(self):
        result = _council_result([_complete_opinion()], disclaimer="")
        scores = evaluate_council_result(result)
        assert any("Missing disclaimer" in i for i in scores["issues"])

    def test_disclaimer_present_no_penalty(self):
        result = _council_result([_complete_opinion()])
        scores = evaluate_council_result(result)
        assert not any("Missing disclaimer" in i for i in scores["issues"])


class TestMetricGroundedness:
    """Agents must only reference metrics from their packet."""

    def test_all_valid_metrics_known(self):
        for metric in ["roic", "earnings_yield", "roe", "debt_to_ebitda", "gross_margin"]:
            assert metric in VALID_METRICS

    def test_fabricated_metrics_penalized(self):
        opinion = _complete_opinion(
            keyMetricsUsed=["made_up_ratio", "fake_metric", "roic"],
        )
        score = evaluate_opinion(opinion)
        assert score.groundedness < 1.0

    def test_packet_scoped_validation(self):
        packet_metrics = {"roic", "earnings_yield"}
        opinion = _complete_opinion(
            keyMetricsUsed=["roic", "roe"],  # roe not in packet
        )
        score = evaluate_opinion(opinion, packet_metrics=packet_metrics)
        assert score.groundedness == 0.5  # 1 of 2


class TestVerdictReasonAlignment:
    """Verdict should be consistent with provided reasons."""

    def test_buy_needs_reasons_for(self):
        opinion = _complete_opinion(verdict="buy", reasonsFor=[])
        score = evaluate_opinion(opinion)
        assert score.consistency < 1.0

    def test_avoid_needs_reasons_against(self):
        opinion = _complete_opinion(verdict="avoid", reasonsAgainst=[])
        score = evaluate_opinion(opinion)
        assert score.consistency < 1.0

    def test_contradicting_reasons_detected(self):
        opinion = _complete_opinion(
            reasonsFor=["High ROIC", "Strong margins"],
            reasonsAgainst=["High ROIC"],
        )
        score = evaluate_opinion(opinion)
        assert score.contradiction_free == 0.0


# ===========================================================================
# SECTION 4: Framework Adherence Tests
# ===========================================================================

class TestFrameworkAdherence:
    """Each agent should cite metrics from its investment school."""

    @pytest.mark.parametrize("agent_id", ["barsi", "graham", "greenblatt", "buffett"])
    def test_core_metrics_defined(self, agent_id: str):
        assert agent_id in AGENT_CORE_METRICS
        assert len(AGENT_CORE_METRICS[agent_id]) >= 4

    def test_greenblatt_uses_ey_roic(self):
        opinion = _complete_opinion(
            agent_id="greenblatt",
            keyMetricsUsed=["earnings_yield", "roic", "ebit"],
        )
        score = evaluate_opinion(opinion)
        assert score.framework_adherence == 1.0

    def test_greenblatt_missing_core_metrics_penalized(self):
        opinion = _complete_opinion(
            agent_id="greenblatt",
            keyMetricsUsed=["roe", "gross_margin"],  # not Greenblatt's core
        )
        score = evaluate_opinion(opinion)
        assert score.framework_adherence < 1.0

    def test_buffett_uses_roe_margins(self):
        opinion = _complete_opinion(
            agent_id="buffett",
            keyMetricsUsed=["roe", "gross_margin", "cash_from_operations"],
        )
        score = evaluate_opinion(opinion)
        assert score.framework_adherence == 1.0

    def test_barsi_uses_cash_flow_metrics(self):
        opinion = _complete_opinion(
            agent_id="barsi",
            keyMetricsUsed=["net_income", "cash_from_operations", "earnings_yield"],
        )
        score = evaluate_opinion(opinion)
        assert score.framework_adherence == 1.0

    def test_graham_uses_debt_and_value(self):
        opinion = _complete_opinion(
            agent_id="graham",
            keyMetricsUsed=["earnings_yield", "debt_to_ebitda", "gross_margin"],
        )
        score = evaluate_opinion(opinion)
        assert score.framework_adherence == 1.0

    def test_no_metrics_at_all_penalized(self):
        opinion = _complete_opinion(
            agent_id="greenblatt",
            keyMetricsUsed=[],
        )
        score = evaluate_opinion(opinion)
        assert score.framework_adherence == 0.0


# ===========================================================================
# SECTION 5: Confidence Calibration Tests
# ===========================================================================

class TestConfidenceCalibration:
    """Confidence levels should be sensible per scenario."""

    def test_insufficient_data_low_confidence(self):
        opinion = _complete_opinion(
            verdict="insufficient_data",
            confidence=85,
        )
        score = evaluate_opinion(opinion)
        assert score.confidence_calibration < 1.0

    def test_insufficient_data_expected_range(self):
        opinion = _complete_opinion(
            verdict="insufficient_data",
            confidence=15,
        )
        expectation = ConfidenceExpectation(0, 30, "no data")
        score = evaluate_opinion(opinion, confidence_expectation=expectation)
        assert score.confidence_calibration == 1.0

    def test_overconfident_on_volatile_penalized(self):
        opinion = _complete_opinion(confidence=95)
        expectation = ConfidenceExpectation(30, 75, "volatile cyclical")
        score = evaluate_opinion(opinion, confidence_expectation=expectation)
        assert score.confidence_calibration < 1.0

    def test_underconfident_on_strong_penalized(self):
        opinion = _complete_opinion(confidence=20)
        expectation = ConfidenceExpectation(60, 95, "strong fundamentals")
        score = evaluate_opinion(opinion, confidence_expectation=expectation)
        assert score.confidence_calibration < 1.0


# ===========================================================================
# SECTION 6: Cross-Agent Consistency Tests
# ===========================================================================

class TestCrossAgentConsistency:
    """Multiple agents analyzing the same asset should be factually consistent."""

    def test_unanimous_buy_high_agreement(self):
        opinions = [
            _complete_opinion("greenblatt", verdict="buy"),
            _complete_opinion("buffett", verdict="buy"),
            _complete_opinion("graham", verdict="buy"),
            _complete_opinion("barsi", verdict="buy"),
        ]
        result = evaluate_cross_agent_consistency(opinions)
        assert result["verdict_agreement"] == 1.0

    def test_split_verdict_lower_agreement(self):
        opinions = [
            _complete_opinion("greenblatt", verdict="buy"),
            _complete_opinion("buffett", verdict="buy"),
            _complete_opinion("graham", verdict="avoid"),
            _complete_opinion("barsi", verdict="watch"),
        ]
        result = evaluate_cross_agent_consistency(opinions)
        assert result["verdict_agreement"] < 1.0
        assert len(result["unique_verdicts"]) == 3

    def test_hard_reject_plus_buy_without_reasons_flagged(self):
        opinions = [
            _complete_opinion("buffett", verdict="avoid",
                              hardRejectsTriggered=["margin_collapse"]),
            _complete_opinion("greenblatt", verdict="buy",
                              reasonsAgainst=[]),  # no counterpoints
        ]
        result = evaluate_cross_agent_consistency(opinions)
        assert len(result["issues"]) > 0


# ===========================================================================
# SECTION 7: Full Council Result Quality
# ===========================================================================

class TestFullCouncilQuality:
    """End-to-end quality checks on full council results."""

    def test_roundtable_4_agents(self):
        opinions = [
            _complete_opinion("greenblatt",
                              keyMetricsUsed=["roic", "earnings_yield", "ebit"]),
            _complete_opinion("buffett",
                              keyMetricsUsed=["roe", "gross_margin", "cash_from_operations"]),
            _complete_opinion("graham", verdict="watch",
                              thesis="Fair valuation but not a deep discount. Margin of safety is thin.",
                              keyMetricsUsed=["earnings_yield", "debt_to_ebitda", "net_margin"]),
            _complete_opinion("barsi",
                              keyMetricsUsed=["net_income", "cash_from_operations", "earnings_yield"]),
        ]
        result = _council_result(opinions)
        scores = evaluate_council_result(result)
        assert scores["overall"] >= 0.8
        assert len(scores["per_agent"]) == 4
        # Each agent should have framework_adherence scored
        for agent_id, agent_scores in scores["per_agent"].items():
            assert "framework_adherence" in agent_scores

    def test_debate_with_conflict(self):
        opinions = [
            _complete_opinion("greenblatt", verdict="buy", confidence=80,
                              keyMetricsUsed=["roic", "earnings_yield"]),
            _complete_opinion("graham", verdict="avoid", confidence=65,
                              thesis="Too expensive relative to book value. Insufficient margin of safety for conservative investors.",
                              reasonsFor=["Decent operating margins"],
                              reasonsAgainst=["P/VPA too high", "Weak current ratio"],
                              keyMetricsUsed=["earnings_yield", "debt_to_ebitda"]),
        ]
        result = _council_result(opinions)
        scores = evaluate_council_result(result)
        assert scores["overall"] >= 0.7
        assert "greenblatt" in scores["per_agent"]
        assert "graham" in scores["per_agent"]


# ===========================================================================
# SECTION 8: Regression Detection
# ===========================================================================

class TestRegressionBaseline:
    """Baseline tracking and drift detection."""

    def test_record_and_check_no_regression(self):
        baseline = RegressionBaseline(threshold=0.10)
        score = evaluate_opinion(_complete_opinion())
        baseline.record("test_case", "greenblatt", score)

        # Same score — no regression
        drift = baseline.check_drift("test_case", "greenblatt", score)
        assert drift["has_regression"] is False

    def test_detect_regression(self):
        baseline = RegressionBaseline(threshold=0.10)
        good_score = evaluate_opinion(_complete_opinion())
        baseline.record("test_case", "greenblatt", good_score)

        # Degraded opinion
        bad_opinion = _complete_opinion(
            thesis="Short.",  # too short
            keyMetricsUsed=[],  # no metrics
            reasonsFor=[],  # buy without reasons
        )
        bad_score = evaluate_opinion(bad_opinion)
        drift = baseline.check_drift("test_case", "greenblatt", bad_score)
        assert drift["has_regression"] is True
        assert drift["drift"] > 0.10

    def test_no_baseline_no_regression(self):
        baseline = RegressionBaseline()
        score = evaluate_opinion(_complete_opinion())
        drift = baseline.check_drift("unknown", "greenblatt", score)
        assert drift["has_regression"] is False
        assert drift["reason"] == "no baseline"
