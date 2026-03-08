"""Tests for the deterministic comparison engine (Sprint 3)."""

from __future__ import annotations

import pytest

from q3_quant_engine.comparison.rules import COMPARISON_RULES, RULES_VERSION, ComparisonRule
from q3_quant_engine.comparison.types import MetricComparison, WinnerSummary, ComparisonMatrix
from q3_quant_engine.comparison.engine import (
    _latest_value,
    _avg_value,
    _stdev_value,
    _determine_winner,
)
from q3_quant_engine.refiner.types import PeriodValue


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def pv(val: float | None, date: str = "2024-12-31") -> PeriodValue:
    return PeriodValue(reference_date=date, value=val)


# ---------------------------------------------------------------------------
# _latest_value
# ---------------------------------------------------------------------------

class TestLatestValue:
    def test_empty(self):
        assert _latest_value([]) is None

    def test_single(self):
        assert _latest_value([pv(1.5)]) == 1.5

    def test_picks_last_non_none(self):
        assert _latest_value([pv(1.0), pv(2.0), pv(None)]) == 2.0

    def test_all_none(self):
        assert _latest_value([pv(None), pv(None)]) is None


# ---------------------------------------------------------------------------
# _avg_value
# ---------------------------------------------------------------------------

class TestAvgValue:
    def test_empty(self):
        assert _avg_value([]) is None

    def test_single(self):
        assert _avg_value([pv(3.0)]) == 3.0

    def test_average(self):
        assert _avg_value([pv(1.0), pv(2.0), pv(3.0)]) == 2.0

    def test_skips_none(self):
        assert _avg_value([pv(1.0), pv(None), pv(3.0)]) == 2.0

    def test_all_none(self):
        assert _avg_value([pv(None), pv(None)]) is None


# ---------------------------------------------------------------------------
# _stdev_value
# ---------------------------------------------------------------------------

class TestStdevValue:
    def test_empty(self):
        assert _stdev_value([]) is None

    def test_single_value(self):
        assert _stdev_value([pv(1.0)]) is None

    def test_two_same(self):
        assert _stdev_value([pv(1.0), pv(1.0)]) == 0.0

    def test_standard(self):
        result = _stdev_value([pv(1.0), pv(2.0), pv(3.0)])
        assert result is not None
        assert abs(result - 1.0) < 0.01


# ---------------------------------------------------------------------------
# _determine_winner
# ---------------------------------------------------------------------------

class TestDetermineWinner:
    rule_higher = ComparisonRule("roe", "higher_better", "latest", 0.01)
    rule_lower = ComparisonRule("debt_to_ebitda", "lower_better", "latest", 0.3)
    rule_stdev = ComparisonRule("margin_stability", "lower_stdev_better", "stdev_3p", 0.005)

    def test_no_data(self):
        w, o, m = _determine_winner({"A": None, "B": None}, self.rule_higher)
        assert o == "inconclusive"
        assert w is None

    def test_one_has_data(self):
        w, o, m = _determine_winner({"A": 0.15, "B": None}, self.rule_higher)
        assert o == "win"
        assert w == "A"

    def test_higher_better_clear_win(self):
        w, o, m = _determine_winner({"A": 0.20, "B": 0.10}, self.rule_higher)
        assert o == "win"
        assert w == "A"
        assert m is not None
        assert abs(m - 0.10) < 0.001

    def test_higher_better_tie(self):
        w, o, m = _determine_winner({"A": 0.100, "B": 0.105}, self.rule_higher)
        assert o == "tie"
        assert w is None

    def test_lower_better_clear_win(self):
        w, o, m = _determine_winner({"A": 3.0, "B": 1.5}, self.rule_lower)
        assert o == "win"
        assert w == "B"

    def test_lower_better_tie(self):
        w, o, m = _determine_winner({"A": 2.0, "B": 2.1}, self.rule_lower)
        assert o == "tie"
        assert w is None

    def test_stdev_lower_is_better(self):
        w, o, m = _determine_winner({"A": 0.05, "B": 0.01}, self.rule_stdev)
        assert o == "win"
        assert w == "B"

    def test_three_issuers(self):
        w, o, m = _determine_winner({"A": 0.20, "B": 0.15, "C": 0.05}, self.rule_higher)
        assert o == "win"
        assert w == "A"


# ---------------------------------------------------------------------------
# Rules config
# ---------------------------------------------------------------------------

class TestRulesConfig:
    def test_rules_version(self):
        assert RULES_VERSION == 1

    def test_eleven_rules(self):
        assert len(COMPARISON_RULES) == 11

    def test_all_rules_have_required_fields(self):
        for rule in COMPARISON_RULES:
            assert rule.metric
            assert rule.direction in ("higher_better", "lower_better", "lower_stdev_better")
            assert rule.comparison_mode in ("latest", "avg_3p", "stdev_3p")
            assert rule.tolerance > 0


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class TestTypes:
    def test_metric_comparison_frozen(self):
        mc = MetricComparison(
            metric="roe", direction="higher_better", comparison_mode="latest",
            tolerance=0.01, values={"A": 0.15}, winner="A",
            outcome="win", margin=None,
        )
        with pytest.raises(AttributeError):
            mc.metric = "other"  # type: ignore[misc]

    def test_winner_summary(self):
        ws = WinnerSummary(
            issuer_id="A", ticker="WEGE3",
            wins=5, ties=2, losses=3, inconclusive=1,
        )
        assert ws.wins == 5

    def test_comparison_matrix(self):
        cm = ComparisonMatrix(
            issuer_ids=["A", "B"],
            tickers=["WEGE3", "ITUB4"],
            metrics=[],
            summaries=[],
            rules_version=1,
            data_reliability={"A": "high", "B": "medium"},
        )
        assert cm.rules_version == 1
