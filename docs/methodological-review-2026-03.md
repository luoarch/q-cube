# Q3 Methodological Review — March 2026

## Purpose

This document audits the Q3 system across 6 axes to establish what is methodologically sound, what is claimed vs verified, and what the system can honestly represent to users and stakeholders.

---

## A. System Definition

### What Q3 is

A quantitative stock screening and ranking platform for the Brazilian market (B3), implementing Magic Formula variants with fundamental overlays, a global thesis layer, and a PIT-aware backtesting engine with a research-grade validation framework implemented, pending empirical exercise on production data.

### Architecture

- **Data sources**: CVM filings (DFP/ITR/FCA), Yahoo Finance (market snapshots), CVM `composicao_capital` (share counts)
- **Core strategies**: magic_formula_original, magic_formula_brazil, magic_formula_hybrid
- **Thesis layer**: Plan 2 — commodity/fragility scoring with AI-assisted rubrics
- **Payout yield**: Dual-trail (exact/vendor + free-source/CVM proxy)
- **Universe**: 741 issuers, 521 CORE_ELIGIBLE, 232 with primary security + metrics in compat view
- **Backtest**: PIT engine with research validation framework

### Current operational state

| Component | Status |
|-----------|--------|
| CVM filing ingestion | Operational (DFP 2024, ITR 2024) |
| Yahoo market snapshots | Operational (283/356 tickers covered) |
| Ranking pipeline | Operational (3 strategies, universe-filtered) |
| Plan 2 thesis | Operational (15 runs) |
| Backtest engine | Implemented, product-wired (API+UI), pending empirical exercise (0 completed runs) |
| Research validation | Implemented as library, unit-tested, not API-exposed, not empirically exercised |

---

## B. Core Strategies & Overlays

### Magic Formula Original (Greenblatt)

| Aspect | Status |
|--------|--------|
| Formula | EY + ROC combined rank — correct |
| Universe filter | Via compat view (CORE_ELIGIBLE only since Plan 4B) |
| Sector exclusion | Enforced by universe classification |
| Liquidity gates | None (original has no gates) |

### Magic Formula Brazil

| Aspect | Status |
|--------|--------|
| Formula | Same as original + B3 gates |
| Gates | Min avg daily volume R$1M, min market cap R$500M, EBIT > 0 |
| Sector exclusion | Via universe classification (replaced legacy `EXCLUDED_SECTORS`) |

### Magic Formula Hybrid

| Aspect | Status |
|--------|--------|
| Formula | 75% core (EY + ROC) + 25% quality overlay (debt/EBITDA + cash conversion) |
| Quality overlay | debt_to_ebitda rank (ascending) + cash_conversion rank (descending) |
| Graceful degradation | If no quality signals, final_score = core_score |

### Plan 2 — Global Thesis Layer

| Aspect | Status |
|--------|--------|
| Opportunity vector | Commodity affinity scoring (sector proxy v2) |
| Fragility vector | USD debt/import/revenue exposure |
| Rubrics | 48 manual + 246 AI-assisted (sector heuristic + LLM) |
| Buckets | A_DIRECT, B_INDIRECT, C_NEUTRAL, D_FRAGILE |
| Monitoring | 6 alert types, dashboard at `/thesis/monitoring` |

---

## C. Metrics Map

### Classification: Exact / Proxy / Heuristic / Gated

| Metric | Trail | Source | Type | Coverage (Core) |
|--------|-------|--------|------|:---------------:|
| `earnings_yield` | Exact | CVM filings + Yahoo mcap | Computed | 192/232 (82.8%) |
| `roic` | Exact | CVM filings | Computed | 232/232 (100%) |
| `dividend_yield` | Shared | CVM filings (TTM) + Yahoo mcap | Computed | 190/232 (81.9%) |
| `net_buyback_yield` | Exact | Yahoo shares_outstanding | Vendor-dependent | 180/232 (77.6%) |
| `net_payout_yield` | Exact | DY + NBY composition | Vendor-dependent | 179/232 (77.2%) |
| `nby_proxy_free` | Free-source | CVM composicao_capital | Proxy | 215/232 (92.7%) |
| `npy_proxy_free` | Free-source | DY + NBY_PROXY composition | Proxy | 180/232 (77.6%) |
| `debt_to_ebitda` | Exact | CVM filings | Computed | ~230/232 |
| `cash_conversion` | Exact | CVM filings | Computed | ~200/232 |

