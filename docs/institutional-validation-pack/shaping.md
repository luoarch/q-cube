# Institutional Validation Pack

## Status: SHAPING COMPLETE — Awaiting Tech Lead approval (v2)

---

## 1. Problem

Q3 has a complete decision pipeline but lacks the **diligence-grade evidence package** a serious fund requires. The gap is not "build more" — it's "prove it works, show where it fails, and be honest about limits."

---

## 2. Five Analytical Blocks (TL-required)

### Block 1 — Coverage: Prudence vs Insufficient Coverage

**Investigated finding (high confidence):**

| Layer | Coverage | % of CORE |
|-------|--------:|:--------:|
| CORE_ELIGIBLE universe | 242 | 100% |
| With earnings_yield | 196 | 81% |
| With market data (mcap > 0) | 194 | 80% |
| With thesis data | 120 | 50% |
| With refiner data | **38** | **16%** |

**BLOCKED decomposition (50-ticker sample):**
- 82% of BLOCKEDs are **CONTINGENT** — would resolve if refiner ran on more tickers
- 18% are **STRUCTURAL** — data gap or governance threshold

**Answer to TL question**: BLOCKED is predominantly **contingent on refiner coverage**, not structural inability. The refiner currently runs only on top ~30 per strategy run. Expanding to full EY universe (196) would reduce contingent blocks from 82% to near-zero.

**Maximum theoretical coverage**: 196 tickers (81% of CORE). Current operational coverage: 38 (16%). The gap is operational, not architectural.

### Block 2 — Incremental Value (Ablation)

**Investigated finding (high confidence):**

38-ticker full-pipeline analysis:

| Layer | What it does | Distribution |
|-------|-------------|:-------------|
| **Ranking only** | Orders by EY | Top 10 includes SNSY3 (critical risk), POSI3/KEPL3 (insufficient evidence) |
| **Ranking + Refiner** | Adds quality scores | Separates quality but no decision |
| **Full Decision Engine** | Adds valuation + yield + risks + governance | 11 APPROVED / 18 BLOCKED / 9 REJECTED |

**Cohort comparison (full pipeline, 38 tickers):**

| Cohort | Avg Quality | Avg Yield | Avg Risks | Critical |
|--------|:----------:|:---------:|:---------:|:--------:|
| APPROVED (11) | **0.629** | **26.9%** | **0.3** | **0** |
| BLOCKED (18) | 0.630 | 20.1% | 0.3 | 0 |
| REJECTED (9) | 0.560 | 9.8% | **2.1** | **13** |

**Key differentiation**: APPROVED and BLOCKED have similar quality (0.63 vs 0.63) — the separator is **yield** (26.9% vs 20.1%) and **confidence**. REJECTED has clearly worse quality (0.56), much worse yield (9.8%), and 13 critical risks.

**Ranking vs Decision (overlap analysis):**
- 7/10 ranking top-10 are also APPROVED (70% alignment)
- Engine REMOVED 3: SNSY3 (critical risk: interest coverage 0.9x), POSI3/KEPL3 (insufficient evidence)
- Engine ADDED 4: ISAE3, LEVE3, REDE3, SAPR3 — all with quality > 0.54 and good yield

**Incremental value**: The decision engine adds risk gating (removes dangerous names), confidence gating (blocks uncertain names), and surfaces quality names the ranking underweighted.

### Block 3 — OOS Protocol

**Primary hypothesis**: APPROVED cohort delivers higher risk-adjusted return than BLOCKED/REJECTED over forward periods.

**Current limitation**: Forward returns cannot be measured yet (decision engine is new). The only OOS evidence available is from the **backtest walk-forward** on the hybrid_20q strategy:

| Split | OOS Sharpe | Period |
|-------|:---------:|--------|
| 2022 | +0.81 | IS 2020-H2→2021, OOS 2022 |
| 2023 | +2.77 | IS 2020-H2→2022, OOS 2023 |
| 2024 | +0.04 | IS 2020-H2→2023, OOS 2024 |

**Benchmark**: ^BVSP (Ibovespa, price index — conservative bias).

**What OOS proves**: The hybrid strategy (quality overlay) shows persistent positive OOS Sharpe in 3/3 annual splits. It does NOT yet prove the decision engine's APPROVED/BLOCKED/REJECTED classification predicts forward returns.

**Future OOS protocol** (when forward data available):
- Evaluation window: 6-12 months post-decision
- Cohorts: APPROVED vs BLOCKED vs REJECTED
- Metrics: total return, Sharpe, max drawdown, hit rate
- Success: APPROVED outperforms BLOCKED/REJECTED on risk-adjusted basis
- Benchmark: Ibovespa + equal-weight universe

### Block 4 — Failure Taxonomy

**Investigated finding (high confidence, 50-ticker sample):**

