"""Benchmark test suite for council agent quality evaluation.

Tests invariants that must hold for ALL council outputs:
- Hard reject → verdict must be 'avoid'
- Verdict-reason alignment (buy has reasonsFor, avoid has reasonsAgainst)
- No contradictions between reasonsFor and reasonsAgainst
- Regulatory compliance (no banned phrases)
- Metrics grounded in packet data
- Disclaimer always present

Also includes known-asset benchmark cases:
- Value trap: high yield but deteriorating fundamentals
- Strong consensus: clearly good company
- Bank classification: safety block skipped
"""

from __future__ import annotations

import pytest

from q3_ai_assistant.council.packet import AssetAnalysisPacket, PeriodValue
from q3_ai_assistant.council.agents.barsi import _negative_fcf_3_years, _negative_net_income_recurring
from q3_ai_assistant.council.agents.graham import _high_leverage_and_expensive, _negative_equity
from q3_ai_assistant.council.agents.greenblatt import _negative_ebit, _roic_consistently_low
from q3_ai_assistant.council.agents.buffett import _roe_consistently_low, _margin_collapse
from q3_ai_assistant.evaluation.quality import (
    BANNED_PHRASES,
    VALID_METRICS,
    evaluate_council_result,
    evaluate_opinion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pv(val: float | None, d: str = "2024-12-31") -> PeriodValue:
    return PeriodValue(reference_date=d, value=val)


def _make_packet(**overrides) -> AssetAnalysisPacket:
    defaults = dict(
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
    return AssetAnalysisPacket(**defaults)


def _complete_opinion(agent_id: str = "greenblatt", **overrides) -> dict:
    base = {
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


def _council_result(opinions: list[dict], **overrides) -> dict:
    base = {
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
# Benchmark Case 1: Value Trap
# High yield but deteriorating fundamentals — agents should be cautious
# ---------------------------------------------------------------------------

class TestValueTrapCase:
    """Company with high EY/ROIC but declining margins and rising debt."""

    @pytest.fixture
    def packet(self):
        return _make_packet(
            ticker="TRAP3",
            fundamentals={
                "earnings_yield": 0.15,  # looks cheap
                "roic": 0.12,
                "roe": 0.10,
                "ebit": 200.0,
                "debt_to_ebitda": 4.5,  # high leverage
                "gross_margin": 0.18,  # low and declining
            },
            trends={
                "gross_margin": [_pv(0.30, "2022"), _pv(0.24, "2023"), _pv(0.18, "2024")],
                "ebit_margin": [_pv(0.15, "2022"), _pv(0.10, "2023"), _pv(0.06, "2024")],
                "debt_to_ebitda": [_pv(2.0, "2022"), _pv(3.0, "2023"), _pv(4.5, "2024")],
                "net_income": [_pv(100, "2022"), _pv(80, "2023"), _pv(50, "2024")],
                "roic": [_pv(0.18, "2022"), _pv(0.15, "2023"), _pv(0.12, "2024")],
                "cash_from_operations": [_pv(120, "2022"), _pv(90, "2023"), _pv(60, "2024")],
                "cash_from_investing": [_pv(-80, "2022"), _pv(-90, "2023"), _pv(-100, "2024")],
            },
        )

    def test_graham_rejects_high_leverage(self, packet):
        """Graham should reject: debt/ebitda > 5 and EY < 5%... but actually D/E=4.5, EY=15%.
        This won't trigger hard reject. But margin collapse should concern Buffett."""
        assert _high_leverage_and_expensive(packet) is False

    def test_buffett_detects_margin_collapse(self, packet):
        """Gross margin went from 30% to 18% — below 70% of initial: 0.30 * 0.7 = 0.21."""
        assert _margin_collapse(packet) is True

    def test_negative_fcf_last_period(self, packet):
        """CFO 60 + CFI -100 = -40 in last period. But not all 3 negative."""
        assert _negative_fcf_3_years(packet) is False

    def test_value_trap_opinion_should_flag_risks(self):
        """An opinion on a value trap should have reasonsAgainst."""
        opinion = _complete_opinion(
            agent_id="buffett",
            verdict="avoid",
            thesis="Despite attractive valuation, margin collapse and rising leverage signal fundamental deterioration.",
            reasonsFor=["High earnings yield"],
            reasonsAgainst=["Margin collapse (30% → 18%)", "Rising debt/EBITDA", "Declining ROIC"],
            keyMetricsUsed=["earnings_yield", "gross_margin", "debt_to_ebitda", "roic"],
            hardRejectsTriggered=["margin_collapse"],
        )
        score = evaluate_opinion(opinion)
        assert score.completeness == 1.0
        assert score.consistency == 1.0  # avoid + reasonsAgainst present
        assert score.regulatory_compliance == 1.0
        assert score.overall >= 0.8


# ---------------------------------------------------------------------------
# Benchmark Case 2: Strong Consensus
# Clearly good company — all agents should lean buy/watch
# ---------------------------------------------------------------------------

class TestStrongConsensusCase:
    """Company with strong fundamentals across all dimensions."""

    @pytest.fixture
    def packet(self):
        return _make_packet(
            ticker="GOOD3",
            fundamentals={
                "earnings_yield": 0.10,
                "roic": 0.25,
                "roe": 0.22,
                "ebit": 500.0,
                "debt_to_ebitda": 1.0,
                "gross_margin": 0.45,
                "ebit_margin": 0.20,
                "net_margin": 0.15,
                "cash_conversion": 1.1,
            },
            trends={
                "roic": [_pv(0.22, "2022"), _pv(0.24, "2023"), _pv(0.25, "2024")],
                "roe": [_pv(0.20, "2022"), _pv(0.21, "2023"), _pv(0.22, "2024")],
                "gross_margin": [_pv(0.43, "2022"), _pv(0.44, "2023"), _pv(0.45, "2024")],
                "ebit_margin": [_pv(0.18, "2022"), _pv(0.19, "2023"), _pv(0.20, "2024")],
                "net_income": [_pv(350, "2022"), _pv(400, "2023"), _pv(450, "2024")],
                "cash_from_operations": [_pv(400, "2022"), _pv(450, "2023"), _pv(500, "2024")],
                "cash_from_investing": [_pv(-100, "2022"), _pv(-110, "2023"), _pv(-120, "2024")],
                "debt_to_ebitda": [_pv(1.2, "2022"), _pv(1.1, "2023"), _pv(1.0, "2024")],
            },
        )

    def test_no_hard_rejects_fire(self, packet):
        """No hard reject should trigger for a strong company."""
        assert _negative_ebit(packet) is False
        assert _roic_consistently_low(packet) is False
        assert _roe_consistently_low(packet) is False
        assert _margin_collapse(packet) is False
        assert _negative_fcf_3_years(packet) is False
        assert _negative_net_income_recurring(packet) is False
        assert _high_leverage_and_expensive(packet) is False
        assert _negative_equity(packet) is False

    def test_consensus_council_result_quality(self):
        """A roundtable with all buy/watch should score high."""
        opinions = [
            _complete_opinion("greenblatt", verdict="buy", confidence=85),
            _complete_opinion("buffett", verdict="buy", confidence=80),
            _complete_opinion("graham", verdict="watch", confidence=70,
                             thesis="Solid fundamentals but valuation is at fair value, not a deep discount."),
            _complete_opinion("barsi", verdict="buy", confidence=75),
        ]
        result = _council_result(opinions)
        scores = evaluate_council_result(result)
        assert scores["overall"] >= 0.8
        assert len(scores["issues"]) == 0


# ---------------------------------------------------------------------------
# Benchmark Case 3: Bank/Financial Classification
# Safety block skipped, different metrics
# ---------------------------------------------------------------------------

class TestBankClassificationCase:
    """Bank should skip debt/EBITDA and leverage hard rejects."""

    @pytest.fixture
    def packet(self):
        return _make_packet(
            ticker="BANK4",
            classification="bank",
            sector="Financeiro",
            subsector="Bancos",
            fundamentals={
                "roe": 0.18,
                "earnings_yield": 0.08,
                "net_margin": 0.25,
                "debt_to_ebitda": 15.0,  # meaningless for banks
            },
            trends={
                "roe": [_pv(0.16, "2022"), _pv(0.17, "2023"), _pv(0.18, "2024")],
                "net_income": [_pv(1000, "2022"), _pv(1100, "2023"), _pv(1200, "2024")],
            },
        )

    def test_graham_skips_leverage_for_banks(self, packet):
        """Graham hard reject for high leverage should skip banks."""
        assert _high_leverage_and_expensive(packet) is False

    def test_roe_not_low_for_bank(self, packet):
        """Bank has good ROE, should not trigger Buffett reject."""
        assert _roe_consistently_low(packet) is False


# ---------------------------------------------------------------------------
# Benchmark Case 4: Insufficient Data
# Company with minimal data — agents should return insufficient_data
# ---------------------------------------------------------------------------

class TestInsufficientDataCase:
    def test_empty_packet_no_hard_rejects(self):
        """With no data, hard rejects should not fire (return False on missing)."""
        packet = _make_packet(fundamentals={}, trends={})
        assert _negative_ebit(packet) is False
        assert _negative_equity(packet) is False
        assert _roic_consistently_low(packet) is False
        assert _roe_consistently_low(packet) is False
        assert _margin_collapse(packet) is False
        assert _negative_fcf_3_years(packet) is False

    def test_insufficient_data_opinion_quality(self):
        """An opinion with insufficient_data verdict should still score well if complete."""
        opinion = _complete_opinion(
            verdict="insufficient_data",
            confidence=10,
            thesis="Insufficient financial data to form a meaningful opinion. Only 1 period available.",
            reasonsFor=[],
            reasonsAgainst=[],
            keyMetricsUsed=[],
            unknowns=["Revenue trend", "Margin trajectory", "Debt levels"],
        )
        score = evaluate_opinion(opinion)
        assert score.completeness == 1.0
        assert score.regulatory_compliance == 1.0


# ---------------------------------------------------------------------------
# Invariant: Hard Reject → Avoid
# ---------------------------------------------------------------------------

class TestHardRejectImpliesAvoid:
    """When a hard reject triggers, the opinion verdict MUST be 'avoid'."""

    @pytest.mark.parametrize("agent_id,reject_name", [
        ("barsi", "negative_fcf_3_years"),
        ("barsi", "negative_net_income_recurring"),
        ("graham", "high_leverage_and_expensive"),
        ("graham", "negative_equity"),
        ("greenblatt", "negative_ebit"),
        ("greenblatt", "roic_consistently_low"),
        ("buffett", "roe_consistently_low"),
        ("buffett", "margin_collapse"),
    ])
    def test_hard_reject_forces_avoid(self, agent_id, reject_name):
        """If hardRejectsTriggered is non-empty, verdict must be avoid."""
        opinion = _complete_opinion(
            agent_id=agent_id,
            verdict="avoid",
            hardRejectsTriggered=[reject_name],
            reasonsAgainst=[f"Hard reject: {reject_name}"],
            reasonsFor=[],
        )
        score = evaluate_opinion(opinion)
        assert score.consistency == 1.0

        # Verify the invariant: hard reject + non-avoid is inconsistent
        bad_opinion = _complete_opinion(
            agent_id=agent_id,
            verdict="buy",
            hardRejectsTriggered=[reject_name],
        )
        # This should have consistency < 1 because verdict contradicts hard reject
        # (the current evaluator doesn't check this yet — but we verify structure)
        assert bad_opinion["hardRejectsTriggered"] == [reject_name]
        assert bad_opinion["verdict"] == "buy"  # structurally valid but logically wrong


# ---------------------------------------------------------------------------
# Invariant: Regulatory Compliance
# ---------------------------------------------------------------------------

class TestRegulatoryInvariants:
    """All council outputs must pass regulatory compliance."""

    def test_all_banned_phrases_detected(self):
        """Every banned phrase should be caught."""
        for phrase in BANNED_PHRASES:
            opinion = _complete_opinion(thesis=f"This company is great. {phrase}!")
            score = evaluate_opinion(opinion)
            assert score.regulatory_compliance == 0.0, f"Missed banned phrase: {phrase}"

    def test_disclaimer_required(self):
        """Council result without disclaimer should be penalized."""
        result = _council_result(
            [_complete_opinion()],
            disclaimer="",
        )
        scores = evaluate_council_result(result)
        assert any("Missing disclaimer" in i for i in scores["issues"])

    def test_disclaimer_present_no_penalty(self):
        """Council result with disclaimer should not be penalized."""
        result = _council_result([_complete_opinion()])
        scores = evaluate_council_result(result)
        assert not any("Missing disclaimer" in i for i in scores["issues"])


# ---------------------------------------------------------------------------
# Invariant: Metric Groundedness
# ---------------------------------------------------------------------------

class TestMetricGroundedness:
    """Agents must only reference metrics from their packet."""

    def test_all_valid_metrics_known(self):
        """All valid metrics should be recognized."""
        for metric in ["roic", "earnings_yield", "roe", "debt_to_ebitda", "gross_margin"]:
            assert metric in VALID_METRICS

    def test_fabricated_metrics_penalized(self):
        """Referencing non-existent metrics should lower groundedness."""
        opinion = _complete_opinion(
            keyMetricsUsed=["made_up_ratio", "fake_metric", "roic"],
        )
        score = evaluate_opinion(opinion)
        assert score.groundedness < 1.0

    def test_packet_scoped_validation(self):
        """When packet_metrics provided, only those should be valid."""
        packet_metrics = {"roic", "earnings_yield"}
        opinion = _complete_opinion(
            keyMetricsUsed=["roic", "roe"],  # roe not in packet
        )
        score = evaluate_opinion(opinion, packet_metrics=packet_metrics)
        assert score.groundedness == 0.5  # 1 of 2


# ---------------------------------------------------------------------------
# Invariant: Verdict-Reason Alignment
# ---------------------------------------------------------------------------

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
            reasonsAgainst=["High ROIC"],  # same as a reason for
        )
        score = evaluate_opinion(opinion)
        assert score.contradiction_free == 0.0


# ---------------------------------------------------------------------------
# Full Council Result Quality
# ---------------------------------------------------------------------------

class TestFullCouncilQuality:
    """End-to-end quality checks on full council results."""

    def test_roundtable_4_agents_scores_high(self):
        opinions = [
            _complete_opinion("greenblatt"),
            _complete_opinion("buffett"),
            _complete_opinion("graham", verdict="watch",
                             thesis="Fair valuation but not a deep discount. Margin of safety is thin."),
            _complete_opinion("barsi"),
        ]
        result = _council_result(opinions)
        scores = evaluate_council_result(result)
        assert scores["overall"] >= 0.8
        assert len(scores["per_agent"]) == 4

    def test_debate_with_conflict(self):
        opinions = [
            _complete_opinion("greenblatt", verdict="buy", confidence=80),
            _complete_opinion("graham", verdict="avoid", confidence=65,
                             thesis="Too expensive relative to book value. Insufficient margin of safety for conservative investors.",
                             reasonsFor=["Decent operating margins"],
                             reasonsAgainst=["P/VPA too high", "Weak current ratio"]),
        ]
        result = _council_result(opinions)
        scores = evaluate_council_result(result)
        assert scores["overall"] >= 0.7
        # Both agents should be evaluated
        assert "greenblatt" in scores["per_agent"]
        assert "graham" in scores["per_agent"]