### Coverage gates (Plan 3A)

| Gate | Required | Actual | Status |
|------|:--------:|:------:|:------:|
| DY ≥ 70% | 70% | **81.9%** | **PASS** |
| NBY ≥ 80% (exact) | 80% | 77.6% | **FAIL** (-2.4pp) |
| NPY ≥ 60% | 60% | **77.2%** | **PASS** |

### Dual-trail contract

| Rule | Description |
|------|-------------|
| DY shared | Both trails use the same `dividend_yield` |
| NBY diverges | Exact: Yahoo. Free: CVM composicao_capital |
| NPY follows trail | `net_payout_yield` = DY + NBY exact. `npy_proxy_free` = DY + NBY proxy |
| No silent substitution | Consumer must explicitly choose trail |
| Provenance preserved | `inputs_snapshot` records source per metric |

### Zero-semantics rule

- `NULL` = unknown / not computable / insufficient evidence
- `0` = computed value, economically valid (e.g., company doesn't pay dividends)
- DY=0 when issuer has DFC coverage (≥3/4 quarters) but no distribution lines

---

## D. Claims & Evidence Map

| Claim | Evidence | Honest status |
|-------|----------|:-------------:|
| "Magic Formula ranking for B3" | 3 strategies implemented, universe-filtered | **Supportable** |
| "Sector-aware universe filtering" | 56 sectors mapped, 25 overrides, check constraints | **Supportable** |
| "Dual-trail payout yield" | Exact + free-source, API-exposed, UI side-by-side | **Supportable** |
| "Point-in-time backtest" | PIT data layer implemented, anti-survivorship | **Partially supportable** (see F) |
| "Research-grade validation" | Walk-forward, PSR/DSR, Reality Check, Purged CV | **Claimed, not yet verified** (see F) |
| "Promotion pipeline prevents overfitting" | 6 checks implemented | **Claimed, 0 strategies promoted** |
| "NBY coverage meets gate" | Exact: 77.6% (FAIL). Proxy: 92.7% | **Not supportable for exact** |
| "Scientifically validated alpha" | No completed backtest runs in production | **Not supportable** |

---

## E. Language Policy

### Terms that CAN be used

- "Quantitative screening tool"
- "Magic Formula implementation for B3"
- "CVM-sourced fundamentals"
- "Universe classification with audit trail"
- "Dual-trail metrics (exact + free-source proxy)"
- "Backtest engine with PIT data layer"

### Terms that CANNOT be used (yet)

- "Proven alpha" — no completed backtests with evidence
- "Statistically validated" — validation framework exists but hasn't produced results
- "Outperforms benchmark" — no benchmark curve implemented
- "Academically rigorous" — framework is research-grade but hasn't been exercised
- "NBY fully covered" — exact trail fails gate

### Terms that require qualification

- "Research-grade backtesting" → "Research-grade backtesting framework implemented; pending empirical validation"
- "Walk-forward validated" → "Walk-forward analysis implemented; not yet run against production data"
- "Multiple testing corrected" → "DSR correction implemented; no strategies have passed promotion"

---

## F. Backtesting & Empirical Validation Audit

### F.1 — Empirical Validation Stack: Implemented → Verified → Exposed → Claimable

| Component | Implemented | Unit-tested | Integration-verified | Exposed (API/UI) | Empirically exercised | Scientifically Claimable |
|-----------|:-----------:|:-----------:|:--------------------:|:----------------:|:---------------------:|:------------------------:|
| **Core backtest engine** | Yes (386 LOC) | Yes (7 tests) | No | Yes (API + UI) | **No** — 0 runs | **No** |
| **PIT data layer** | Yes (275 LOC) | No | No | Via engine | **No** | **No** |
| **Cost models** | Yes (23 LOC) | Yes (2 tests) | No | Via engine | **No** | Partial (formulas correct) |
| **Metrics (Sharpe, etc.)** | Yes (176 LOC) | No | No | Via engine | **No** | Partial (standard formulas) |
| **Walk-forward** | Yes (146 LOC) | Yes (3 tests) | No | **No** — library | **No** | **No** |
| **PSR/DSR** | Yes (155 LOC) | Yes (9 tests) | No | **No** — library | **No** | **No** |
| **White's Reality Check** | Yes (185 LOC) | Yes (12 tests) | No | **No** — library | **No** | **No** |
| **Purged temporal CV** | Yes (200 LOC) | Yes (8 tests) | No | **No** — library | **No** (simplified) | **No** |
| **OOS/Subperiod/Sensitivity** | Yes (366 LOC) | Yes (8 tests) | No | **No** — library | **No** | **No** |
| **Promotion pipeline** | Yes (165 LOC) | Yes (11 tests) | No | **No** — library | **No** — 0 promoted | **No** |
| **Marginal contribution** | Yes (106 LOC) | No | No | **No** — library | **No** | **No** |
| **Manifest/persistence** | Yes (215 LOC) | No | No | **No** — library | N/A | N/A |
| **Official splits** | Yes (95 LOC) | No | No | **No** — library | N/A | N/A |
| **Benchmark curve** | **No** | N/A | N/A | N/A | N/A | **No** |

### F.2 — Engine operational status

**Core engine**: Implemented with 3 strategies, monthly/quarterly rebalancing, B3 lot rounding, realistic cost models. The code is complete and the API/UI flow works (create → queue → worker → results → poll). However: **0 completed backtest runs in production DB.**

**PIT integrity**:
- `Filing.available_at` used for temporal gating — correct
- `Security.valid_from/valid_to` for survivorship — correct
- Market staleness window (7 days) — correct
- **Threat**: Backtest engine uses legacy `EXCLUDED_SECTORS` bridge patch instead of `universe_classifications`. This means the backtest universe may differ from the live ranking universe.

### F.3 — Research validation assessment

**What exists**: A comprehensive research validation framework with 6 modules (walk-forward, PSR/DSR, Reality Check, purged CV, reports, promotion). Total: ~2,200 LOC across modules + ~350 LOC of tests (60 unit tests).

**Mathematical correctness**: PSR/DSR formulas follow Bailey & Lopez de Prado (2014). White's test uses stationary bootstrap per Politis & Romano (1994). Purged CV follows Lopez de Prado (2018). Formulas are testable and tested.

**What's missing**:
1. **Zero empirical results** — no strategy has been run through the validation framework on production data
2. **No benchmark** — `benchmark.py` doesn't exist, no Ibovespa/CDI comparison curve
3. **Purged CV simplified** — uses longest train period, not union of all clean periods (documented in code)
4. **No integration tests against DB** — all tests use mock data or in-memory computation
5. **e2e script exists** (`run_e2e_backtest.py`) but unclear if it has ever been executed successfully against production

### F.4 — Threats to validity

| Threat | Severity | Mitigation |
|--------|:--------:|------------|
| 0 completed backtest runs | **High** | Must run before any empirical claim |
| No benchmark curve | **High** | Cannot claim excess returns without reference |
| Legacy universe in backtest | **Medium** | Bridge patch uses stale `EXCLUDED_SECTORS` instead of `universe_classifications` |
| Purged CV simplified | **Low** | Documented; conservative vs full implementation |
| PIT data not independently tested | **Medium** | Engine tests don't verify PIT correctness specifically |
| Research modules not API-exposed | **Medium** | Results can't be reproduced via product interface |

### F.5 — What can be honestly claimed

**Can claim:**
- "We have a PIT-aware backtest engine with survivorship bias protection"
- "We have a research validation framework implementing walk-forward, PSR/DSR, Reality Check, and purged CV"
- "The framework follows published methodologies (Bailey & Lopez de Prado, White, Politis & Romano)"

**Cannot claim:**
- "Our strategies are empirically validated"
- "We have proven alpha over the benchmark"
- "Our research validation has been exercised on production data"
- "Strategies have passed promotion checks"

**Honest framing:**
> Q3 has a production-ready backtesting engine and a research-grade validation framework. The framework is implemented and unit-tested but has not yet been exercised against production data. No strategy has completed the full validation pipeline. Empirical claims require completing the validation cycle.

---

## Summary: System Maturity Assessment

| Axis | Maturity | Key gap |
|------|:--------:|---------|
| A. System definition | High | — |
| B. Core strategies | High | Hybrid quality overlay limited by data coverage |
| C. Metrics | High | NBY exact blocked by vendor (proxy available) |
| D. Claims | Medium | Gap between capability and evidence |
| E. Language | Defined | Needs enforcement |
| F. Empirical validation | **Low** | 0 completed runs, 0 promoted strategies, no benchmark |

### The single biggest gap

**The backtest engine and research framework exist but have never produced results.** This is the gap between "we built it" and "it works on our data." Closing this gap is the highest-value next step for scientific credibility.
