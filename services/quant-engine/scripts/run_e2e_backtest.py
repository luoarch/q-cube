#!/usr/bin/env python3
"""End-to-end backtest: backtest -> OOS -> sensitivity -> contribution -> Reality Check -> promotion -> persist."""

from __future__ import annotations

import json
import sys
from datetime import date
from pprint import pprint

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# ---- Backtest ----
from q3_quant_engine.backtest.engine import BacktestConfig, run_backtest
from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC
from q3_quant_engine.backtest.metrics import compute_returns
from q3_quant_engine.backtest.statistical import compute_statistical_metrics

# ---- Reports ----
from q3_quant_engine.backtest.reports import (
    generate_oos_report,
    generate_sensitivity_report,
)

# ---- Contribution ----
from q3_quant_engine.backtest.contribution import generate_contribution_report

# ---- Reality Check ----
from q3_quant_engine.backtest.reality_check import (
    StrategyReturns,
    run_reality_check,
)

# ---- Promotion ----
from q3_quant_engine.backtest.promotion import run_promotion_check

# ---- Manifest + Persistence ----
from q3_quant_engine.backtest.manifest import build_manifest
from q3_quant_engine.backtest.persistence import persist_backtest


DATABASE_URL = "postgresql://127.0.0.1:5432/q3"


