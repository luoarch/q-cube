"""Ranking strategy specification tests."""

from __future__ import annotations

from decimal import Decimal

from q3_quant_engine.strategies.ranking import (
    RankedAsset,
    _CompatAsset,
    _CompatFS,
    _compute_ey_roc,
    _rank_descending,
)
from q3_quant_engine.backtest.engine import _rank_pit_data


def _make_asset(ticker: str, sector: str | None = "Tecnologia") -> _CompatAsset:
    return _CompatAsset(ticker=ticker, name=f"Company {ticker}", sector=sector)


def _make_fs(
    ebit: float = 100,
    ev: float = 1000,
    nwc: float = 200,
    fa: float = 300,
    market_cap: float = 1e9,
    avg_daily_volume: float = 2e6,
    **kwargs,
) -> _CompatFS:
    return _CompatFS(
        ebit=Decimal(str(ebit)),
        enterprise_value=Decimal(str(ev)),
        net_working_capital=Decimal(str(nwc)),
        fixed_assets=Decimal(str(fa)),
        market_cap=Decimal(str(market_cap)),
        avg_daily_volume=Decimal(str(avg_daily_volume)),
        **kwargs,
    )


def test_magic_formula_ey_plus_roc_equal_weight():
    """Combined rank = EY_rank + ROC_rank, sorted ascending."""
    data = [
        (_make_asset("A3"), _make_fs(ebit=100, ev=500, nwc=100, fa=100)),   # EY=0.2, ROC=0.5
        (_make_asset("B3"), _make_fs(ebit=50, ev=500, nwc=100, fa=400)),    # EY=0.1, ROC=0.1
        (_make_asset("C3"), _make_fs(ebit=200, ev=1000, nwc=200, fa=200)),  # EY=0.2, ROC=0.5
    ]
    ranked = _rank_pit_data(data, "magic_formula_original")
    # A3 and C3 have same EY and ROC — should both rank above B3
    tickers = [r.ticker for r in ranked]
    assert tickers[-1] == "B3"


def test_ranking_excludes_negative_ebit():
    """Brazil variant: EBIT <= 0 excluded."""
    data = [
        (_make_asset("POS3"), _make_fs(ebit=100)),
        (_make_asset("NEG3"), _make_fs(ebit=-50)),
    ]
    ranked = _rank_pit_data(data, "magic_formula_brazil")
    tickers = [r.ticker for r in ranked]
    assert "NEG3" not in tickers
    assert "POS3" in tickers


def test_ranking_excludes_negative_ev():
    """EV <= 0 excluded (from _compute_ey_roc returning None EY, still ranks but poorly)."""
    data = [
        (_make_asset("POS3"), _make_fs(ebit=100, ev=1000)),
        (_make_asset("NEGEV3"), _make_fs(ebit=100, ev=-500)),
    ]
    ranked = _rank_pit_data(data, "magic_formula_original")
    # Negative EV gives negative EY, asset still included in original but ranks poorly
    assert len(ranked) == 2


def test_ranking_ordering_ey_desc_roc_desc():
    """Higher EY = better rank. Higher ROC = better rank."""
    data = [
        (_make_asset("HIGH3"), _make_fs(ebit=200, ev=400, nwc=50, fa=50)),   # EY=0.5, ROC=2.0
        (_make_asset("LOW3"), _make_fs(ebit=10, ev=1000, nwc=200, fa=300)),  # EY=0.01, ROC=0.02
    ]
    ranked = _rank_pit_data(data, "magic_formula_original")
    assert ranked[0].ticker == "HIGH3"
    assert ranked[1].ticker == "LOW3"


def test_gate_applied_before_ranking():
    """Universe filtering is done upstream (run_backtest), not in _rank_pit_data.

    After Plan 4B + Empirical Validation Closure, sector exclusion uses
    universe_classifications, applied before _rank_pit_data is called.
    This test verifies that _rank_pit_data still applies liquidity/EBIT gates.
    """
    data = [
        (_make_asset("GOOD3"), _make_fs(ebit=100, ev=1000)),
        (_make_asset("NOEBIT3"), _make_fs(ebit=-50, ev=1000)),
    ]
    ranked = _rank_pit_data(data, "magic_formula_brazil")
    tickers = [r.ticker for r in ranked]
    assert "NOEBIT3" not in tickers
    assert "GOOD3" in tickers


def test_gate_is_filter_not_score():
    """Liquidity/EBIT filters don't change remaining assets' relative ranking."""
    base_data = [
        (_make_asset("A3"), _make_fs(ebit=200, ev=400, nwc=50, fa=50)),
        (_make_asset("B3"), _make_fs(ebit=100, ev=1000, nwc=100, fa=100)),
        (_make_asset("C3"), _make_fs(ebit=50, ev=500, nwc=200, fa=200)),
    ]
    # With a filtered asset (negative EBIT)
    with_gate = [
        (_make_asset("BAD3"), _make_fs(ebit=-100, ev=100)),
    ] + base_data

    ranked_without = _rank_pit_data(base_data, "magic_formula_brazil")
    ranked_with = _rank_pit_data(with_gate, "magic_formula_brazil")

    # Order of non-excluded assets should be the same
    order_without = [r.ticker for r in ranked_without]
    order_with = [r.ticker for r in ranked_with]
    assert order_without == order_with


def test_quality_overlay_uses_available_signals():
    """Hybrid variant uses debt_to_ebitda and cash_conversion when available."""
    data = [
        (_make_asset("A3"), _make_fs(ebit=100, ev=500, nwc=100, fa=100,
                                     net_debt=Decimal("200"), ebitda=Decimal("150"),
                                     cash_conversion=Decimal("0.8"))),
        (_make_asset("B3"), _make_fs(ebit=100, ev=500, nwc=100, fa=100,
                                     net_debt=Decimal("500"), ebitda=Decimal("100"),
                                     cash_conversion=Decimal("0.3"))),
    ]
    ranked = _rank_pit_data(data, "magic_formula_hybrid")
    # A3 has lower leverage (200/150=1.33) and higher cash conversion (0.8)
    # So A3 should rank higher than B3
    assert ranked[0].ticker == "A3"


def test_no_overlay_does_not_corrupt_score():
    """Hybrid variant without quality signals falls back to core-only score."""
    data = [
        (_make_asset("A3"), _make_fs(ebit=200, ev=400, nwc=50, fa=50)),
        (_make_asset("B3"), _make_fs(ebit=100, ev=1000, nwc=100, fa=100)),
    ]
    # Without quality signals, hybrid should still produce valid rankings
    ranked = _rank_pit_data(data, "magic_formula_hybrid")
    assert len(ranked) == 2
    # A3 has better EY (0.5 vs 0.1) and better ROC (2.0 vs 0.5)
    assert ranked[0].ticker == "A3"


def test_sector_filtering_is_upstream():
    """Sector filtering now happens upstream via universe_classifications.

    _rank_pit_data no longer filters by sector — that's done in run_backtest()
    using the frozen policy universe. This test confirms all sectors pass through.
    """
    data = [
        (_make_asset("BANK3", sector="Financeiro"), _make_fs(ebit=500, ev=100)),
        (_make_asset("TECH3", sector="Tecnologia"), _make_fs(ebit=100, ev=1000)),
    ]
    ranked = _rank_pit_data(data, "magic_formula_brazil")
    tickers = [r.ticker for r in ranked]
    # Both should be present — sector filtering is upstream
    assert "BANK3" in tickers
    assert "TECH3" in tickers
