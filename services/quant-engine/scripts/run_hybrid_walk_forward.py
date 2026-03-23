"""Walk-Forward Multi-Split OOS for hybrid_20q.

Tests hybrid_20q across multiple IS/OOS splits to determine if
the 2024 OOS survival was persistent or lucky.

Controls: ctrl_original_20m, ctrl_brazil_20m (frozen, rejected).

Splits (expanding IS, rolling 6-month OOS):
  Split 1: IS 2020-H2→2022-H1 | OOS 2022-H2
  Split 2: IS 2020-H2→2022    | OOS 2023-H1
  Split 3: IS 2020-H2→2023-H1 | OOS 2023-H2
  Split 4: IS 2020-H2→2023    | OOS 2024-H1
  Split 5: IS 2020-H2→2024-H1 | OOS 2024-H2

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/run_hybrid_walk_forward.py
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
logger = logging.getLogger("walk_forward")

RESULTS_DIR = Path("results/hybrid_walk_forward")

SPLITS = [
    {"label": "Split 1", "is_start": date(2020, 7, 1), "is_end": date(2022, 6, 30), "oos_start": date(2022, 7, 1), "oos_end": date(2022, 12, 31)},
    {"label": "Split 2", "is_start": date(2020, 7, 1), "is_end": date(2022, 12, 31), "oos_start": date(2023, 1, 2), "oos_end": date(2023, 6, 30)},
    {"label": "Split 3", "is_start": date(2020, 7, 1), "is_end": date(2023, 6, 30), "oos_start": date(2023, 7, 3), "oos_end": date(2023, 12, 31)},
    {"label": "Split 4", "is_start": date(2020, 7, 1), "is_end": date(2023, 12, 31), "oos_start": date(2024, 1, 2), "oos_end": date(2024, 6, 28)},
    {"label": "Split 5", "is_start": date(2020, 7, 1), "is_end": date(2024, 6, 28), "oos_start": date(2024, 7, 1), "oos_end": date(2024, 12, 31)},
]

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
            logger.info("%s: IS %s→%s | OOS %s→%s", label, split["is_start"], split["is_end"], split["oos_start"], split["oos_end"])

            split_results = {}
            for strat_label, params in STRATEGIES.items():
                # OOS only (IS is for context but we focus on OOS performance)
                oos_cfg = _cfg(split["oos_start"], split["oos_end"], params)
                t0 = time.time()
                oos_r = run_backtest(session, oos_cfg)
                elapsed = time.time() - t0

                oos_ret = _returns(oos_r.equity_curve)
                oos_stats = compute_statistical_metrics(oos_ret, oos_r.metrics.get("sharpe", 0), n_trials=3) if len(oos_ret) >= 3 else {}

                split_results[strat_label] = {
                    **oos_r.metrics,
                    "trades": len(oos_r.trades),
                    "rebalances": len(oos_r.rebalance_dates),
                    "psr": oos_stats.get("psr", None),
                    "dsr": oos_stats.get("dsr", None),
                }
                logger.info("  %s OOS Sharpe=%.4f CAGR=%.2f%% (%.1fs)",
                            strat_label, oos_r.metrics.get("sharpe", 0), oos_r.metrics.get("cagr", 0) * 100, elapsed)

            all_results[label] = {
                "is_period": f"{split['is_start']} → {split['is_end']}",
                "oos_period": f"{split['oos_start']} → {split['oos_end']}",
                "results": split_results,
            }

    # Save
    (RESULTS_DIR / "results.json").write_text(json.dumps(all_results, indent=2, default=str))

    # Report
    print(f"\n{'=' * 100}")
    print("WALK-FORWARD MULTI-SPLIT: hybrid_20q vs controls")
    print(f"{'=' * 100}")
    print("Expanding IS from 2020-H2, rolling 6-month OOS windows")
    print()

    # Table: OOS Sharpe per split
    print("--- OOS SHARPE BY SPLIT ---")
    header = f"{'Split':10s} {'OOS Period':25s} {'hybrid_20q':>12s} {'ctrl_orig':>12s} {'ctrl_brazil':>12s} {'hybrid wins':>12s}"
    print(header)
    print("-" * 85)

    hybrid_wins = 0
    hybrid_positive = 0
    hybrid_sharpes = []

    for split in SPLITS:
        label = split["label"]
        sr = all_results[label]["results"]
        h = sr["hybrid_20q"].get("sharpe", 0)
        o = sr["ctrl_original"].get("sharpe", 0)
        b = sr["ctrl_brazil"].get("sharpe", 0)
        hybrid_sharpes.append(h)
        wins = h > o and h > b
        if wins:
            hybrid_wins += 1
        if h > 0:
            hybrid_positive += 1
        oos = all_results[label]["oos_period"]
        print(f"  {label:8s} {oos:25s} {h:12.4f} {o:12.4f} {b:12.4f} {'YES' if wins else 'no':>12s}")

    print()
    print(f"  Hybrid wins: {hybrid_wins}/{len(SPLITS)} splits")
    print(f"  Hybrid OOS positive: {hybrid_positive}/{len(SPLITS)} splits")
    print(f"  Hybrid avg OOS Sharpe: {sum(hybrid_sharpes)/len(hybrid_sharpes):.4f}")
    print()

    # Table: OOS CAGR per split
    print("--- OOS CAGR BY SPLIT ---")
    header = f"{'Split':10s} {'hybrid_20q':>12s} {'ctrl_orig':>12s} {'ctrl_brazil':>12s}"
    print(header)
    print("-" * 50)
    for split in SPLITS:
        label = split["label"]
        sr = all_results[label]["results"]
        print(f"  {label:8s} {sr['hybrid_20q'].get('cagr', 0)*100:11.2f}% {sr['ctrl_original'].get('cagr', 0)*100:11.2f}% {sr['ctrl_brazil'].get('cagr', 0)*100:11.2f}%")
    print()

    # Table: OOS excess return per split
    print("--- OOS EXCESS RETURN vs ^BVSP BY SPLIT ---")
    header = f"{'Split':10s} {'hybrid_20q':>12s} {'ctrl_orig':>12s} {'ctrl_brazil':>12s}"
    print(header)
    print("-" * 50)
    for split in SPLITS:
        label = split["label"]
        sr = all_results[label]["results"]
        print(f"  {label:8s} {sr['hybrid_20q'].get('excess_return', 0)*100:11.2f}% {sr['ctrl_original'].get('excess_return', 0)*100:11.2f}% {sr['ctrl_brazil'].get('excess_return', 0)*100:11.2f}%")
    print()

    # Verdict
    print("--- VERDICT ---")
    if hybrid_wins == len(SPLITS):
        print("  hybrid_20q WINS ALL SPLITS — strong persistence signal")
    elif hybrid_wins >= len(SPLITS) * 0.8:
        print(f"  hybrid_20q wins {hybrid_wins}/{len(SPLITS)} — good persistence")
    elif hybrid_wins >= len(SPLITS) * 0.6:
        print(f"  hybrid_20q wins {hybrid_wins}/{len(SPLITS)} — moderate persistence")
    else:
        print(f"  hybrid_20q wins {hybrid_wins}/{len(SPLITS)} — weak/no persistence")

    if hybrid_positive >= len(SPLITS) * 0.6:
        print(f"  hybrid_20q OOS positive in {hybrid_positive}/{len(SPLITS)} — signal present")
    else:
        print(f"  hybrid_20q OOS positive in {hybrid_positive}/{len(SPLITS)} — signal weak")

    avg_sharpe = sum(hybrid_sharpes) / len(hybrid_sharpes)
    if avg_sharpe > 0.3:
        print(f"  Avg OOS Sharpe {avg_sharpe:.4f} — promotion-grade")
    elif avg_sharpe > 0:
        print(f"  Avg OOS Sharpe {avg_sharpe:.4f} — positive but below promotion threshold")
    else:
        print(f"  Avg OOS Sharpe {avg_sharpe:.4f} — not promotable")

    print()
    print(f"Artifacts: {RESULTS_DIR}")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    main()