def main():
    engine = create_engine(DATABASE_URL)

    config = BacktestConfig(
        strategy_type="magic_formula_brazil",
        start_date=date(2025, 12, 15),
        end_date=date(2026, 3, 1),
        rebalance_freq="monthly",
        execution_lag_days=1,
        top_n=20,
        equal_weight=True,
        cost_model=BRAZIL_REALISTIC,
        initial_capital=1_000_000.0,
        benchmark="^BVSP",
    )

    print("=" * 70)
    print("Q3 RESEARCH VALIDATION — END-TO-END BACKTEST")
    print("=" * 70)
    print(f"Strategy:    {config.strategy_type}")
    print(f"Period:      {config.start_date} → {config.end_date}")
    print(f"Rebalance:   {config.rebalance_freq}")
    print(f"Top N:       {config.top_n}")
    print(f"Exec lag:    {config.execution_lag_days} day(s)")
    print(f"Cost model:  proportional={config.cost_model.proportional_cost}, slippage={config.cost_model.slippage_bps}bps")
    print(f"Benchmark:   {config.benchmark}")
    print()

    # ===== 1. FULL BACKTEST =====
    print("-" * 70)
    print("1. FULL BACKTEST")
    print("-" * 70)

    with Session(engine) as session:
        result = run_backtest(session, config)

    print(f"Rebalance dates:  {len(result.rebalance_dates)}")
    print(f"Total trades:     {len(result.trades)}")
    print(f"Equity curve pts: {len(result.equity_curve)}")
    print()
    print("METRICS:")
    for k, v in sorted(result.metrics.items()):
        if isinstance(v, float):
            print(f"  {k:30s} {v:>12.6f}")
        else:
            print(f"  {k:30s} {v!s:>12}")
    print()

    # Print equity curve
    print("EQUITY CURVE:")
    for pt in result.equity_curve:
        print(f"  {pt['date']}  R$ {pt['value']:>14,.2f}")
    print()

    # ===== 2. OOS REPORT =====
    print("-" * 70)
    print("2. OOS REPORT (IS: Dec 2025 - Jan 2026, OOS: Feb - Mar 2026)")
    print("-" * 70)

    with Session(engine) as session:
        oos_report = generate_oos_report(
            session, config,
            is_end=date(2026, 1, 31),
            oos_start=date(2026, 2, 1),
            n_trials=1,
        )

    print(f"Fragile:          {oos_report.fragile}")
    print(f"IS period:        {oos_report.is_period}")
    print(f"OOS period:       {oos_report.oos_period}")
    print()
    print("IS metrics:")
    for k, v in sorted(oos_report.is_metrics.items()):
        if isinstance(v, float):
            print(f"  {k:30s} {v:>12.6f}")
    print()
    print("OOS metrics:")
    for k, v in sorted(oos_report.oos_metrics.items()):
        if isinstance(v, float):
            print(f"  {k:30s} {v:>12.6f}")
    print()
    print("Degradation (IS → OOS):")
    for k, v in sorted(oos_report.degradation.items()):
        pct = v * 100
        marker = " !!!" if abs(v) > 0.50 else ""
        print(f"  {k:30s} {pct:>+8.1f}%{marker}")
    print()
    print("Statistical (OOS):")
    for k, v in sorted(oos_report.oos_statistical.items()):
        if isinstance(v, (int, float)):
            print(f"  {k:30s} {v:>12.6f}")
    print()

    # ===== 3. SENSITIVITY REPORT =====
    print("-" * 70)
    print("3. SENSITIVITY REPORT")
    print("-" * 70)

    with Session(engine) as session:
        sens_report = generate_sensitivity_report(session, config)

    print(f"Robust:           {sens_report.robust}")
    print(f"Base Sharpe:      {sens_report.base_metrics.get('sharpe', 0):.4f}")
    print(f"Base CAGR:        {sens_report.base_metrics.get('cagr', 0):.6f}")
    print()
    print(f"{'Param':<25s} {'Value':<15s} {'Sharpe':>10s} {'ΔSharpe':>10s} {'ΔCAGR':>12s}")
    print("-" * 75)
    for v in sens_report.variations:
        print(f"  {v['param']:<23s} {str(v['value']):<15s} {v['metrics'].get('sharpe', 0):>10.4f} {v['delta_sharpe']:>+10.4f} {v['delta_cagr']:>+12.6f}")
    print()

    # ===== 4. REALITY CHECK =====
    print("-" * 70)
    print("4. REALITY CHECK (White 2000)")
    print("-" * 70)

    # Simulate 3 strategy variants using different top_n
    strategy_returns = []
    for top_n in (10, 20, 30):
        v_config = BacktestConfig(
            strategy_type="magic_formula_brazil",
            start_date=config.start_date,
            end_date=config.end_date,
            rebalance_freq="monthly",
            top_n=top_n,
            cost_model=BRAZIL_REALISTIC,
        )
        with Session(engine) as session:
            v_result = run_backtest(session, v_config)
        returns = compute_returns(v_result.equity_curve)
        strategy_returns.append(StrategyReturns(
            name=f"magic_formula_top{top_n}",
            returns=returns,
        ))

    rc_report = run_reality_check(strategy_returns, n_bootstrap=500, seed=42)
    print(f"N strategies:     {rc_report.n_strategies}")
    print(f"Best strategy:    {rc_report.best_strategy}")
    print(f"Best Sharpe:      {rc_report.best_sharpe:.4f}")
    print(f"P-value:          {rc_report.p_value:.4f}")
    print(f"Reject null:      {rc_report.reject_null}")
    print(f"Significance:     {rc_report.significance_level}")
    print()
    print("Hypothesis registry:")
    for h in rc_report.hypothesis_registry:
        print(f"  {h['name']:<30s} Sharpe={h['sharpe']:>8.4f}  n={h['n_returns']}")
    print()

    # ===== 5. PROMOTION CHECK =====
    print("-" * 70)
    print("5. PROMOTION CHECK")
    print("-" * 70)

    promo = run_promotion_check(
        strategy="magic_formula_brazil",
        variant="base",
        oos_metrics=oos_report.oos_metrics,
        oos_statistical=oos_report.oos_statistical,
        degradation=oos_report.degradation,
        sensitivity_robust=sens_report.robust,
        subperiod_fragile=oos_report.fragile,
        manifest_valid=True,
        pit_validated=True,
        costs_applied=True,
        oos_months=1,  # Feb - Mar 2026
    )

    print(f"PROMOTED:         {'YES' if promo.promoted else 'NO'}")
    print(f"Blocking checks:  {promo.blocking_checks or 'none'}")
    print()
    print("Checks:")
    for c in promo.checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"  [{status}] {c.name:<30s} {c.detail}")
    print()
    print("Summary:")
    for k, v in sorted(promo.summary.items()):
        print(f"  {k:<25s} {v}")
    print()

    # ===== 6. RESEARCH MANIFEST =====
    print("-" * 70)
    print("6. RESEARCH MANIFEST")
    print("-" * 70)

    manifest = build_manifest(
        config=config,
        variant="base",
        n_trials=len(strategy_returns),
        metrics_summary=result.metrics,
        statistical_metrics=oos_report.oos_statistical,
    )
    print(f"Experiment ID:    {manifest.experiment_id}")
    print(f"Commit hash:      {manifest.commit_hash}")
    print(f"Content hash:     {manifest.content_hash()}")
    print(f"Formula version:  {manifest.formula_version}")
    print(f"N trials:         {manifest.n_trials}")
    print()

    # ===== 7. MARGINAL CONTRIBUTION =====
    print("-" * 70)
    print("7. MARGINAL CONTRIBUTION ANALYSIS")
    print("-" * 70)

    with Session(engine) as session:
        contrib_report = generate_contribution_report(session, config)

    print(f"Base variant:     {contrib_report.base_variant}")
    print(f"All positive:     {contrib_report.all_positive}")
    print()
    print(f"{'Variant':<20s} {'Sharpe':>10s} {'CAGR':>12s} {'MaxDD':>10s}")
    print("-" * 55)
    for v in contrib_report.variants:
        print(f"  {v.variant:<18s} {v.metrics.get('sharpe', 0):>10.4f} {v.metrics.get('cagr', 0):>12.6f} {v.metrics.get('max_drawdown', 0):>10.6f}")
    print()
    print("Marginal contributions (vs core_only):")
    for c in contrib_report.contributions:
        status = "+" if c.positive else "-"
        print(f"  [{status}] {c.component:<18s} ΔSharpe={c.delta_sharpe:>+8.4f}  ΔCAGR={c.delta_cagr:>+10.6f}  ΔMaxDD={c.delta_max_drawdown:>+10.6f}  ΔTurnover={c.delta_turnover:>+8.4f}")
    print()

    # ===== 8. PERSIST ARTIFACTS =====
    print("-" * 70)
    print("8. PERSIST ARTIFACTS")
    print("-" * 70)

    out_dir = persist_backtest(result, manifest)
    print(f"Artifacts saved to: {out_dir}")
    import os
    for f in sorted(os.listdir(out_dir)):
        size = os.path.getsize(os.path.join(out_dir, f))
        print(f"  {f:<25s} {size:>8,} bytes")
    print()

    print("=" * 70)
    print("END-TO-END VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
