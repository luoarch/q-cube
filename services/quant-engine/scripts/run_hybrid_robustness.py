"""Hybrid Robustness Lane — controlled comparison within Hybrid family.

Tests 4 Hybrid configs against 2 frozen controls (Original, Brazil).
Same protocol: IS 2020-H2→2023, OOS 2024, ^BVSP benchmark.

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/run_hybrid_robustness.py
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

from q3_quant_engine.backtest.benchmark import fetch_benchmark_curve
from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC
from q3_quant_engine.backtest.engine import BacktestConfig, run_backtest
from q3_quant_engine.backtest.statistical import compute_statistical_metrics
from q3_quant_engine.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("hybrid_robustness")

IS_START = date(2020, 7, 1)
IS_END = date(2023, 12, 31)
OOS_START = date(2024, 1, 2)
OOS_END = date(2024, 12, 31)
RESULTS_DIR = Path("results/hybrid_robustness")

CONFIGS = {
    # Controls (frozen, rejected)
    "ctrl_original_20m": {"strategy_type": "magic_formula_original", "top_n": 20, "rebalance_freq": "monthly"},
    "ctrl_brazil_20m": {"strategy_type": "magic_formula_brazil", "top_n": 20, "rebalance_freq": "monthly"},
    # Hybrid variants
    "hybrid_20m": {"strategy_type": "magic_formula_hybrid", "top_n": 20, "rebalance_freq": "monthly"},
    "hybrid_30m": {"strategy_type": "magic_formula_hybrid", "top_n": 30, "rebalance_freq": "monthly"},
    "hybrid_20q": {"strategy_type": "magic_formula_hybrid", "top_n": 20, "rebalance_freq": "quarterly"},
    "hybrid_30q": {"strategy_type": "magic_formula_hybrid", "top_n": 30, "rebalance_freq": "quarterly"},
}


def _make_config(start, end, **kw):
    return BacktestConfig(
        strategy_type=kw["strategy_type"], start_date=start, end_date=end,
        rebalance_freq=kw.get("rebalance_freq", "monthly"),
        top_n=kw.get("top_n", 20), execution_lag_days=1,
        equal_weight=True, cost_model=BRAZIL_REALISTIC,
        initial_capital=1_000_000.0, benchmark="^BVSP", lot_size=100,
    )


def _returns(ec):
    vals = [p["value"] for p in ec]
    return [(vals[i] - vals[i-1]) / vals[i-1] for i in range(1, len(vals)) if vals[i-1] > 0]


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    with SessionLocal() as session:
        for label, params in CONFIGS.items():
            logger.info("Running %s (IS + OOS)...", label)

            is_cfg = _make_config(IS_START, IS_END, **params)
            t0 = time.time()
            is_r = run_backtest(session, is_cfg)
            is_time = time.time() - t0

            oos_cfg = _make_config(OOS_START, OOS_END, **params)
            t0 = time.time()
            oos_r = run_backtest(session, oos_cfg)
            oos_time = time.time() - t0

            is_ret = _returns(is_r.equity_curve)
            oos_ret = _returns(oos_r.equity_curve)
            is_stats = compute_statistical_metrics(is_ret, is_r.metrics.get("sharpe", 0), n_trials=6) if len(is_ret) >= 3 else {}
            oos_stats = compute_statistical_metrics(oos_ret, oos_r.metrics.get("sharpe", 0), n_trials=6) if len(oos_ret) >= 3 else {}

            results[label] = {
                "params": params,
                "is": {**is_r.metrics, "trades": len(is_r.trades), "rebalances": len(is_r.rebalance_dates), **{f"stat_{k}": v for k, v in is_stats.items()}},
                "oos": {**oos_r.metrics, "trades": len(oos_r.trades), "rebalances": len(oos_r.rebalance_dates), **{f"stat_{k}": v for k, v in oos_stats.items()}},
                "oos_tickers": sorted({pos["ticker"] for h in oos_r.holdings_history for pos in h.get("holdings", [])}),
            }
            logger.info("  %s: IS Sharpe=%.4f OOS Sharpe=%.4f (%.0fs)", label,
                        is_r.metrics.get("sharpe", 0), oos_r.metrics.get("sharpe", 0), is_time + oos_time)

    # Save
    (RESULTS_DIR / "results.json").write_text(json.dumps(results, indent=2, default=str))

    # Report
    print(f"\n{'=' * 100}")
    print("HYBRID ROBUSTNESS LANE")
    print(f"{'=' * 100}")
    print(f"IS: {IS_START} → {IS_END} | OOS: {OOS_START} → {OOS_END} | Benchmark: ^BVSP")
    print()

    # Table 1: IS/OOS comparison
    labels = list(CONFIGS.keys())
    short = {k: k.replace("ctrl_", "").replace("magic_formula_", "") for k in labels}

    print("--- IS/OOS METRICS ---")
    header = f"{'':16s}" + "".join(f" {short[l]:>14s}" for l in labels)
    print(header)
    print("-" * (16 + 15 * len(labels)))

    for period in ["is", "oos"]:
        for m in ["cagr", "sharpe", "sortino", "max_drawdown"]:
            row = f"  {period.upper()} {m:11s}"
            for l in labels:
                v = results[l][period].get(m)
                if v is not None:
                    if m in ("cagr", "max_drawdown"):
                        row += f" {v*100:13.2f}%"
                    else:
                        row += f" {v:14.4f}"
                else:
                    row += f" {'—':>14s}"
            print(row)
        print()

    # Table 2: Degradation
    print("--- DEGRADATION IS → OOS ---")
    header = f"{'':16s}" + "".join(f" {short[l]:>14s}" for l in labels)
    print(header)
    print("-" * (16 + 15 * len(labels)))
    for m in ["sharpe", "cagr"]:
        row = f"  {m:14s}"
        for l in labels:
            is_v = results[l]["is"].get(m, 0)
            oos_v = results[l]["oos"].get(m, 0)
            if is_v != 0:
                deg = (oos_v - is_v) / abs(is_v) * 100
                row += f" {deg:+13.1f}%"
            else:
                row += f" {'—':>14s}"
        print(row)
    print()

    # Table 3: Benchmark-relative OOS
    print("--- BENCHMARK-RELATIVE (OOS) ---")
    header = f"{'':16s}" + "".join(f" {short[l]:>14s}" for l in labels)
    print(header)
    print("-" * (16 + 15 * len(labels)))
    for m in ["excess_return", "information_ratio"]:
        row = f"  {m:14s}"
        for l in labels:
            v = results[l]["oos"].get(m)
            if v is not None:
                if m == "excess_return":
                    row += f" {v*100:13.2f}%"
                else:
                    row += f" {v:14.4f}"
            else:
                row += f" {'—':>14s}"
        print(row)
    print()

    # Table 4: Statistical
    print("--- STATISTICAL (OOS) ---")
    header = f"{'':16s}" + "".join(f" {short[l]:>14s}" for l in labels)
    print(header)
    print("-" * (16 + 15 * len(labels)))
    for m in ["stat_psr", "stat_dsr"]:
        row = f"  {m:14s}"
        for l in labels:
            v = results[l]["oos"].get(m, 0)
            row += f" {v:14.4f}"
        print(row)
    print()

    # Key questions
    print("--- KEY FINDINGS ---")
    print()

    # Does Hybrid consistently beat controls?
    hybrid_variants = [l for l in labels if l.startswith("hybrid")]
    control_variants = [l for l in labels if l.startswith("ctrl")]

    best_hybrid_oos = max(hybrid_variants, key=lambda l: results[l]["oos"].get("sharpe", -99))
    best_control_oos = max(control_variants, key=lambda l: results[l]["oos"].get("sharpe", -99))

    bh_sharpe = results[best_hybrid_oos]["oos"]["sharpe"]
    bc_sharpe = results[best_control_oos]["oos"]["sharpe"]

    print(f"  Best Hybrid OOS:  {short[best_hybrid_oos]:14s} Sharpe={bh_sharpe:.4f}")
    print(f"  Best Control OOS: {short[best_control_oos]:14s} Sharpe={bc_sharpe:.4f}")
    if bh_sharpe > bc_sharpe:
        print(f"  → Hybrid edge: +{bh_sharpe - bc_sharpe:.4f} Sharpe")
    else:
        print(f"  → No Hybrid edge")
    print()

    # Sensitivity: does Hybrid hold across configs?
    hybrid_oos_sharpes = {short[l]: results[l]["oos"].get("sharpe", 0) for l in hybrid_variants}
    all_negative = all(s < 0 for s in hybrid_oos_sharpes.values())
    any_positive = any(s > 0 for s in hybrid_oos_sharpes.values())
    spread = max(hybrid_oos_sharpes.values()) - min(hybrid_oos_sharpes.values())

    print(f"  Hybrid OOS Sharpes: {hybrid_oos_sharpes}")
    print(f"  All negative: {all_negative}")
    print(f"  Spread: {spread:.4f}")
    if all_negative:
        print(f"  → Hybrid does NOT survive OOS 2024 in any configuration")
    elif any_positive:
        positive = {k: v for k, v in hybrid_oos_sharpes.items() if v > 0}
        print(f"  → Some configs survive: {positive}")
    print()

    # Least degraded
    least_deg = min(labels, key=lambda l: abs((results[l]["oos"].get("sharpe", 0) - results[l]["is"].get("sharpe", 0)) / max(abs(results[l]["is"].get("sharpe", 0)), 0.01)))
    print(f"  Least degraded: {short[least_deg]}")
    print(f"    IS Sharpe:  {results[least_deg]['is'].get('sharpe', 0):.4f}")
    print(f"    OOS Sharpe: {results[least_deg]['oos'].get('sharpe', 0):.4f}")
    print()

    # Promotion verdict
    print("--- PROMOTION VERDICT ---")
    for l in hybrid_variants:
        oos_sharpe = results[l]["oos"].get("sharpe", 0)
        oos_dsr = results[l]["oos"].get("stat_dsr", 0)
        is_sharpe = results[l]["is"].get("sharpe", 0)
        deg = abs((oos_sharpe - is_sharpe) / max(abs(is_sharpe), 0.01) * 100)
        passes_oos = oos_sharpe > 0.3
        passes_dsr = oos_dsr > 0.5
        passes_deg = deg < 50

        status = "PROMOTABLE" if (passes_oos and passes_dsr and passes_deg) else "REJECTED"
        print(f"  {short[l]:14s}: OOS Sharpe={oos_sharpe:.4f} DSR={oos_dsr:.4f} Deg={deg:.0f}%  → {status}")

    print()
    print(f"Artifacts: {RESULTS_DIR}")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
