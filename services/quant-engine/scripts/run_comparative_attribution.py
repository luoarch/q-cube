"""Comparative OOS Failure Attribution — original vs brazil vs hybrid.

Same protocol for all 3 variants:
- Universe: frozen policy v1 (CORE_ELIGIBLE)
- IS: 2020-07-01 → 2023-12-31
- OOS: 2024-01-02 → 2024-12-31
- Benchmark: ^BVSP (price index)
- Costs: BRAZIL_REALISTIC
- Rebalance: monthly
- Top N: 20
- Equal weight

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/run_comparative_attribution.py
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from q3_quant_engine.backtest.benchmark import fetch_benchmark_curve
from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC
from q3_quant_engine.backtest.engine import BacktestConfig, run_backtest
from q3_quant_engine.backtest.statistical import compute_statistical_metrics
from q3_quant_engine.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("comparative")

IS_START = date(2020, 7, 1)
IS_END = date(2023, 12, 31)
OOS_START = date(2024, 1, 2)
OOS_END = date(2024, 12, 31)
BENCHMARK = "^BVSP"
RESULTS_DIR = Path("results/comparative_attribution")

VARIANTS = ["magic_formula_original", "magic_formula_brazil", "magic_formula_hybrid"]


def _make_config(strategy: str, start: date, end: date) -> BacktestConfig:
    return BacktestConfig(
        strategy_type=strategy,
        start_date=start,
        end_date=end,
        rebalance_freq="monthly",
        execution_lag_days=1,
        top_n=20,
        equal_weight=True,
        cost_model=BRAZIL_REALISTIC,
        initial_capital=1_000_000.0,
        benchmark=BENCHMARK,
        lot_size=100,
    )


def _returns(equity_curve):
    vals = [p["value"] for p in equity_curve]
    return [(vals[i] - vals[i-1]) / vals[i-1] for i in range(1, len(vals)) if vals[i-1] > 0]


def _extract_holdings(holdings_history):
    """Extract ticker sets per rebalance from holdings_history."""
    result = []
    for h in holdings_history:
        tickers = {pos["ticker"] for pos in h.get("holdings", [])}
        result.append({"date": h["date"], "tickers": tickers})
    return result


def _trade_pnl(trades, side="sell"):
    """Compute P&L per ticker from sell trades."""
    pnl = defaultdict(float)
    for t in trades:
        if t.get("side") == side:
            # Approximate: sell value - cost
            pnl[t["ticker"]] += t["shares"] * t["price"] - t.get("cost", 0)
    return dict(pnl)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    # Fetch benchmark once
    logger.info("Fetching benchmark...")
    bench = fetch_benchmark_curve(IS_START, OOS_END, ticker=BENCHMARK)
    bench_oos = [p for p in bench if isinstance(p["date"], date) and p["date"] >= OOS_START]

    with SessionLocal() as session:
        for variant in VARIANTS:
            logger.info("=" * 60)
            logger.info("Running %s", variant)
            logger.info("=" * 60)

            # IS
            is_cfg = _make_config(variant, IS_START, IS_END)
            t0 = time.time()
            is_result = run_backtest(session, is_cfg)
            is_time = time.time() - t0

            # OOS
            oos_cfg = _make_config(variant, OOS_START, OOS_END)
            t0 = time.time()
            oos_result = run_backtest(session, oos_cfg)
            oos_time = time.time() - t0

            # Stats
            is_ret = _returns(is_result.equity_curve)
            oos_ret = _returns(oos_result.equity_curve)
            is_stats = compute_statistical_metrics(is_ret, is_result.metrics.get("sharpe", 0), n_trials=3) if len(is_ret) >= 3 else {}
            oos_stats = compute_statistical_metrics(oos_ret, oos_result.metrics.get("sharpe", 0), n_trials=3) if len(oos_ret) >= 3 else {}

            # OOS holdings analysis
            oos_holdings = _extract_holdings(oos_result.holdings_history)
            all_oos_tickers = set()
            for h in oos_holdings:
                all_oos_tickers.update(h["tickers"])

            # Sector attribution from trades
            sector_pnl = defaultdict(float)
            ticker_pnl = defaultdict(float)
            for t in oos_result.trades:
                if t.get("side") == "sell":
                    pnl = t["shares"] * t["price"] - t.get("cost", 0)
                    ticker_pnl[t["ticker"]] += pnl

            results[variant] = {
                "is_metrics": is_result.metrics,
                "oos_metrics": oos_result.metrics,
                "is_stats": is_stats,
                "oos_stats": oos_stats,
                "is_time": is_time,
                "oos_time": oos_time,
                "is_trades": len(is_result.trades),
                "oos_trades": len(oos_result.trades),
                "is_rebalances": len(is_result.rebalance_dates),
                "oos_rebalances": len(oos_result.rebalance_dates),
                "oos_tickers": sorted(all_oos_tickers),
                "oos_ticker_pnl": dict(sorted(ticker_pnl.items(), key=lambda x: x[1])),
                "oos_equity_curve": oos_result.equity_curve,
            }

    # Compute overlaps between variants
    overlaps = {}
    for v1 in VARIANTS:
        for v2 in VARIANTS:
            if v1 >= v2:
                continue
            t1 = set(results[v1]["oos_tickers"])
            t2 = set(results[v2]["oos_tickers"])
            overlap = t1 & t2
            overlaps[f"{v1} ∩ {v2}"] = {
                "count": len(overlap),
                "pct_of_v1": len(overlap) / max(len(t1), 1) * 100,
                "pct_of_v2": len(overlap) / max(len(t2), 1) * 100,
                "tickers": sorted(overlap),
            }

    # Save artifacts
    (RESULTS_DIR / "results.json").write_text(json.dumps({
        k: {kk: vv for kk, vv in v.items() if kk != "oos_equity_curve"}
        for k, v in results.items()
    }, indent=2, default=str))
    (RESULTS_DIR / "overlaps.json").write_text(json.dumps(overlaps, indent=2))

    # Print report
    print(f"\n{'=' * 80}")
    print("COMPARATIVE OOS FAILURE ATTRIBUTION")
    print(f"{'=' * 80}")
    print(f"Protocol: Top 20 | Monthly | Equal weight | BRAZIL_REALISTIC costs")
    print(f"IS: {IS_START} → {IS_END} | OOS: {OOS_START} → {OOS_END}")
    print(f"Benchmark: {BENCHMARK} (price index)")
    print()

    # === Table 1: IS/OOS comparison ===
    print("--- 1. IS/OOS METRICS BY VARIANT ---")
    print(f"{'':20s} {'original':>12s} {'brazil':>12s} {'hybrid':>12s}")
    print("-" * 58)

    for period_label, metric_key in [("IS", "is_metrics"), ("OOS", "oos_metrics")]:
        for m in ["cagr", "sharpe", "sortino", "max_drawdown", "turnover_avg"]:
            row = f"  {period_label} {m:16s}"
            for v in VARIANTS:
                val = results[v][metric_key].get(m)
                if val is not None:
                    if m in ("cagr", "max_drawdown", "turnover_avg"):
                        row += f" {val*100:11.2f}%"
                    else:
                        row += f" {val:12.4f}"
                else:
                    row += f" {'—':>12s}"
            print(row)
        print()

    # === Table 2: Degradation ===
    print("--- 2. DEGRADATION IS → OOS ---")
    print(f"{'Metric':20s} {'original':>12s} {'brazil':>12s} {'hybrid':>12s}")
    print("-" * 58)
    for m in ["sharpe", "cagr"]:
        row = f"  {m:18s}"
        for v in VARIANTS:
            is_val = results[v]["is_metrics"].get(m, 0)
            oos_val = results[v]["oos_metrics"].get(m, 0)
            if is_val != 0:
                deg = (oos_val - is_val) / abs(is_val) * 100
                row += f" {deg:+11.1f}%"
            else:
                row += f" {'—':>12s}"
        print(row)
    print()

    # === Table 3: Statistical metrics ===
    print("--- 3. STATISTICAL METRICS ---")
    print(f"{'':20s} {'original':>12s} {'brazil':>12s} {'hybrid':>12s}")
    print("-" * 58)
    for period_label, stats_key in [("IS", "is_stats"), ("OOS", "oos_stats")]:
        for m in ["psr", "dsr"]:
            row = f"  {period_label} {m:16s}"
            for v in VARIANTS:
                val = results[v][stats_key].get(m, 0)
                row += f" {val:12.4f}"
            print(row)
    print()

    # === Table 4: Holdings overlap ===
    print("--- 4. OOS HOLDINGS OVERLAP ---")
    for label, data in overlaps.items():
        print(f"  {label}: {data['count']} tickers ({data['pct_of_v1']:.0f}% / {data['pct_of_v2']:.0f}%)")
    print()

    # === Table 5: Worst OOS positions per variant ===
    print("--- 5. WORST OOS POSITIONS (by sell P&L proxy) ---")
    for v in VARIANTS:
        short_name = v.replace("magic_formula_", "")
        pnl = results[v]["oos_ticker_pnl"]
        sorted_pnl = sorted(pnl.items(), key=lambda x: x[1])
        print(f"  {short_name}:")
        for ticker, val in sorted_pnl[:5]:
            print(f"    {ticker:8s}  R$ {val:>12,.0f}")
        print()

    # === Table 6: Best OOS positions per variant ===
    print("--- 6. BEST OOS POSITIONS ---")
    for v in VARIANTS:
        short_name = v.replace("magic_formula_", "")
        pnl = results[v]["oos_ticker_pnl"]
        sorted_pnl = sorted(pnl.items(), key=lambda x: x[1], reverse=True)
        print(f"  {short_name}:")
        for ticker, val in sorted_pnl[:5]:
            print(f"    {ticker:8s}  R$ {val:>12,.0f}")
        print()

    # === Key questions ===
    print("--- 7. KEY QUESTIONS ---")
    print()

    # Q1: Is OOS collapse structural or variant-specific?
    oos_sharpes = {v.replace("magic_formula_", ""): results[v]["oos_metrics"].get("sharpe", 0) for v in VARIANTS}
    all_negative = all(s < 0 for s in oos_sharpes.values())
    print(f"  Q1. OOS collapse structural?")
    print(f"       OOS Sharpes: {oos_sharpes}")
    if all_negative:
        print(f"       → YES: all 3 variants have negative OOS Sharpe. Problem is upstream of variant-specific logic.")
    else:
        best = max(oos_sharpes, key=oos_sharpes.get)
        print(f"       → PARTIAL: {best} held up better. Variant-specific logic matters.")
    print()

    # Q2: Do Brazil gates help or hurt?
    orig_oos = results["magic_formula_original"]["oos_metrics"].get("sharpe", 0)
    brazil_oos = results["magic_formula_brazil"]["oos_metrics"].get("sharpe", 0)
    print(f"  Q2. Do Brazil gates help?")
    print(f"       original OOS Sharpe: {orig_oos:.4f}")
    print(f"       brazil OOS Sharpe:   {brazil_oos:.4f}")
    if brazil_oos > orig_oos:
        print(f"       → YES: gates improved OOS by {(brazil_oos - orig_oos):.4f}")
    else:
        print(f"       → NO: gates made OOS worse by {(orig_oos - brazil_oos):.4f}")
    print()

    # Q3: Does hybrid help OOS?
    hybrid_oos = results["magic_formula_hybrid"]["oos_metrics"].get("sharpe", 0)
    print(f"  Q3. Does hybrid overlay help OOS?")
    print(f"       brazil OOS Sharpe:   {brazil_oos:.4f}")
    print(f"       hybrid OOS Sharpe:   {hybrid_oos:.4f}")
    if hybrid_oos > brazil_oos:
        print(f"       → YES: quality overlay improved OOS by {(hybrid_oos - brazil_oos):.4f}")
    else:
        print(f"       → NO: quality overlay made OOS worse by {(brazil_oos - hybrid_oos):.4f}")
    print()

    # Q4: Concentration or broad-based loss?
    for v in VARIANTS:
        short_name = v.replace("magic_formula_", "")
        pnl = results[v]["oos_ticker_pnl"]
        if not pnl:
            continue
        total_loss = sum(val for val in pnl.values() if val < 0)
        worst_5_loss = sum(val for val in sorted(pnl.values())[:5])
        pct = worst_5_loss / total_loss * 100 if total_loss < 0 else 0
        print(f"  Q4. Loss concentration ({short_name}):")
        print(f"       Total negative P&L:    R$ {total_loss:>12,.0f}")
        print(f"       Worst 5 positions:     R$ {worst_5_loss:>12,.0f} ({pct:.0f}% of total loss)")
    print()

    print(f"Artifacts: {RESULTS_DIR}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
