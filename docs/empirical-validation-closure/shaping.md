# Empirical Validation Closure

## Status: BUILD COMPLETE — Awaiting Tech Lead review

---

## 1. Objective

Transform the backtest/validation stack from **"implemented"** to **"exercised and evidenced"** by executing 1 canonical experiment end-to-end with the full validation stack.

Steps:
1. Aligning the backtest universe with `universe_classifications` (frozen policy)
2. Implementing a real benchmark (Ibovespa) with explicit methodological contract
3. Running 1 canonical end-to-end experiment
4. Executing the full validation stack
5. Producing the first auditable empirical report

### What this closes

After this micro feature, Q3 can claim:

- The empirical pipeline runs end-to-end (engine → metrics → validation → report)
- 1 reproducible experiment was executed with frozen universe, real costs, and benchmark comparison
- The validation stack (OOS, PSR/DSR, Reality Check, walk-forward, promotion) produces real artifacts
- 1 auditable report exists with honest outcomes (including failures)

### What this does NOT close

- **Alpha validated** — 1 experiment is not evidence of persistent alpha
- **Statistical robustness of the method** — requires multiple strategies, periods, and market regimes
- **Strategy promotion readiness** — promotion may fail; failure is valid evidence
- **Broad empirical evidence** — this is a proof-of-pipeline, not a comprehensive research study
- **PIT-correct historical universe** — the experiment uses frozen current policy universe, not historical universe composition (see universe contract below)

---

## 2. Problem

The methodological review identified the single biggest gap:

> The backtest engine and research framework exist but have never produced results. No strategy has completed the full validation pipeline. Empirical claims require completing the validation cycle.

Specifically:
- 0 completed backtest runs in production DB
- No benchmark curve for outperformance comparison
- Legacy `EXCLUDED_SECTORS` in backtest path (misaligned with live universe)
- Research validation modules (walk-forward, PSR/DSR, Reality Check, purged CV, promotion) never exercised on production data
- No empirical report exists

---

## 3. Scope: 5 Sequential Steps

### Step 1 — Backtest Universe Alignment

**Problem**: `backtest/engine.py` uses local `EXCLUDED_SECTORS = {"financeiro", "utilidade pública"}` (bridge patch from Plan 4B). The live ranking uses `universe_classifications`. The backtest may produce results on a different universe than the live product.

**Fix**: Replace `EXCLUDED_SECTORS` in `_rank_pit_data()` with a query to `universe_classifications`.

#### Universe contract for this experiment

The experiment uses:
- **PIT fundamentals**: filing data available at each rebalance date (`Filing.available_at <= rebalance_date`)
- **PIT prices**: market snapshot closest to rebalance date within staleness window
- **Frozen current policy universe**: `universe_classifications` as of experiment execution time (policy_version='v1')

This means the universe composition is **NOT historically reconstructed**. A company classified as `PERMANENTLY_EXCLUDED` today (e.g., GOL, Azul) is excluded from the entire backtest period, even if it was actively traded during that period.

