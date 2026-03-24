# Month 1 Deep Analysis (TL-mandated actions)

## Action 1 — Confidence Decomposition

### Why zero HIGH confidence

Max confidence score observed: **0.40** (threshold for HIGH: 0.70).

Root cause chain:
1. `sector_fallback` penalty (-0.10) hits **100% of tickers** — most CVM sectors have < 5 CORE issuers
2. `missing_thesis` penalty affects 55% (thesis at 11% coverage)
3. Even with perfect data_completeness (0.60) + LOW evidence (0.12) = 0.72, minus sector_fallback (-0.10) = **0.62** → MEDIUM, not HIGH

**Conclusion**: HIGH confidence is structurally unreachable until either (a) sector_fallback threshold is lowered from 5, or (b) thesis coverage expands. This is a calibration observation, not a bug — documented under frozen rules.

### What drives LOW (116 tickers)

| Penalty | Count | % of LOW |
|---------|------:|:--------:|
| sector_fallback | 116 | 100% |
| drivers_insufficient | 36 | 31% |
| missing_thesis | 29 | 25% |
| valuation_missing | 2 | 2% |

## Action 2 — Approved Without Thesis

**All 33 APPROVED have thesis missing.** Zero APPROVED have thesis present.

This means thesis presence is NOT a gating requirement for approval. The system approves based on quality + valuation + yield + confidence MEDIUM — thesis is a booster for confidence, not a hard gate.

### Profile of thesis-less APPROVED

- Avg quality: 0.661
- Avg yield: 28.2%
- Avg risks: 0.5
- Suppressed valuation: 12/33 (36%)
- Yield outliers: 4/33 (12%)

**Interpretation**: These are "good enough without thesis context" — fundamentally strong names that pass quality and yield thresholds despite incomplete evidence. Not ideal, but consistent with the system's design (thesis boosts confidence, doesn't gate approval).

## Action 3 — Ranking vs APPROVED Delta

| Metric | Ranking Top-20 | APPROVED (33) |
|--------|:--------------:|:-------------:|
| Avg quality | 0.622 | **0.661** |
| Count | 20 | 33 |

### Engine REMOVED 11 from Ranking Top-20

| Ticker | Status | Quality | Reason |
|--------|:------:|:-------:|--------|
| BOBR3 | REJECTED | 0.52 | Interest coverage 0.2x |
| SNSY3 | REJECTED | 0.47 | Interest coverage 0.9x |
| MNDL3 | REJECTED | 0.39 | Cash conversion -12x |
| GOAU3 | BLOCKED | 0.71 | Low confidence |
| MMAQ3 | BLOCKED | 0.75 | Low confidence |
| MYPK3 | BLOCKED | 0.76 | Low confidence |
| + 5 more | BLOCKED | 0.45-0.62 | Low confidence |

3 removed for **critical risk** (correct). 8 removed for **low confidence** (prudent — some have high quality but insufficient evidence).

### Engine ADDED 24 outside Top-20

Top additions: LEVE3 (Q=0.75), POMO3 (Q=0.79), ESPA3 (Q=0.68), RANI3 (Q=0.62)

**Value-add**: Decision engine surfaces 24 quality names that pure EY ranking misses, while removing 3 dangerous names and blocking 8 uncertain ones.
