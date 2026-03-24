# Institutional Validation Pack

## Status: SHAPING COMPLETE — Awaiting Tech Lead approval

---

## 1. Problem

Q3 has a complete pipeline (ranking → refiner → decision engine → UI) with governance, but lacks the **evidence package** a serious fund would require. The TL assessment:

- Product/methodology: 8.5/10
- Institutional robustness perceived: 7/10
- Evidence to convince serious fund: 5.5–6.5/10

The gap is not "build more" — it's "validate better and package better."

---

## 2. Appetite

**Level: M** — 4 deliverables, 1 session

---

## 3. Post-Validation Findings (MF-TDE-POST-VALIDATION-01)

### 30-ticker validation results

| Metric | Value |
|--------|------:|
| APPROVED | 8/30 (27%) |
| BLOCKED | 17/30 (57%) |
| REJECTED | 5/30 (17%) |
| Suppression rate (implied value) | 20/30 (67%) |
| Yield outlier rate | 9/30 (30%) |
| Market data invalid | 2/30 |
| Has refiner data | 11/30 (37%) |
| Has thesis data | 4/30 (13%) |
| Critical risks | 6 total |
| All valuations | CHEAP (100%) |

### Key observations

1. **All 30 are CHEAP** — the top-30 by EY is, by definition, the cheapest universe. Not a bug; it's how the selection works.
2. **67% suppression** — the sanity guard works aggressively. Most suppressions are from upside > 300% (EV distortion in cheap names).
3. **57% BLOCKED by LOW_CONFIDENCE** — dominated by missing refiner data (only 11/30 have it). The engine correctly blocks when evidence is insufficient.
4. **8 APPROVED with refiner** — all 8 have quality ≥ 0.54, confidence MEDIUM, and yield > minimum threshold.
5. **System refuses to opine** on 17/30 — this is the governance working as designed.

---

## 4. Deliverables

### D1 — System Overview (1 page)

**Title**: Q3 — Decision-Support Research System for B3 Equity Selection

Content:
- What Q3 is (and isn't)
- Architecture diagram (ranking → refiner → decision → governance)
- Data sources (CVM filings, Yahoo market data — free sources only)
- Key methodological commitments (PIT integrity, proxy-aware, no overclaim)
- Current status: research tool, not production allocator

### D2 — Evidence Pack

Content:
- **Decision engine vs ranking**: approved tickers outperform ranking average on quality
- **Approved vs blocked vs rejected**: quality/yield/risk profile comparison
- **OOS empirical evidence**: hybrid_20q walk-forward results (3/3 splits positive)
- **Benchmark comparison**: Ibovespa relative metrics
- **Failure analysis**: 2024 OOS collapse — what happened, why, and what the system learned

### D3 — Governance Pack

Content:
- What is proxy vs hard data (table)
- When the system refuses to opine (BLOCKED conditions)
- Strategy status registry (APPROVED/BLOCKED/REJECTED with evidence)
- Confidence breakdown (what LOW/MEDIUM/HIGH means)
- Sanity guards (valuation suppression, yield outlier flagging, market data invalidation)

### D4 — Casebook (5 studies)

Selection criteria:
- 2 cases where system correctly APPROVED (with evidence)
- 2 cases where system correctly BLOCKED/REJECTED (with evidence)
- 1 case where system's output is debatable (honest uncertainty)

Each case:
- Full decision output
- Why the system decided what it decided
- What a human analyst might see differently
- Lessons for the methodology

---

## 5. Boundaries

- Do NOT create new features
- Do NOT change the decision engine
- Do NOT run new backtests
- All evidence from existing artifacts
- Honest framing only — no overclaim

---

## 6. Build Scope

### S1 — Generate all 4 documents

Single script that produces:
1. `system-overview.md`
2. `evidence-pack.md`
3. `governance-pack.md`
4. `casebook.md`

All in `docs/institutional-validation-pack/`.

### Validation

| Check | Pass criteria |
|-------|---------------|
| V1 | 4 documents complete |
| V2 | No overclaims (verified by language audit) |
| V3 | All evidence traceable to artifacts |
| V4 | 5 case studies with full decision outputs |
| V5 | Governance pack covers all suppression/invalidation types |

---

## 7. Close Summary

_Not started._