| Category | Count | % | Example |
|----------|------:|--:|---------|
| COVERAGE_GAP_REFINER | 28 | 56% | VSPT3 |
| REJECTED_CRITICAL_RISK | 7 | 14% | SNSY3 (interest coverage 0.9x) |
| GOVERNANCE_BLOCK_CONFIDENCE | 5 | 10% | POSI3 |
| APPROVED_WITH_SUPPRESSED_VALUATION | 4 | 8% | CEDO3 (upside > 300%) |
| APPROVED_MARGINAL_CONFIDENCE | 4 | 8% | DEXP3 |
| APPROVED_WITH_OUTLIER_YIELD | 1 | 2% | VLID3 |
| COVERAGE_GAP_THESIS | 1 | 2% | BRAP3 |

**Summary:**
- **58% CONTINGENT** (coverage gap — would resolve with expanded refiner)
- **14% STRUCTURAL REJECT** (critical risks — correct behavior)
- **10% GOVERNANCE BLOCK** (confidence/threshold rules)
- **18% APPROVED** (9 of 50 approved, 4 with suppression/marginal flags)

**Zero FALSE_APPROVAL detected**: All APPROVED tickers have quality ≥ 0.54, no critical risks. Some have suppressed valuation proxy (correct behavior — suppression ≠ rejection).

**FALSE_REJECTION risk**: KEPL3 and POSI3 are BLOCKED by LOW_CONFIDENCE despite having refiner quality 0.57-0.58. They'd likely be APPROVED with thesis data. This is **prudent false-negative**, not system error.

### Block 5 — Institutional Limits

**Current limits (explicit):**

| Limit | Impact | Mitigable? |
|-------|--------|:----------:|
| Refiner covers 38/242 tickers (16%) | 82% of BLOCKEDs are contingent | Yes — expand refiner run |
| Thesis covers 120/242 (50%) | Missing fragility/opportunity data | Yes — expand thesis run |
| Proxy valuation (EY normalization) | Not intrinsic value; 67% suppressed | Structural — by design |
| No forward return data yet | Cannot validate APPROVED vs BLOCKED performance | Time-dependent |
| Benchmark is price-only | Conservative bias vs strategy DY component | Can add total return benchmark |
| Strategy not promoted | hybrid_20q BLOCKED by sensitivity | More OOS splits needed |
| Output is research classification | Not executable recommendation | By design — governance requirement |
| 100% of top-50 are CHEAP by EY | Selection bias (sorted by EY) | Expected — not a bug |
| Implied yield > 40% in 30% of cases | EV distortion in cheap names | Flagged + suppressed |

---

## 3. Deliverables

### D1 — System Overview (institutional framing)

Mandatory sections:
- Architecture (1 diagram)
- Data sources + dependencies
- Coverage: current (38 full pipeline) vs theoretical (196)
- Refusal rate: 57% BLOCKED, 67% suppression — and why that's correct
- Explicit non-goals: not a recommender, not an allocator, not a DCF engine
- Current limits (from Block 5)

### D2 — Evidence Pack

Mandatory sections:
- **Ablation**: ranking only → ranking + refiner → full decision (from Block 2)
- **Cohort analysis**: APPROVED vs BLOCKED vs REJECTED profiles
- **Overlap analysis**: what the engine adds/removes vs pure ranking
- **OOS protocol**: hypothesis, window, metrics, current evidence, future plan
- **Coverage vs prudence**: contingent (82%) vs structural (18%)

### D3 — Governance Pack

Mandatory sections:
- Proxy vs hard data table (what is computed vs what is derived)
- Data validity rules (market_cap = 0 → hard invalidation)
- Suppression rules (upside > 300% → proxy unavailable)
- Confidence breakdown semantics (5 boolean flags + score + label)
- When UI must not show numbers (3 explicit conditions)
- Strategy registry (3 entries, statuses, evidence)
- Language guardrails (disclaimers on every surface)

### D4 — Casebook (5 studies, fixed template)

Each case:
1. **Thesis**: what the system sees in the data
2. **Inputs**: quality, valuation, yield, drivers, risks, confidence
3. **Decision**: status + reason + block/rejection basis
4. **Human counterargument**: what an analyst might challenge
5. **Validation proxy**: subsequent data or logical check
6. **Lesson**: what the system learned or should learn

Selection:
- **APPROVED correct**: VLID3 (quality 0.71, yield 42.1%, 0 risks)
- **APPROVED correct**: CMIG3 (quality 0.61, CHEAP, 0 risks, DY 9.5%)
- **REJECTED correct**: SNSY3 (quality 0.34, critical risk: interest coverage 0.9x)
- **BLOCKED correct**: ABEV3 (quality 0.64, FAIR, but LOW_CONFIDENCE from thesis gap)
- **Debatable**: KEPL3 (quality 0.58, CHEAP, yield 35.9% — BLOCKED by confidence, analyst might APPROVE)

---

## 4. Appetite

**Level: M** — 4 documents, data-driven

---

## 5. Boundaries

- No new features
- No engine changes
- All evidence from existing artifacts + validation runs
- Honest framing only

---

## 6. Close Summary

_Not started._
