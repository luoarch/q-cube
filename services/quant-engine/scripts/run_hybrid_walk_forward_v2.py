"""Walk-Forward v2 — OOS anual, compatível com quarterly rebalance.

Each OOS window is 12 months (≥4 quarterly rebalance events).
Expanding IS, rolling 12-month OOS.

Splits:
  Split 1: IS 2020-H2→2021 | OOS 2022 (full year)
  Split 2: IS 2020-H2→2022 | OOS 2023 (full year)
  Split 3: IS 2020-H2→2023 | OOS 2024 (full year)

Controls: ctrl_original_20m, ctrl_brazil_20m (frozen).

Reporting:
  - trade_count per split (mandatory)
  - active vs inactive splits separated
  - two statistics: all_splits and active_splits_only

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/run_hybrid_walk_forward_v2.py
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC
from q3_quant_engine.backtest.engine import BacktestConfig, run_backtest
from q3_quant_engine.backtest.statistical import compute_statistical_metrics
from q3_quant_engine.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("wf_v2")

RESULTS_DIR = Path("results/hybrid_walk_forward_v2")

# 12-month OOS windows → ≥4 quarterly rebalances per split
SPLITS = [
    {"label": "Split 1", "is_end": date(2021, 12, 31), "oos_start": date(2022, 1, 3), "oos_end": date(2022, 12, 30)},
    {"label": "Split 2", "is_end": date(2022, 12, 30), "oos_start": date(2023, 1, 2), "oos_end": date(2023, 12, 29)},
    {"label": "Split 3", "is_end": date(2023, 12, 29), "oos_start": date(2024, 1, 2), "oos_end": date(2024, 12, 31)},
]
IS_START = date(2020, 7, 1)

STRATEGIES = {
    "hybrid_20q": {"strategy_type": "magic_formula_hybrid", "top_n": 20, "rebalance_freq": "quarterly"},
    "ctrl_original": {"strategy_type": "magic_formula_original", "top_n": 20, "rebalance_freq": "monthly"},
    "ctrl_brazil": {"strategy_type": "magic_formula_brazil", "top_n": 20, "rebalance_freq": "monthly"},
}


def _cfg(start, end, params):
    return BacktestConfig(
        strategy_type=params["strategy_type"], start_date=start, end_date=end,
        rebalance_freq=params.get("rebalance_freq", "monthly"),
        top_n=params.get("top_n", 20), execution_lag_days=1,
        equal_weight=True, cost_model=BRAZIL_REALISTIC,
        initial_capital=1_000_000.0, benchmark="^BVSP", lot_size=100,
    )


def _returns(ec):
    vals = [p["value"] for p in ec]
    return [(vals[i] - vals[i-1]) / vals[i-1] for i in range(1, len(vals)) if vals[i-1] > 0]


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_results = {}

    with SessionLocal() as session:
        for split in SPLITS:
            label = split["label"]
            logger.info("=" * 60)
            logger.info("%s: IS %s→%s | OOS %s→%s", label, IS_START, split["is_end"], split["oos_start"], split["oos_end"])

            split_data = {}
            for strat_label, params in STRATEGIES.items():
                oos_cfg = _cfg(split["oos_start"], split["oos_end"], params)
                t0 = time.time()
                oos_r = run_backtest(session, oos_cfg)
                elapsed = time.time() - t0

                oos_ret = _returns(oos_r.equity_curve)
                oos_stats = compute_statistical_metrics(oos_ret, oos_r.metrics.get("sharpe", 0), n_trials=3) if len(oos_ret) >= 3 else {}

                trade_count = len(oos_r.trades)
                rebalance_count = len(oos_r.rebalance_dates)
                active = trade_count > 0

                split_data[strat_label] = {
                    **oos_r.metrics,
                    "trade_count": trade_count,
                    "rebalance_count": rebalance_count,
                    "active": active,
                    "psr": oos_stats.get("psr"),
                    "dsr": oos_stats.get("dsr"),
                }
                logger.info("  %s: Sharpe=%.4f CAGR=%.2f%% trades=%d rebal=%d active=%s (%.1fs)",
                            strat_label, oos_r.metrics.get("sharpe", 0), oos_r.metrics.get("cagr", 0)*100,
                            trade_count, rebalance_count, active, elapsed)

            all_results[label] = {
                "is_period": f"{IS_START} → {split['is_end']}",
                "oos_period": f"{split['oos_start']} → {split['oos_end']}",
                "results": split_data,
            }

    (RESULTS_DIR / "results.json").write_text(json.dumps(all_results, indent=2, default=str))

    # Report
    print(f"\n{'=' * 100}")
    print("WALK-FORWARD v2 — hybrid_20q (12-month OOS, quarterly rebalance)")
    print(f"{'=' * 100}")
    print(f"Expanding IS from {IS_START}, rolling 12-month OOS windows")
    print(f"Minimum 4 quarterly rebalances per OOS split")
    print()

    # Table 1: OOS metrics with trade count
    print("--- OOS METRICS BY SPLIT ---")
    print(f"{'Split':10s} {'OOS':25s} {'Strat':16s} {'Sharpe':>8s} {'CAGR':>8s} {'MaxDD':>8s} {'Trades':>7s} {'Rebal':>6s} {'Active':>7s}")
    print("-" * 100)
    for split in SPLITS:
        label = split["label"]
        oos_period = all_results[label]["oos_period"]
        for strat in STRATEGIES:
            d = all_results[label]["results"][strat]
            short = strat.replace("ctrl_", "").replace("hybrid_", "H_")
            sharpe = d.get("sharpe", 0)
            cagr = d.get("cagr", 0) * 100
            maxdd = d.get("max_drawdown", 0) * 100
            trades = d["trade_count"]
            rebal = d["rebalance_count"]
            active = "YES" if d["active"] else "NO"
            print(f"  {label:8s} {oos_period:25s} {short:16s} {sharpe:8.4f} {cagr:7.2f}% {maxdd:7.2f}% {trades:7d} {rebal:6d} {active:>7s}")
        print()

    # Table 2: Hybrid vs controls per split
    print("--- HYBRID_20Q vs CONTROLS ---")
    print(f"{'Split':10s} {'H_20q Sharpe':>12s} {'Ctrl_Orig':>12s} {'Ctrl_Braz':>12s} {'H wins?':>8s} {'H trades':>9s}")
    print("-" * 65)

    hybrid_wins_all = 0
    hybrid_wins_active = 0
    active_count = 0
    hybrid_sharpes_active = []

    for split in SPLITS:
        label = split["label"]
        sr = all_results[label]["results"]
        h = sr["hybrid_20q"]
        o = sr["ctrl_original"]
        b = sr["ctrl_brazil"]

        h_sharpe = h.get("sharpe", 0)
        o_sharpe = o.get("sharpe", 0)
        b_sharpe = b.get("sharpe", 0)
        h_trades = h["trade_count"]
        is_active = h["active"]

        wins = h_sharpe > o_sharpe and h_sharpe > b_sharpe
        if wins:
            hybrid_wins_all += 1
        if is_active:
            active_count += 1
            hybrid_sharpes_active.append(h_sharpe)
            if wins:
                hybrid_wins_active += 1

        print(f"  {label:8s} {h_sharpe:12.4f} {o_sharpe:12.4f} {b_sharpe:12.4f} {'YES' if wins else 'no':>8s} {h_trades:9d}")

    print()
    print(f"  All splits:    Hybrid wins {hybrid_wins_all}/{len(SPLITS)}")
    print(f"  Active splits: Hybrid wins {hybrid_wins_active}/{active_count} (splits with trades > 0)")
    if hybrid_sharpes_active:
        avg = sum(hybrid_sharpes_active) / len(hybrid_sharpes_active)
        print(f"  Avg OOS Sharpe (active only): {avg:.4f}")
        positive = sum(1 for s in hybrid_sharpes_active if s > 0)
        print(f"  Positive OOS Sharpe (active): {positive}/{len(hybrid_sharpes_active)}")
    print()

    # Excess return
    print("--- OOS EXCESS RETURN vs ^BVSP ---")
    print(f"{'Split':10s} {'H_20q':>12s} {'Ctrl_Orig':>12s} {'Ctrl_Braz':>12s}")
    print("-" * 50)
    for split in SPLITS:
        label = split["label"]
        sr = all_results[label]["results"]
        for strat_key in ["hybrid_20q", "ctrl_original", "ctrl_brazil"]:
            pass
        h_ex = sr["hybrid_20q"].get("excess_return", 0) * 100
        o_ex = sr["ctrl_original"].get("excess_return", 0) * 100
        b_ex = sr["ctrl_brazil"].get("excess_return", 0) * 100
        print(f"  {label:8s} {h_ex:11.2f}% {o_ex:11.2f}% {b_ex:11.2f}%")
    print()

    # Verdict
    print("--- VERDICT ---")
    if active_count == 0:
        print("  NO ACTIVE SPLITS — cannot assess robustness")
    elif active_count < len(SPLITS):
        inactive = len(SPLITS) - active_count
        print(f"  {inactive}/{len(SPLITS)} splits inactive (no trades) — noted as limitation")

    if hybrid_sharpes_active:
        avg = sum(hybrid_sharpes_active) / len(hybrid_sharpes_active)
        positive = sum(1 for s in hybrid_sharpes_active if s > 0)

        if positive == active_count and avg > 0.3:
            print(f"  hybrid_20q: ALL active splits positive, avg Sharpe {avg:.4f} — STRONG candidate for promotion review")
        elif positive > active_count / 2:
            print(f"  hybrid_20q: {positive}/{active_count} active splits positive, avg Sharpe {avg:.4f} — promising but mixed")
        else:
            print(f"  hybrid_20q: only {positive}/{active_count} active splits positive — signal weak")

    print()
    print(f"Artifacts: {RESULTS_DIR}")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
