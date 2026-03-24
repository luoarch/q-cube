# MF-PILOT-01 — Institutional Pilot Protocol

## Status: SHAPING COMPLETE — Awaiting Tech Lead approval

---

## 1. Central Question

> Does the APPROVED cohort generate practical utility superior to ranking/refiner alone, without increasing serious errors?

---

## 2. Pilot Design

### Mode: Shadow (no capital at risk)

Q3 runs prospectively alongside the evaluator's existing process. No trades executed based on Q3 output. All decisions logged in real-time, never retroadjusted.

### Duration: 6 months (minimum 3 for interim assessment)

| Month | Activity |
|------:|---------|
| 0 | Freeze engine rules. Expand refiner to full eligible universe. Run initial classification. |
| 1-5 | Monthly classification cycle. Log decisions + human overrides. Track forward returns. |
| 6 | Final assessment against predefined success/fail criteria. |

### Universe: CORE_ELIGIBLE with full refiner coverage

Before pilot starts:
- Expand refiner run from top-30 to **all 196 data-eligible tickers**
- This resolves 82% of contingent BLOCKEDs
- Pilot measures the engine at full operational capacity, not current 16% coverage

### Frequency: Monthly classification cycle

1st business day of each month:
1. Refresh market snapshots
2. Run ranking
3. Run refiner (full universe)
4. Run decision engine
5. Log all APPROVED / BLOCKED / REJECTED with full output
6. Human evaluator reviews APPROVED list, records agree/disagree/override

---

## 3. Frozen Rules

During the pilot, the following are **immutable**:

| Component | Frozen version |
|-----------|---------------|
| Decision thresholds | quality ≥ 0.5, yield ≥ dynamic, confidence ≥ MEDIUM |
| Sanity guards | upside > 300% suppression, mcap = 0 invalidation |
| Confidence penalties | refiner -0.15, thesis -0.10, sector fallback -0.10, drivers -0.10, valuation -0.20 |
| Risk gates | critical risk thresholds (leverage > 5x, coverage < 1x, cash conv < -0.5) |
| Strategy registry | ctrl_original REJECTED, ctrl_brazil REJECTED, hybrid_20q BLOCKED |

No engine changes during pilot. Bug fixes only (with documentation).

---

## 4. Predefined Metrics

### Primary metrics (monthly)

| Metric | Definition | Target |
|--------|-----------|--------|
| **APPROVED forward return** | Equal-weight return of APPROVED cohort over 1/3/6 months | Positive |
| **Relative return** | APPROVED return minus BLOCKED return | Positive |
| **Benchmark-relative** | APPROVED return minus Ibovespa | Positive (6-month horizon) |
| **Hit rate** | % of APPROVED names with positive return at 3 months | > 55% |
| **Max drawdown** | Worst peak-to-trough of APPROVED cohort | < 20% |

### Secondary metrics (monthly)

| Metric | Definition | Target |
|--------|-----------|--------|
| **False positive rate** | % of APPROVED names that lose > 15% in 3 months | < 20% |
| **False negative rate** | % of BLOCKED names that gain > 20% in 3 months | Reported (no target) |
| **Suppression usefulness** | % of suppressed valuations where proxy would have been misleading | > 70% |
| **Override rate** | % of APPROVED where human evaluator disagrees | < 30% |
| **REJECTED accuracy** | % of REJECTED names that underperform universe | > 60% |

### Governance metrics

| Metric | Definition |
|--------|-----------|
| Coverage rate | % of universe with non-BLOCKED classification |
| Refusal rate | % classified as BLOCKED |
| Classification stability | % of names that changed status month-over-month |
| Engine drift | Any deviation from frozen rules (should be 0) |

---

## 5. Success Criteria (at 6 months)

### PASS (pilot successful — justify next phase)

All of:
- APPROVED cohort return > BLOCKED cohort return (3 of 6 months minimum)
- APPROVED hit rate > 55% at 3-month horizon
- False positive rate < 20%
- Override rate < 30% (human agrees with most approvals)
- No engine drift (rules frozen throughout)

### INCONCLUSIVE (extend pilot)

Any of:
- APPROVED outperforms in 2/6 months but not 3
- Hit rate between 45-55%
- Override rate between 30-50%

### FAIL (pilot does not justify next phase)

Any of:
- APPROVED cohort return < BLOCKED cohort return (4+ of 6 months)
- Hit rate < 45%
- False positive rate > 30%
- Override rate > 50% (human disagrees with most approvals)

---

## 6. Fail Criteria (hard stops)

| Condition | Action |
|-----------|--------|
| APPROVED cohort drawdown > 30% | Pause pilot, review |
| Engine produces identical output 3 months in row (stale data) | Pause, investigate |
| > 3 APPROVED names hit critical risk post-classification | Review risk gates |

---

## 7. Prospective Logging

### Decision journal (per cycle)

For each monthly run, persist:

```json
{
  "cycle": "2026-04",
  "run_date": "2026-04-01T09:00:00Z",
  "engine_version": "v1.0-frozen",
  "universe_size": 196,
  "classification_counts": {"APPROVED": 45, "BLOCKED": 80, "REJECTED": 71},
  "approved_tickers": ["VALE3", "CMIG3", ...],
  "human_overrides": [
    {"ticker": "VALE3", "system": "APPROVED", "human": "AGREE", "note": ""},
    {"ticker": "ABEV3", "system": "BLOCKED", "human": "WOULD_APPROVE", "note": "Strong brand moat not captured"}
  ],
  "forward_returns": null  // populated at T+1, T+3, T+6 months
}
```

No retroadjustment. Journal is append-only. Forward returns filled in later from market data.

### Monthly report

| Section | Content |
|---------|---------|
| Classification summary | Counts + changes from prior month |
| Forward returns (lagged) | T+1 for prior month, T+3 for 3 months ago |
| Override analysis | Where human disagreed, why |
| Risk events | Any APPROVED name that hit a critical threshold |
| Suppression review | Were suppressed proxies correct in hindsight? |

---

## 8. What Would Justify Next Phase

If PASS at 6 months:

1. **Coverage expansion**: Expand thesis layer to full universe
2. **Confidence recalibration**: Adjust penalties based on override patterns
3. **Strategy promotion**: Re-evaluate hybrid_20q with 2 additional OOS splits
4. **Production deployment**: Live signal generation (still shadow, but integrated into workflow)

---

## 9. What This Pilot Does NOT Do

- Does not allocate capital
- Does not replace human judgment
- Does not prove long-term alpha
- Does not validate all parameter choices
- Does not test portfolio construction or execution

It answers one question only:

> **Does the classification add useful signal to the investment process?**

---

## 10. Pre-Pilot Checklist

| Item | Status | Required before start |
|------|:------:|:--------------------:|
| Refiner expanded to 196 tickers | Pending | YES |
| Engine rules frozen + versioned | Ready | YES |
| Decision journal schema defined | Ready | YES |
| Forward return tracking pipeline | Pending | YES |
| Human evaluator identified | Pending | YES |
| Monthly report template | Ready | YES |
| Baseline classification run (month 0) | Pending | YES |
