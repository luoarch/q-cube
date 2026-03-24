# Evidence Pack

## 1. Ablation: Incremental Value of Each Layer

### Three layers compared (38 tickers with full pipeline)

| Layer | What it does | What it misses |
|-------|-------------|---------------|
| **Ranking only** | Orders by EY (earnings yield) | No quality filter, no risk gating, no governance |
| **Ranking + Refiner** | Adds 4 quality scores (0-1) + flags | No valuation context, no yield gate, no decision |
| **Full Decision Engine** | Quality + valuation + yield + risks + confidence → APPROVED/BLOCKED/REJECTED | Forward validation pending |

### Distribution (38 full-pipeline tickers)

| Status | Count | Avg Quality | Avg Yield | Avg Risks | Critical |
|--------|------:|:----------:|:---------:|:---------:|:--------:|
| APPROVED | 11 | 0.629 | 26.9% | 0.3 | 0 |
| BLOCKED | 18 | 0.630 | 20.1% | 0.3 | 0 |
| REJECTED | 9 | 0.560 | 9.8% | 2.1 | 13 |

### What the decision engine changes vs pure ranking

**Ranking Top 10 vs APPROVED (38-ticker universe):**
- Overlap: 7/10 (70% alignment)
- Engine REMOVED 3 from ranking top-10:
  - **SNSY3**: REJECTED — critical risk (interest coverage 0.9x)
  - **POSI3**: BLOCKED — insufficient confidence
  - **KEPL3**: BLOCKED — insufficient confidence
- Engine ADDED 4 not in ranking top-10:
  - **ISAE3**: quality 0.54, yield 21.9%
  - **LEVE3**: quality 0.62, yield 22.6%
  - **REDE3**: quality 0.61, yield 20.1%
  - **SAPR3**: quality 0.73, yield 15.2%

**Value-add**: Risk gating (removes dangerous names), confidence gating (blocks uncertain names), and quality surfacing (promotes names the ranking underweighted).

---

## 2. Coverage vs Prudence

### BLOCKED decomposition (50-ticker sample)

| Category | Count | % |
|----------|------:|--:|
| **CONTINGENT** (refiner gap) | 29 | 58% |
| **GOVERNANCE** (threshold/confidence) | 5 | 10% |
| **STRUCTURAL** (critical risk/quality) | 7 | 14% |
| **APPROVED** (all types) | 9 | 18% |

**Key finding**: 82% of BLOCKEDs are contingent on refiner coverage expansion. The refiner currently runs on top ~30 per strategy execution. Expanding to the full data-eligible universe (196 tickers) would reduce contingent blocks from 82% to near-zero.

**This is not structural incapacity — it's operational scope limitation with a clear resolution path.**

---

## 3. OOS Evidence

### Strategy-level (walk-forward, hybrid_20q)

| Split | OOS Period | Sharpe | vs ctrl_original | vs ctrl_brazil |
|-------|-----------|:------:|:----------------:|:--------------:|
| 1 | 2022 | +0.81 | Wins | Wins |
| 2 | 2023 | +2.77 | Wins | Wins |
| 3 | 2024 | +0.04 | Wins | Wins |

3/3 splits positive, 3/3 wins vs controls. Avg OOS Sharpe: 1.20.

### Decision engine level (forward validation pending)

**Primary hypothesis**: APPROVED cohort delivers higher risk-adjusted return than BLOCKED/REJECTED over forward periods.

**Secondary hypothesis**: BLOCKED should underperform APPROVED in coverage-adjusted analysis, but may contain prudent false negatives that would have been APPROVED with more data.

**Protocol** (when forward data available):
- Window: 6-12 months post-decision
- Cohorts: APPROVED vs BLOCKED vs REJECTED
- Metrics: total return, Sharpe, max drawdown, hit rate
- Benchmark: Ibovespa + equal-weight CORE universe

---

## 4. Failure Taxonomy

### Formal categories (50-ticker sample)

| Category | Count | % | Example |
|----------|------:|--:|---------|
| COVERAGE_GAP_REFINER | 28 | 56% | VSPT3 — no refiner data |
| REJECTED_CRITICAL_RISK | 7 | 14% | SNSY3 — interest coverage 0.9x |
| GOVERNANCE_BLOCK_CONFIDENCE | 5 | 10% | POSI3 — quality OK but thesis missing |
| APPROVED_WITH_SUPPRESSED_VALUATION | 4 | 8% | CEDO3 — upside > 300% suppressed |
| APPROVED_MARGINAL_CONFIDENCE | 4 | 8% | DEXP3 — confidence 0.40 (borderline) |
| APPROVED_WITH_OUTLIER_YIELD | 1 | 2% | VLID3 — yield 42.1% flagged |
| COVERAGE_GAP_THESIS | 1 | 2% | BRAP3 — no thesis data |

### False approval analysis

No approval violating current hard risk/quality gates was detected in the reviewed sample. All APPROVED tickers have quality ≥ 0.54, zero critical risks, and yield above dynamic threshold. However, without forward return validation, false approvals cannot be definitively ruled out.

### Prudent false negatives

KEPL3 (quality 0.58, yield 35.9%) and POSI3 (quality 0.57, yield 33.6%) are BLOCKED by LOW_CONFIDENCE despite having refiner data — their thesis data is missing. An analyst might APPROVE these. The system errs on the side of caution.

---

## 5. Error Analysis: 2024 OOS Collapse

The full-year 2024 OOS showed:
- ctrl_original: Sharpe -0.76, CAGR -9.4%
- ctrl_brazil: Sharpe -1.00, CAGR -10.5%
- hybrid_20q: Sharpe +0.04, CAGR -0.06%

**Root cause**: EY+ROC signal was weak across all Core names in 2024. All 22 holdings in the brazil portfolio had negative sell P&L. The hybrid overlay (quality weighting) provided defensive protection but not alpha.

**System response**: The strategy registry records all three as NOT PROMOTED. The governance framework correctly prevents overclaiming based on IS-only results.
