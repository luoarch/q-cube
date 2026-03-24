# MF-PILOT-01 — Institutional Pilot Protocol

## Status: SHAPING COMPLETE — Awaiting Tech Lead approval (v2)

---

## 1. Central Question

> Does the APPROVED cohort generate practical utility superior to ranking alone and universe baseline, without increasing serious errors?

---

## 2. Pilot Phases

### Phase 0 — Operational Shakeout (non-evaluated)

**Duration**: 1 full monthly cycle before pilot starts.

**Objective**: Validate that the expanded refiner (196 tickers), tracking pipeline, logging, and monthly report all work at scale. This phase does NOT count toward pilot metrics.

| Check | Pass to proceed |
|-------|:---------------:|
| Refiner runs on 196 tickers without error | YES |
| Decision engine produces valid output for ≥ 180 tickers | YES |
| Classification distribution is non-degenerate (not 100% one status) | YES |
| Forward return tracking pipeline logs correctly | YES |
| Decision journal schema persists without data loss | YES |
| Monthly report generates with all sections populated | YES |

If any check fails, fix and re-run Phase 0. Do not start Phase 1.

### Phase 1 — Shadow Pilot (evaluated)

**Duration**: 6 months (interim review at month 3).

**Mode**: Shadow only. No capital at risk. All decisions logged prospectively. No retroadjustment.

**Frequency**: Monthly classification cycle (1st business day).

---

## 3. Universe & Baseline Comparisons

### Universe

CORE_ELIGIBLE with full refiner coverage (196 data-eligible tickers).

### Three comparison cohorts

| Cohort | Definition | Purpose |
|--------|-----------|---------|
| **APPROVED** | Decision engine APPROVED output | Primary test subject |
| **RANKING TOP-N** | Top 20 by EY from compat view (no decision filter) | Baseline: is decision engine better than pure ranking? |
| **UNIVERSE EW** | Equal-weight all 196 eligible tickers | Baseline: is selection better than no selection? |

All forward returns measured on the same dates, same universe, same period.

---

## 4. Frozen Rules

During Phase 1, the following are **immutable**:

| Component | Frozen version |
|-----------|---------------|
| Decision thresholds | quality ≥ 0.5, yield ≥ dynamic, confidence ≥ MEDIUM |
| Sanity guards | upside > 300% suppression, mcap = 0 invalidation |
| Confidence penalties | refiner -0.15, thesis -0.10, sector -0.10, drivers -0.10, valuation -0.20 |
| Risk gates | leverage > 5x, coverage < 1x, cash conv < -0.5 |
| Strategy registry | All current entries unchanged |

Bug fixes only (with documentation and justification).

---

## 5. Success Criteria (hierarchical)

### Primary criterion (signal validation)

| Criterion | Definition | Target |
|-----------|-----------|--------|
| **APPROVED > Ranking Top-20** | APPROVED 3-month return > Ranking Top-20 3-month return | Positive in ≥ 3 of 6 months |
| **APPROVED > Universe EW** | APPROVED 3-month return > Universe equal-weight return | Positive in ≥ 3 of 6 months |

Both must pass. If APPROVED doesn't beat at least one baseline consistently, the decision layer doesn't add signal.

### Secondary criteria (quality metrics)

| Criterion | Definition | Target |
|-----------|-----------|--------|
| Hit rate | % of APPROVED names with positive excess return vs Ibovespa at 3 months | > 55% |
| False positive rate | % of APPROVED names with excess return < -10% vs Ibovespa at 3 months | < 20% |
| False negative rate | % of BLOCKED names with excess return > +15% vs Ibovespa at 3 months | Reported, no hard target |
| Override rate | % of APPROVED where evaluator disagrees | < 30% |
| REJECTED accuracy | % of REJECTED names that underperform Ibovespa at 3 months | > 60% |

**Note on FP/FN thresholds**: Defined as excess return vs Ibovespa (benchmark-adjusted), not absolute. This controls for market/beta effects. Thresholds (-10% FP, +15% FN) are asymmetric by design: false approvals are more costly than false blocks.

### Operational integrity criteria

| Criterion | Target |
|-----------|--------|
| Engine drift | 0 (frozen rules throughout) |
| Missing runs | 0 (all 6 monthly cycles completed) |
| Log integrity | Append-only, no retroadjustment |
| Phase 0 passed | YES |

---

## 6. PASS / INCONCLUSIVE / FAIL

### PASS (justify next phase)

- Primary: both APPROVED > Ranking Top-20 AND APPROVED > Universe EW in ≥ 3/6 months
- Secondary: hit rate > 55%, FP < 20%, override < 30%
- Operational: all integrity criteria met

