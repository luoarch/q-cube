"""Tests for council agent hard reject logic (Sprint 4).

Hard rejects are deterministic checks run before LLM call.
If triggered, verdict is locked to 'avoid'.
"""

from __future__ import annotations

import pytest

from q3_ai_assistant.council.packet import AssetAnalysisPacket, PeriodValue
from q3_ai_assistant.council.agents.barsi import _negative_fcf_3_years, _negative_net_income_recurring
from q3_ai_assistant.council.agents.graham import _high_leverage_and_expensive, _negative_equity
from q3_ai_assistant.council.agents.greenblatt import _negative_ebit, _roic_consistently_low
from q3_ai_assistant.council.agents.buffett import _roe_consistently_low, _margin_collapse


def _make_packet(**overrides) -> AssetAnalysisPacket:
    defaults = dict(
        issuer_id="test-id",
        ticker="TEST3",
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


def _pv(val: float | None, d: str = "2024-12-31") -> PeriodValue:
    return PeriodValue(reference_date=d, value=val)


# ---------------------------------------------------------------------------
# Barsi hard rejects
# ---------------------------------------------------------------------------

class TestBarsiNegativeFcf3y:
    def test_not_triggered_insufficient_data(self):
        packet = _make_packet(trends={
            "cash_from_operations": [_pv(100), _pv(200)],
            "cash_from_investing": [_pv(-50), _pv(-60)],
        })
        assert _negative_fcf_3_years(packet) is False

    def test_not_triggered_positive_fcf(self):
        packet = _make_packet(trends={
            "cash_from_operations": [_pv(100), _pv(200), _pv(300)],
            "cash_from_investing": [_pv(-50), _pv(-60), _pv(-70)],
        })
        assert _negative_fcf_3_years(packet) is False

    def test_triggered_negative_fcf_all_3(self):
        packet = _make_packet(trends={
            "cash_from_operations": [_pv(10), _pv(20), _pv(30)],
            "cash_from_investing": [_pv(-50), _pv(-60), _pv(-70)],
        })
        assert _negative_fcf_3_years(packet) is True

    def test_not_triggered_one_positive(self):
        packet = _make_packet(trends={
            "cash_from_operations": [_pv(10), _pv(20), _pv(100)],
            "cash_from_investing": [_pv(-50), _pv(-60), _pv(-70)],
        })
        # 100 + (-70) = 30 >= 0, so not triggered
        assert _negative_fcf_3_years(packet) is False


class TestBarsiNegativeNiRecurring:
    def test_not_triggered_insufficient_data(self):
        packet = _make_packet(trends={"net_income": [_pv(-10)]})
        assert _negative_net_income_recurring(packet) is False

    def test_triggered_two_negatives(self):
        packet = _make_packet(trends={
            "net_income": [_pv(-10), _pv(-5), _pv(20)]
        })
        assert _negative_net_income_recurring(packet) is True

    def test_not_triggered_one_negative(self):
        packet = _make_packet(trends={
            "net_income": [_pv(-10), _pv(5), _pv(20)]
        })
        assert _negative_net_income_recurring(packet) is False


# ---------------------------------------------------------------------------
# Graham hard rejects
# ---------------------------------------------------------------------------

class TestGrahamHighLeverageExpensive:
    def test_skips_banks(self):
        packet = _make_packet(
            classification="bank",
            fundamentals={"debt_to_ebitda": 10.0, "earnings_yield": 0.01},
        )
        assert _high_leverage_and_expensive(packet) is False

    def test_triggered(self):
        packet = _make_packet(
            fundamentals={"debt_to_ebitda": 6.0, "earnings_yield": 0.03},
        )
        assert _high_leverage_and_expensive(packet) is True

    def test_not_triggered_low_debt(self):
        packet = _make_packet(
            fundamentals={"debt_to_ebitda": 3.0, "earnings_yield": 0.03},
        )
        assert _high_leverage_and_expensive(packet) is False

    def test_not_triggered_high_ey(self):
        packet = _make_packet(
            fundamentals={"debt_to_ebitda": 6.0, "earnings_yield": 0.10},
        )
        assert _high_leverage_and_expensive(packet) is False

    def test_not_triggered_missing_data(self):
        packet = _make_packet(fundamentals={})
        assert _high_leverage_and_expensive(packet) is False


class TestGrahamNegativeEquity:
    def test_triggered(self):
        packet = _make_packet(fundamentals={"equity": -100.0})
        assert _negative_equity(packet) is True

    def test_not_triggered_positive(self):
        packet = _make_packet(fundamentals={"equity": 500.0})
        assert _negative_equity(packet) is False

    def test_not_triggered_missing(self):
        packet = _make_packet(fundamentals={})
        assert _negative_equity(packet) is False


# ---------------------------------------------------------------------------
# Greenblatt hard rejects
# ---------------------------------------------------------------------------

class TestGreenblattNegativeEbit:
    def test_triggered(self):
        packet = _make_packet(fundamentals={"ebit": -50.0})
        assert _negative_ebit(packet) is True

    def test_triggered_zero(self):
        packet = _make_packet(fundamentals={"ebit": 0.0})
        assert _negative_ebit(packet) is True

    def test_not_triggered(self):
        packet = _make_packet(fundamentals={"ebit": 100.0})
        assert _negative_ebit(packet) is False


class TestGreenblattRoicLow:
    def test_not_triggered_insufficient_data(self):
        packet = _make_packet(trends={"roic": [_pv(0.03)]})
        assert _roic_consistently_low(packet) is False

    def test_triggered(self):
        packet = _make_packet(trends={"roic": [_pv(0.03), _pv(0.04)]})
        assert _roic_consistently_low(packet) is True

    def test_not_triggered_one_high(self):
        packet = _make_packet(trends={"roic": [_pv(0.03), _pv(0.10)]})
        assert _roic_consistently_low(packet) is False


# ---------------------------------------------------------------------------
# Buffett hard rejects
# ---------------------------------------------------------------------------

class TestBuffettRoeLow:
    def test_not_triggered_insufficient(self):
        packet = _make_packet(trends={"roe": [_pv(0.05)]})
        assert _roe_consistently_low(packet) is False

    def test_triggered(self):
        packet = _make_packet(trends={"roe": [_pv(0.05), _pv(0.06)]})
        assert _roe_consistently_low(packet) is True

    def test_not_triggered_above_threshold(self):
        packet = _make_packet(trends={"roe": [_pv(0.10), _pv(0.12)]})
        assert _roe_consistently_low(packet) is False


class TestBuffettMarginCollapse:
    def test_not_triggered_insufficient(self):
        packet = _make_packet(trends={"gross_margin": [_pv(0.30), _pv(0.25)]})
        assert _margin_collapse(packet) is False

    def test_triggered(self):
        # 0.20 < 0.40 * 0.7 = 0.28
        packet = _make_packet(trends={
            "gross_margin": [_pv(0.40), _pv(0.30), _pv(0.20)]
        })
        assert _margin_collapse(packet) is True

    def test_not_triggered_stable(self):
        packet = _make_packet(trends={
            "gross_margin": [_pv(0.40), _pv(0.38), _pv(0.36)]
        })
        assert _margin_collapse(packet) is False
