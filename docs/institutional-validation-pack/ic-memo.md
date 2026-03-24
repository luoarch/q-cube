# Investment Committee Memo — Q3 Evaluation

**Date**: March 2026
**Subject**: Q3 Decision-Support Research System — Pilot Evaluation Proposal
**Classification**: For internal evaluation only

---

## What It Is

Q3 is a deterministic equity screening and classification system for B3, built on CVM public filings and Yahoo market data. It produces per-ticker research classifications (APPROVED / BLOCKED / REJECTED) with full audit trail.

**Pipeline**: Ranking (EY+ROC) → Quality Refiner (4 scores) → Decision Engine (valuation proxy + yield + drivers + risks + confidence) → Governance (thresholds + suppression + registry).

**Data**: Free public sources only (CVM DFP/ITR, Yahoo Finance). No proprietary feeds.

**Output**: Standardized per-ticker report with quality, valuation label, implied yield, drivers, risks, confidence score, and final classification. Every field is traceable to source data.

---

## What It Is Not

- Not an intrinsic valuation engine (uses EY normalization proxy, not DCF)
- Not a portfolio allocator (no position sizing, no execution)
- Not a recommendation system (output is research classification)
- Not forward-looking (implied yield assumes no growth)
- Not a black box (fully deterministic, same input = same output)

---

## Evidence Summary

### System behavior (38 full-pipeline tickers)

| Cohort | Count | Avg Quality | Avg Yield | Critical Risks |
|--------|------:|:----------:|:---------:|:--------------:|
| APPROVED | 11 | 0.63 | 26.9% | 0 |
| BLOCKED | 18 | 0.63 | 20.1% | 0 |
| REJECTED | 9 | 0.56 | 9.8% | 13 |

Decision engine removes 3 dangerous names from ranking top-10 (critical risk, insufficient evidence) and surfaces 4 quality names the ranking underweighted.

### Strategy-level OOS (walk-forward, hybrid quality overlay)

| Period | OOS Sharpe | vs Controls |
|--------|:---------:|:-----------:|
| 2022 | +0.81 | Wins both |
| 2023 | +2.77 | Wins both |
| 2024 | +0.04 | Wins both |

Quality overlay shows persistent relative advantage (3/3 splits) but high dispersion. Not promoted.

### Refusal behavior

57% of top-50 tickers are BLOCKED (system refuses to opine). 82% of blocks are contingent on refiner coverage expansion — operational, not structural.

---

## Current Limits

1. Refiner covers 16% of eligible universe (38 of 242 CORE tickers)
2. No forward validation of APPROVED vs BLOCKED return differential
3. Lead strategy (hybrid_20q) blocked by OOS sensitivity — not promoted
4. Proxy valuation suppressed in 67% of cases (EV distortion in cheap names)
5. All data is free/public — no Bloomberg, no proprietary feeds
6. Output is research classification, not investment recommendation

---

## Proposed Evaluation

**Format**: 3-6 month parallel run alongside existing process.

**Protocol**:
- Q3 runs monthly on the CORE universe
- Track APPROVED vs BLOCKED vs REJECTED forward returns
- Compare Q3 classifications against analyst decisions
- Measure: hit rate, false positive rate, false negative rate, incremental signal

**Success criteria**:
- APPROVED cohort outperforms BLOCKED/REJECTED on risk-adjusted basis
- System correctly identifies ≥70% of names analysts would flag as risky
- Refusal behavior (BLOCKED) correlates with higher uncertainty in outcomes

**What we need**:
- Access to run parallel evaluation
- Feedback on threshold calibration
- 1 hour per month for review and calibration discussion

**What we do NOT need**:
- Capital allocation
- System integration
- Proprietary data access
