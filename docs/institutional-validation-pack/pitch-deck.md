# Q3 — Institutional Partner Deck

---

## Slide 1 — Problem

**Equity screening in Brazil is manual, opaque, and unauditable.**

Fund analysts spend weeks on ranking + quality checks + valuation + risk assessment — then make decisions with no systematic governance over what's "good enough" to act on.

Result: inconsistent process, hidden biases, no audit trail.

---

## Slide 2 — Q3 System

**A deterministic, governed research system for B3 equity selection.**

Q3 takes CVM filings + public market data and produces per-ticker research classifications:

- **APPROVED** — quality + valuation + yield + confidence all pass thresholds
- **BLOCKED** — insufficient evidence to decide (system refuses to opine)
- **REJECTED** — critical risk, low quality, or unfavorable valuation

Every output is auditable. Every number has provenance. Every proxy is labeled.

---

## Slide 3 — Pipeline

```
CVM Filings → Fundamentals → Ranking (EY+ROC) → Quality Refiner → Decision Engine → Governance
```

| Layer | What it does | Data |
|-------|-------------|------|
| Ranking | Orders by earnings yield + return on capital | 15 computed metrics |
| Refiner | Scores quality (earnings, safety, consistency, discipline) | 4 sub-scores, flags |
| Decision | Classifies: valuation proxy + implied yield + drivers + risks | Deterministic rules |
| Governance | Enforces thresholds, suppresses distortions, requires acknowledgment | Registry + guardrails |

No black boxes. No ML opacity. Fully deterministic.

---

## Slide 4 — Guardrails

**The system is designed to say "I don't know."**

| Guard | What it does |
|-------|-------------|
| **Confidence gate** | Blocks when data is insufficient (57% of top-50) |
| **Yield threshold** | Blocks when implied yield is below sector-adjusted floor |
| **Sanity suppression** | Hides proxy valuation when upside > 300% (67% suppressed) |
| **Risk gate** | Rejects when critical risks detected (interest coverage, leverage) |
| **Soft enforcement** | Warning modal before running rejected strategies |
| **Language guardrails** | "Research classification, not investment recommendation" on every surface |

A system that always says "yes" is dangerous. Q3 says "no" more often than "yes."

---

## Slide 5 — Evidence

### Ablation: what each layer adds

| Scenario | Ranking Top 10 overlap with APPROVED | Names removed | Names added |
|----------|:---:|:-:|:-:|
| Ranking only | — | — | — |
| + Decision Engine | 70% | 3 (risk/confidence) | 4 (quality surfaced) |

### Cohort profiles (38 full-pipeline tickers)

| | APPROVED (11) | BLOCKED (18) | REJECTED (9) |
|-|:---:|:---:|:---:|
| Avg Quality | 0.63 | 0.63 | 0.56 |
| Avg Yield | 26.9% | 20.1% | 9.8% |
| Critical Risks | 0 | 0 | 13 |

APPROVED: higher yield, zero critical risks.
REJECTED: lower quality, much lower yield, 13 critical risks.

---

## Slide 6 — Failure Modes (honest)

| Category | % | Example |
|----------|--:|---------|
| Coverage gap (refiner) | 56% | No quality data → BLOCKED |
| Critical risk rejection | 14% | Interest coverage < 1x |
| Governance block | 10% | Confidence below threshold |
| Approved with caveats | 18% | Suppressed proxy or marginal confidence |

**82% of BLOCKEDs are contingent** — they'd resolve with expanded refiner coverage (from 38 to 196 tickers). This is an operational gap with a clear path to resolution.

---

## Slide 7 — Case Studies

**SNSY3 — Rejected (correct)**
EY 110% looks attractive. But interest coverage = 0.9x. The company can't service its debt. System correctly prioritized solvency over cheapness.

**ABEV3 — Blocked (correct)**
Quality 0.64, FAIR valuation. But thesis data missing → system can't assess fragility. Blocks rather than guess. "Unknown ≠ safe."

**CEDO3 — Approved with suppressed proxy**
EY 34.8%, quality 0.60, CHEAP. But implied price R$237 vs current R$10 (2,258% upside). System approved based on quality/yield, but **suppressed the proxy number** to prevent misleading display.

---

## Slide 8 — Current Limits

1. **Refiner covers 16% of universe** (38/242) — operational, not architectural
2. **No forward return validation** of APPROVED vs BLOCKED — requires time
3. **Strategy not promoted** — hybrid_20q blocked by OOS dispersion
4. **Proxy valuation, not DCF** — EY normalization, not intrinsic value
5. **Free data only** — CVM + Yahoo. No Bloomberg, no proprietary feeds
6. **Research classification** — not executable recommendation

---

## Slide 9 — Where This Fits

Q3 is **not** a replacement for your investment process.

Q3 is a **systematic first-pass layer** that:

- Screens the universe deterministically
- Flags quality/risk/valuation signals
- Classifies each name with explicit governance
- Refuses to opine when evidence is insufficient
- Provides auditable provenance for every number

**Use case**: pre-screening for idea generation, systematic quality check, governance layer for stock selection.

---

## Slide 10 — Next Steps

### What we're looking for

- **Pilot evaluation**: Run Q3 alongside your process for 3-6 months
- **Forward validation**: Track APPROVED vs BLOCKED vs REJECTED performance
- **Coverage expansion**: Expand refiner to full universe (196 tickers)
- **Feedback loop**: Calibrate thresholds with institutional input

### What we're NOT asking

- Not asking you to allocate capital based on Q3 alone
- Not asking you to replace your analysts
- Not asking you to trust a proxy as intrinsic valuation

We're asking for a structured evaluation of whether this adds signal to your process.
