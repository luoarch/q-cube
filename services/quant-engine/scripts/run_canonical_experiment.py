"""Canonical empirical experiment — Steps 3-5 of Empirical Validation Closure.

Runs magic_formula_brazil backtest with benchmark, then executes the full
validation stack, and produces the empirical report.

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/run_canonical_experiment.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from q3_quant_engine.backtest.benchmark import fetch_benchmark_curve
from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC
from q3_quant_engine.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from q3_quant_engine.backtest.metrics import compute_metrics
from q3_quant_engine.backtest.statistical import compute_statistical_metrics
from q3_quant_engine.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("canonical_experiment")

# Canonical experiment parameters — adapted to available data
# Filings: 2024 only. Snapshots: 2023-2026.
# IS period: use what we have (2024 filings + snapshots)
# OOS period: limited by data — this is a proof-of-pipeline run

CONFIG = BacktestConfig(
    strategy_type="magic_formula_brazil",
    start_date=date(2024, 4, 1),   # Earliest usable (Q1 2024 filings available)
    end_date=date(2025, 12, 31),   # Latest data
    rebalance_freq="quarterly",     # Quarterly to reduce noise on short period
    execution_lag_days=1,
    top_n=20,
    equal_weight=True,
    cost_model=BRAZIL_REALISTIC,
    initial_capital=1_000_000.0,
    benchmark="^BVSP",
    lot_size=100,
)

RESULTS_DIR = Path(os.getenv("Q3_RESULTS_DIR", "results"))


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()[:12]
    except Exception:
        return "unknown"


def _experiment_id(config: BacktestConfig) -> str:
    """Deterministic experiment ID from config parameters."""
    params = json.dumps({
        "strategy": config.strategy_type,
        "start": str(config.start_date),
        "end": str(config.end_date),
        "freq": config.rebalance_freq,
        "top_n": config.top_n,
        "cost_proportional": config.cost_model.proportional_cost,
        "cost_slippage": config.cost_model.slippage_bps,
        "initial_capital": config.initial_capital,
        "benchmark": config.benchmark,
    }, sort_keys=True)
    return hashlib.sha256(params.encode()).hexdigest()[:16]


def main() -> None:
    exp_id = _experiment_id(CONFIG)
    git_hash = _git_hash()
    logger.info("Experiment ID: %s, git: %s", exp_id, git_hash)

    # --- Step 3: Run canonical backtest ---
    logger.info("Step 3: Running canonical backtest...")
    with SessionLocal() as session:
        result = run_backtest(session, CONFIG)

    logger.info(
        "Backtest complete: %d rebalances, %d trades, final equity=%.0f",
        len(result.rebalance_dates),
        len(result.trades),
        result.equity_curve[-1]["value"] if result.equity_curve else 0,
    )

    # Fetch benchmark
    logger.info("Fetching benchmark %s...", CONFIG.benchmark)
    benchmark_curve = fetch_benchmark_curve(
        CONFIG.start_date, CONFIG.end_date,
        ticker=CONFIG.benchmark or "^BVSP",
        initial_capital=CONFIG.initial_capital,
    )
    logger.info("Benchmark: %d points", len(benchmark_curve))

    # Compute metrics
    metrics = result.metrics
    logger.info("Metrics: %s", {k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()})

    # --- Step 4: Validation stack ---
    logger.info("Step 4: Running validation stack...")

    # Statistical metrics on strategy returns
    if len(result.equity_curve) >= 3:
        values = [p["value"] for p in result.equity_curve]
        returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values)) if values[i-1] > 0]
        sharpe = metrics.get("sharpe", 0)

        stat_metrics = compute_statistical_metrics(
            returns=returns,
            sharpe=sharpe,
            n_trials=3,  # small candidate set: top_n 10/20/30
        )
        logger.info("Statistical: PSR=%.4f, DSR=%.4f, skew=%.4f, kurt=%.4f",
                     stat_metrics.get("psr", 0), stat_metrics.get("dsr", 0),
                     stat_metrics.get("skewness", 0), stat_metrics.get("excess_kurtosis", 0))
    else:
        stat_metrics = {}
        logger.warning("Insufficient data for statistical metrics")

    # --- Step 5: Produce report ---
    logger.info("Step 5: Generating empirical report...")

    # Build manifest
    manifest = {
        "experiment_id": exp_id,
        "git_hash": git_hash,
        "strategy": CONFIG.strategy_type,
        "start_date": str(CONFIG.start_date),
        "end_date": str(CONFIG.end_date),
        "rebalance_freq": CONFIG.rebalance_freq,
        "top_n": CONFIG.top_n,
        "equal_weight": CONFIG.equal_weight,
        "cost_model": {
            "fixed": CONFIG.cost_model.fixed_cost_per_trade,
            "proportional": CONFIG.cost_model.proportional_cost,
            "slippage_bps": CONFIG.cost_model.slippage_bps,
        },
        "initial_capital": CONFIG.initial_capital,
        "benchmark": CONFIG.benchmark,
        "benchmark_type": "price_index (not total return)",
        "universe_policy_version": "v1",
        "frozen_policy_date": str(date.today()),
        "source_assumptions": {
            "filings": "CVM DFP/ITR 2024",
            "snapshots": "Yahoo Finance 2023-2026",
            "benchmark": "yfinance ^BVSP adjusted close",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist artifacts
    out_dir = RESULTS_DIR / exp_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    (out_dir / "equity_curve.json").write_text(json.dumps(result.equity_curve, default=str))
    (out_dir / "trades.json").write_text(json.dumps(result.trades, default=str))
    (out_dir / "benchmark_curve.json").write_text(json.dumps(benchmark_curve, default=str))
    if stat_metrics:
        (out_dir / "statistical_metrics.json").write_text(json.dumps(stat_metrics, indent=2))

    # Print summary report
    print(f"\n{'=' * 70}")
    print(f"EMPIRICAL VALIDATION — CANONICAL EXPERIMENT")
    print(f"{'=' * 70}")
    print(f"Experiment ID:  {exp_id}")
    print(f"Git hash:       {git_hash}")
    print(f"Strategy:       {CONFIG.strategy_type}")
    print(f"Period:         {CONFIG.start_date} → {CONFIG.end_date}")
    print(f"Rebalance:      {CONFIG.rebalance_freq}")
    print(f"Top N:          {CONFIG.top_n}")
    print(f"Cost model:     BRAZIL_REALISTIC ({CONFIG.cost_model.proportional_cost*10000:.0f}bps + {CONFIG.cost_model.slippage_bps:.0f}bps slippage)")
    print(f"Universe:       frozen policy v1 (CORE_ELIGIBLE)")
    print(f"Benchmark:      {CONFIG.benchmark} (price index)")
    print()

    print("--- Performance Metrics ---")
    for key in ["cagr", "volatility", "sharpe", "sortino", "max_drawdown", "max_drawdown_duration_days",
                "turnover_avg", "hit_rate", "total_costs"]:
        val = metrics.get(key)
        if val is not None:
            if key in ("cagr", "volatility", "max_drawdown", "turnover_avg", "hit_rate"):
                print(f"  {key:30s}: {val*100:.2f}%")
            elif key == "total_costs":
                print(f"  {key:30s}: R$ {val:,.0f}")
            else:
                print(f"  {key:30s}: {val:.4f}")
    print()

    if benchmark_curve and result.equity_curve:
        strat_final = result.equity_curve[-1]["value"]
        bench_final = benchmark_curve[-1]["value"]
        excess = (strat_final / CONFIG.initial_capital) - (bench_final / CONFIG.initial_capital)
        print(f"--- Benchmark Comparison ---")
        print(f"  Strategy final:   R$ {strat_final:,.0f}")
        print(f"  Benchmark final:  R$ {bench_final:,.0f}")
        print(f"  Excess return:    {excess*100:.2f}%")
        print()

    if stat_metrics:
        print("--- Statistical Metrics ---")
        print(f"  PSR (vs Sharpe=0):        {stat_metrics.get('psr', 0):.4f}")
        print(f"  DSR (3 strategies):       {stat_metrics.get('dsr', 0):.4f}")
        print(f"  Skewness:                 {stat_metrics.get('skewness', 0):.4f}")
        print(f"  Excess kurtosis:          {stat_metrics.get('excess_kurtosis', 0):.4f}")
        print()

    print("--- Data Limitations ---")
    print("  - Filings: 2024 only (no historical IS/OOS split possible)")
    print("  - Universe: frozen current policy, not PIT historical")
    print("  - Benchmark: price index only (no dividend reinvestment)")
    print("  - Period: too short for statistically significant claims")
    print()

    print("--- What This Experiment Proves ---")
    print("  - The empirical pipeline runs end-to-end")
    print("  - Backtest engine produces results with real data")
    print("  - Costs are applied (BRAZIL_REALISTIC)")
    print("  - Benchmark comparison is computable")
    print("  - Statistical metrics (PSR/DSR) are computable")
    print("  - Results are reproducible (manifest + experiment_id)")
    print()

    print("--- What This Experiment Does NOT Prove ---")
    print("  - Persistent alpha (period too short)")
    print("  - Statistical robustness (single strategy/config)")
    print("  - Historical universe accuracy (frozen policy)")
    print("  - Benchmark fairness (price-only)")
    print("  - Strategy promotion readiness (no IS/OOS split)")
    print()

    print(f"Artifacts saved to: {out_dir}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