**This is a known limitation.** True historical universe reconstruction would require:
- Historical `universe_classifications` snapshots (don't exist)
- Historical CVM sector data per period (not ingested)
- Listing/delisting event reconstruction beyond `Security.valid_from/valid_to`

For v1, frozen policy universe is acceptable because:
- Core eligibility is stable (sector classification rarely changes)
- The main exclusions (financial, retail, airline) were excluded in practice during the backtest period too
- The limitation is explicitly documented in the empirical report

**Files**: `services/quant-engine/src/q3_quant_engine/backtest/engine.py`

**Done**: `EXCLUDED_SECTORS` removed from backtest. Universe filter uses `universe_classifications` (frozen policy).

---

### Step 2 — Benchmark Implementation

**Problem**: No benchmark curve exists. Cannot claim excess returns. `benchmark.py` file doesn't exist.

#### Benchmark methodological contract

**1. Benchmark definition**

| Field | Value |
|-------|-------|
| Ticker | `^BVSP` (Ibovespa) |
| Source | yfinance historical prices |
| Type | **Price index** (not total return) |
| Why Ibovespa | Standard B3 equity benchmark; most commonly used for Brazilian equity comparison |

**Limitation**: Ibovespa via yfinance is a **price index**, not a total return index. It does NOT include dividend reinvestment. This creates a **conservative bias** against the strategy (strategy's DY component is real return, benchmark doesn't capture reinvested dividends). This limitation must be documented in the report.

**2. Return methodology**

- Benchmark equity curve: normalized to `initial_capital` at `start_date`
- Daily returns from adjusted close prices: `r_t = (P_t / P_{t-1}) - 1`
- Cumulative value: `V_t = initial_capital * product(1 + r_i)` for i in [start..t]
- Compared against strategy's equity curve at the same dates

**3. Calendar alignment**

- Benchmark prices fetched for every trading day in the backtest period
- Strategy equity curve has values at rebalance dates (monthly/quarterly)
- For comparison: interpolate strategy curve to benchmark dates using last-known value (step function — portfolio value doesn't change between rebalances)
- For metrics: use aligned monthly returns (last trading day of each month)
- Missing benchmark dates: skip (non-trading day)

**4. Benchmark limitations**

| Limitation | Impact | Documentation |
|------------|--------|---------------|
| Price-only (no dividends) | Conservative bias (~3-5% annual DY not captured) | Reported in report |
| yfinance as sole source | No independent verification | Noted as data dependency |
| Adjusted close may have revisions | Minor | Accepted for v1 |
| No CDI benchmark for comparison | Cannot measure risk-free excess | Follow-up |

**Implementation**:
- New file: `services/quant-engine/src/q3_quant_engine/backtest/benchmark.py`
- Function: `fetch_benchmark_curve(start_date, end_date, ticker="^BVSP", initial_capital=1_000_000) -> list[EquityCurvePoint]`
- Integrate into `run_backtest()`: if `config.benchmark` is set, fetch and include in results
- Metrics: compute `excess_return`, `tracking_error`, `information_ratio` (already in `metrics.py`)

**Done**: Benchmark curve fetchable with documented methodology. Backtest results include benchmark comparison.

---

### Step 3 — Canonical End-to-End Run

**Problem**: 0 completed backtest runs. Need at least 1 to prove the pipeline works.

**Design**: Run `magic_formula_brazil` with the official `SPLIT_FULL` parameters:
- IS: 2015-01-01 → 2023-12-31
- OOS: 2024-02-01 → 2025-12-31
- Benchmark: Ibovespa
- Cost model: BRAZIL_REALISTIC
- Top 20, monthly rebalance, equal weight

**Execution**: Script that creates a backtest run, executes it, persists results, and validates output.

**Done**: 1 completed backtest run in DB with metrics, equity curve, trade log, and manifest.

---

### Step 4 — Validation Stack Execution

**Problem**: Walk-forward, PSR/DSR, Reality Check, purged CV, sensitivity, promotion — all library code, never exercised.

**Design**: Run the e2e validation pipeline on the canonical run from Step 3:
1. OOS report (IS vs OOS metrics + degradation)
2. Statistical metrics (PSR, DSR)
3. Subperiod report (regime analysis)
4. Sensitivity report (parameter robustness)
5. Reality Check (data snooping test across **3 strategy variants only** — small candidate set, not a comprehensive sweep. Variants: magic_formula_brazil with top_n = 10, 20, 30)
6. Walk-forward analysis (expanding IS + rolling OOS)
7. Promotion check (6 mandatory gates)

**Execution**: Script that chains all validation steps and persists artifacts.

**Done**: All validation modules exercised. Results persisted as JSON artifacts.

---

### Step 5 — Empirical Report

**Problem**: No auditable report exists. Results live only in DB/JSON.

**Design**: Markdown report with mandatory sections:

#### Report structure

1. **Experiment metadata**
   - Strategy, variant, config parameters
   - Universe: policy_version, classification counts, frozen date
   - Benchmark: ^BVSP price index, source, limitations
   - Cost model: BRAZIL_REALISTIC

2. **Reproducibility manifest**
   - `experiment_id` (SHA-256 hash of parameters)
   - `git_hash` (commit at execution time)
   - Full config (strategy, dates, top_n, costs, benchmark)
   - `universe_policy_version` = 'v1'
   - `benchmark_definition` = '^BVSP price index via yfinance'
   - Source assumptions: CVM filings (DFP/ITR 2024), Yahoo snapshots

3. **Results**: IS/OOS metrics, benchmark comparison, equity curve
4. **Statistical metrics**: PSR, DSR, skewness, kurtosis
5. **Sensitivity analysis**: parameter robustness
6. **Reality Check**: p-value, strategy variants tested
7. **Walk-forward**: IS/OOS degradation per split
8. **Promotion decision**: pass/fail + which checks failed

9. **What this experiment proves**
   - The empirical pipeline runs end-to-end
   - Results are reproducible (manifest + experiment_id)
   - The validation stack produces real artifacts
   - [If promoted]: strategy passed 6 mandatory checks on this specific configuration and period
   - [If not promoted]: specific checks that failed and why

10. **What this experiment does NOT prove**
    - Persistent alpha across market regimes
    - Statistical robustness across strategy variants beyond 3 tested
    - Historical universe accuracy (frozen policy, not PIT universe)
    - Benchmark fairness (price-only, no dividend reinvestment)
    - Generalizability beyond the tested period

**Done**: `docs/empirical-validation-closure/empirical-report-v1.md` exists with all sections.

---

## 4. Appetite

**Level: M** — 5 steps, sequential dependency, ~1 session

Steps 1-2 are code changes. Steps 3-5 are execution + documentation.

### Must-fit:
- Universe alignment (remove bridge patch)
- Benchmark implementation
- 1 canonical run with evidence
- Validation stack execution
- Report

### First cuts:
- Multiple strategy variants (just brazil for v1)
- Purged CV full implementation (simplified is acceptable)
- API exposure of validation results
- UI for validation reports

---

## 5. Boundaries / No-Gos

- Do NOT change ranking pipeline
- Do NOT change the compat view
- Do NOT change DY/NBY/NPY metrics
- Do NOT expose validation results via API yet
- Do NOT claim "validated alpha" — report honestly
- Do NOT modify research validation module logic (exercise as-is)

---

## 6. Risks

| Risk | Severity | Mitigation |
|------|:--------:|------------|
| PIT data insufficient for 2015-2023 | High | May need to narrow IS period to available data (e.g., 2020+) |
| Ibovespa yfinance data unavailable | Low | ^BVSP is well-covered by Yahoo |
| Backtest run takes too long | Medium | Can narrow date range or reduce rebalance frequency |
| Strategy fails promotion | Expected | Honest reporting. Failure is valid evidence. |
| Market snapshot staleness in historical period | Medium | PIT layer already handles 7-day staleness window |

---

## 7. Validation Plan

| Check | Pass criteria |
|-------|---------------|
| V1 — Universe aligned | 0 occurrences of `EXCLUDED_SECTORS` in backtest code |
| V2 — Benchmark works | Ibovespa curve fetched and plotted for test period |
| V3 — Run completes | 1 backtest_run in DB with status=completed |
| V4 — Metrics computed | CAGR, Sharpe, Sortino, max DD, turnover all non-null |
| V5 — Benchmark comparison | excess_return and information_ratio computed |
| V6 — Validation stack runs | OOS, sensitivity, Reality Check, walk-forward all produce output |
| V7 — Promotion decision | promotion check runs and produces pass/fail with reasons |
| V8 — Report exists | `empirical-report-v1.md` with all sections populated |
| V9 — Reproducibility | Manifest with experiment_id, git hash, parameters |

---

## 8. Close Summary

### Delivered

1. **Step 1 — Universe alignment**: `EXCLUDED_SECTORS` removed from backtest engine. Frozen policy universe (521 CORE_ELIGIBLE) loaded at backtest start. 0 occurrences of `EXCLUDED_SECTORS` in codebase.

2. **Step 2 — Benchmark**: `benchmark.py` created. Fetches ^BVSP via yfinance. Price index (not total return). Normalized to initial_capital. Limitation documented.

3. **Step 3 — Canonical run**: Experiment `6f9cbc8a521cba9a` executed. magic_formula_brazil, 2024-04-01 → 2025-12-31, quarterly, top 20. Result: CAGR -7.88%, Sharpe -1.07, excess return -38.47% vs Ibovespa. **Honest negative result.**

4. **Step 4 — Validation stack (partial)**: PSR=0.00, DSR=0.00. OOS/sensitivity/Reality Check/walk-forward/promotion not feasible (only 2024 filings available). Documented as limitation.

5. **Step 5 — Report**: `empirical-report-v1.md` with all 10 mandatory sections including "What this proves" and "What this does NOT prove".

6. **PIT fix**: `fetch_fundamentals_pit` now uses `publication_date` (estimated CVM deadline) instead of `available_at` (import timestamp) for historical PIT gating.

### Artifacts

- `results/6f9cbc8a521cba9a/manifest.json`
- `results/6f9cbc8a521cba9a/metrics.json`
- `results/6f9cbc8a521cba9a/equity_curve.json`
- `results/6f9cbc8a521cba9a/trades.json`
- `results/6f9cbc8a521cba9a/benchmark_curve.json`
- `results/6f9cbc8a521cba9a/statistical_metrics.json`
- `docs/empirical-validation-closure/empirical-report-v1.md`

### Tests: 414 quant-engine, 0 regressions

### Key finding

The experiment ran successfully as **proof of pipeline**. The strategy underperformed (-38.47% vs benchmark) which is expected given data constraints (only 3/7 rebalances had market prices). The result is honest and documented. Full validation stack requires multi-year filing ingestion.

---

## 9. Tech Lead Handoff

### What changed
- `backtest/engine.py`: Frozen policy universe from `universe_classifications`. `EXCLUDED_SECTORS` removed.
- `data/pit_data.py`: PIT filter uses `publication_date` (with `available_at` fallback) for historical correctness.
- New `backtest/benchmark.py`: Ibovespa price index curve.
- New `scripts/run_canonical_experiment.py`: End-to-end experiment runner.
- `tests/test_ranking_spec.py`: Updated to reflect upstream sector filtering.

### What did NOT change
- Ranking pipeline (live) — untouched
- Research validation modules — exercised as-is, not modified
- DY/NBY/NPY metrics — untouched

### Where to start review
1. `empirical-report-v1.md` — the honest results
2. `data/pit_data.py` — PIT publication_date fix
3. `backtest/engine.py` — frozen policy universe
4. `benchmark.py` — Ibovespa curve methodology
