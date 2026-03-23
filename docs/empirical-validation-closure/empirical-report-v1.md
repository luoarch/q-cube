# Q3 Empirical Report v1 — Canonical Experiment

## Experiment Metadata

| Field | Value |
|-------|-------|
| Experiment ID | `6f9cbc8a521cba9a` |
| Git hash | `38f8262b4161` |
| Strategy | `magic_formula_brazil` |
| Period | 2024-04-01 → 2025-12-31 |
| Rebalance | Quarterly (first business day) |
| Top N | 20 |
| Weighting | Equal weight |
| Cost model | BRAZIL_REALISTIC (5bps proportional + 10bps slippage) |
| Initial capital | R$ 1,000,000 |
| Universe | Frozen policy v1 (521 CORE_ELIGIBLE), frozen 2026-03-20 |
| Benchmark | ^BVSP (Ibovespa, price index, NOT total return) |

---

## Reproducibility Manifest

- `experiment_id`: SHA-256 hash of parameters → `6f9cbc8a521cba9a`
- `git_hash`: `38f8262b4161`
- `universe_policy_version`: v1
- `frozen_policy_date`: 2026-03-20
- `benchmark_definition`: ^BVSP price index via yfinance adjusted close
- Source: CVM filings (DFP/ITR 2024), Yahoo market snapshots (2023-2026)
- Artifacts: `results/6f9cbc8a521cba9a/` (manifest, metrics, equity_curve, trades, benchmark_curve, statistical_metrics)

---

## Performance Metrics

| Metric | Value |
|--------|------:|
| CAGR | **-7.88%** |
| Volatility (ann.) | 18.06% |
| Sharpe ratio | **-1.07** |
| Sortino ratio | -1.03 |
| Max drawdown | 13.30% |
| Max DD duration | 92 days |
| Turnover (avg) | 47.30% |
| Hit rate | 0.00% |
| Total costs | R$ 2,524 |

---

## Benchmark Comparison

| Measure | Strategy | Benchmark (^BVSP) |
|---------|:--------:|:-----------------:|
| Final value | R$ 884,119 | R$ 1,268,801 |
| Total return | -11.59% | +26.88% |
| Excess return | **-38.47%** | — |
| Tracking error | 10.11% | — |
| Information ratio | **-1.94** | — |

**Benchmark limitation**: ^BVSP is a price index (no dividend reinvestment). This creates a ~3-5% annual conservative bias against the strategy. Even accounting for this, the strategy materially underperformed.

---

## Statistical Metrics

| Metric | Value | Interpretation |
|--------|------:|---------------|
| PSR (vs Sharpe=0) | 0.00 | 0% probability that true Sharpe > 0 |
| DSR (3 trials) | 0.00 | After multiple-testing correction: no evidence of skill |
| Skewness | -2.51 | Strong negative skew (tail risk) |
| Excess kurtosis | 6.51 | Heavy tails |

---

## Data Constraints

This experiment ran under severe data constraints:

1. **Only 2024 filings available** — no historical filings for IS/OOS split
2. **Market snapshots sparse after Q1 2025** — only 3 of 7 rebalances had price data
3. **4 rebalances had 0 market prices** — strategy couldn't trade in those periods
4. **Only 36 trades executed** across the entire backtest

These constraints make the results **unreliable as performance evidence** but **valid as pipeline proof**.

---

## Validation Stack (partial)

| Module | Executed? | Result |
|--------|:---------:|--------|
| Core backtest | Yes | 7 rebalances, 36 trades, R$884K final |
| Benchmark comparison | Yes | -38.47% excess return |
| PSR/DSR | Yes | Both 0.00 (no evidence of skill) |
| OOS report | Not feasible | Only 1 year of filings — no IS/OOS split |
| Sensitivity | Not feasible | Would require multiple runs on same period |
| Reality Check | Not feasible | Needs ≥3 strategy runs to compare |
| Walk-forward | Not feasible | Needs multi-year IS data |
| Promotion check | Not feasible | Requires OOS report as input |

**Note**: OOS, sensitivity, Reality Check, walk-forward, and promotion could not be executed because only 2024 filing data is available. These require multi-year historical data that hasn't been ingested yet.

---

## What This Experiment Proves

1. **The empirical pipeline runs end-to-end** — engine → PIT data → ranking → trades → metrics → benchmark → statistical metrics → report
2. **The backtest engine produces results with real data** — 355 PIT-visible issuers, 287 priced tickers, actual trades at B3 lot sizes
3. **Costs are applied** — R$2,524 total (BRAZIL_REALISTIC model)
4. **Benchmark comparison is computable** — Ibovespa curve fetched, excess return and information ratio computed
5. **Statistical metrics are computable** — PSR/DSR produced from actual return series
6. **Results are reproducible** — manifest with experiment_id, git hash, full config
7. **Universe alignment works** — frozen policy universe (521 CORE_ELIGIBLE) used instead of legacy EXCLUDED_SECTORS

---

## What This Experiment Does NOT Prove

1. **Persistent alpha** — period too short, data too sparse (4/7 rebalances had no prices)
2. **Statistical robustness** — single strategy/config, no variants tested
3. **Historical universe accuracy** — frozen policy, not PIT historical
4. **Benchmark fairness** — price-only index (no dividend reinvestment)
5. **Strategy promotion readiness** — couldn't run OOS/sensitivity/promotion (insufficient data)
6. **Walk-forward or Reality Check validity** — couldn't execute (need multi-year filings)
7. **The strategy itself** — negative Sharpe is expected given data constraints, not a verdict on the method

---

## Recommendations

### To produce meaningful empirical evidence, Q3 needs:

1. **Multi-year CVM filing ingestion** — at minimum 2020-2024 DFP/ITR filings for a 4-year IS + 1-year OOS
2. **Historical market snapshot backfill** — daily prices for the same period
3. **Re-run with adequate data** — then OOS, sensitivity, Reality Check, walk-forward, and promotion become feasible

### This experiment serves as:

- **Proof that the pipeline works**
- **Template for future experiments** (script, manifest, artifact structure)
- **Honest baseline** (negative result documented, not hidden)