### INCONCLUSIVE (extend 3 months)

- Primary passes 1 of 2 baselines but not both, OR passes in 2/6 months
- Secondary: hit rate 45-55% or override 30-40%

### FAIL (does not justify next phase)

- Primary: APPROVED < both baselines in ≥ 4/6 months
- OR: hit rate < 45%
- OR: FP > 30%
- OR: override > 50%
- OR: operational integrity violated

---

## 7. Hard Stops

| Condition | Check method | Action |
|-----------|-------------|--------|
| APPROVED cohort drawdown > 30% vs start of pilot | Monthly mark-to-market | Pause, review risk gates |
| Stale data: upstream snapshot freshness > 14 days for > 50% of universe | Check `fetched_at` timestamps | Pause, investigate data pipeline |
| ≥ 3 APPROVED names hit critical risk thresholds post-classification | Monthly risk scan | Review gates, document |
| Evaluator signals systematic disagreement (override > 60% for 2 consecutive months) | Override log | Pause, recalibrate or end |

---

## 8. Evaluator Protocol

### Reviewer definition

- **Primary evaluator**: 1 designated analyst or portfolio manager
- **Rubric**: Fixed decision rubric (agree / disagree-would-approve / disagree-would-block / disagree-would-reject)
- **Override reasons**: Standardized taxonomy:
  - `RISK_NOT_CAPTURED` — system missed a material risk
  - `QUALITY_OVERRATED` — refiner score doesn't reflect reality
  - `VALUATION_DISAGREE` — EY proxy misrepresents value
  - `THESIS_DISAGREE` — thesis/sector classification wrong
  - `DATA_STALE` — underlying data is outdated
  - `OTHER` — free text (max 100 chars)

### Review process

- Evaluator reviews ALL APPROVED names (expected ~30-50 per cycle)
- Reviews a random sample of 10 BLOCKED names per cycle
- Logs override + reason within 5 business days of classification
- No communication of Q3 output to investment decisions during shadow period

---

## 9. Monthly Report

### Section 1 — Pipeline Coverage

| Metric | Reported |
|--------|:--------:|
| Universe size | YES |
| Refiner coverage achieved | YES |
| Thesis coverage | YES |
| Decision coverage (non-BLOCKED) | YES |
| Valuation suppression rate | YES |
| Market data invalidation rate | YES |

### Section 2 — Classification Summary

- APPROVED / BLOCKED / REJECTED counts
- Month-over-month status changes (stability metric)
- New entrants / exits from each cohort

### Section 3 — Forward Returns (lagged)

- T+1 month returns for prior cycle
- T+3 month returns for 3 cycles ago
- APPROVED vs Ranking Top-20 vs Universe EW
- Cohort Sharpe (if enough data points)

### Section 4 — Override Analysis

- Override count and rate
- Breakdown by reason
- Where evaluator disagreed, what was the subsequent return

### Section 5 — Risk Events

- APPROVED names that subsequently hit critical thresholds
- REJECTED names that subsequently recovered (potential false negatives)
- Suppression review: were suppressed proxies correct in hindsight?

---

## 10. What Would Justify Next Phase

If PASS at 6 months:

1. **Thesis expansion**: Full Plan 2 coverage on 196 tickers
2. **Confidence recalibration**: Adjust penalties based on override patterns
3. **Strategy re-evaluation**: hybrid_20q with 2 additional OOS splits from pilot period
4. **Production integration**: Live signal generation, integrated into research workflow (still shadow)
5. **Second pilot**: Longer horizon (12 months), potentially with paper portfolio

---

## 11. What This Pilot Does NOT Do

- Does not allocate capital
- Does not replace human judgment
- Does not prove long-term alpha
- Does not validate all parameter choices
- Does not test portfolio construction or execution
- Does not guarantee the system works in all market regimes

It answers one question:

> **Does the classification add useful signal to the investment process?**

---

## 12. Pre-Pilot Checklist

| Item | Status | Required |
|------|:------:|:--------:|
| Refiner expanded to 196 tickers | Pending | YES |
| Engine rules frozen + versioned | Ready | YES |
| Decision journal schema | Ready | YES |
| Forward return tracking pipeline | Pending | YES |
| Primary evaluator identified + trained | Pending | YES |
| Override rubric + reason taxonomy | Ready | YES |
| Monthly report template | Ready | YES |
| Phase 0 shakeout passed | Pending | YES |
| Baseline classification run (month 0) | Pending | YES |
