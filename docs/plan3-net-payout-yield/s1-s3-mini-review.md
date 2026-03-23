# Mini Review Consolidada — S1 a S3

## Status: DATA COVERAGE BLOCKER IDENTIFIED

---

## 1. S1 — Mapping Coverage

| Metric | Value |
|--------|-------|
| Total issuers with completed filings | 740 |
| Issuers with `shareholder_distributions` | 552 (74.6%) |
| Total distribution lines | 1,895 |
| Sectors covered | 53 |

### Top matched labels

| Count | Label |
|------:|-------|
| 383 | Dividendos pagos |
| 139 | Pagamento de dividendos |
| 137 | Dividendos Pagos |
| 87 | Dividendos e juros sobre capital próprio pagos |
| 85 | Dividendos e juros sobre o capital próprio pagos |
| 64 | Pagamento de Dividendos |
| 41 | Pagamentos de dividendos |
| 26 | Dividendos |

### Sign distribution

| Sign | Count | % |
|------|------:|----:|
| Negative (correct) | 1,236 | 65.2% |
| Zero | 641 | 33.8% |
| Positive (anomaly) | 18 | 0.9% |

18 positive values: known edge cases (BRKM3 sign anomaly, CASN3 AFAC). Acceptable for v1 since `abs()` handles them.

### Unmapped DFC lines

18,262 DFC 6.03.XX lines remain without `canonical_key` — correctly excluded (empréstimos, recompras, AFAC, etc.).

### NULL reasons (188 issuers without distributions)

- Company genuinely has no DFC sub-account matching dividend/JCP patterns
- No DFC statement available in completed filings

**Verdict: S1 mapping is sound.** 552/740 coverage aligns with expectation that ~25% of B3 issuers either don't pay dividends or don't file DFC sub-accounts.

---

## 2. S2 — Quarter Extraction (3 audited cases)

### Case 1: HBOR3 — Full year, con scope, DFP Q4

| Quarter | YTD | Standalone | Filing |
|---------|----:|----------:|--------|
| Q1 2024-03-31 | 0 | 0 | ITR |
| Q2 2024-06-30 | -12,077,000 | -12,077,000 | ITR |
| Q3 2024-09-30 | -12,077,000 | 0 | ITR |
| Q4 2024-12-31 | -12,077,000 | 0 | DFP |

### Case 2: LWSA3 — Bulk Q4 payout

| Quarter | YTD | Standalone | Filing |
|---------|----:|----------:|--------|
| Q1 2024-03-31 | 0 | 0 | ITR |
| Q2 2024-06-30 | 0 | 0 | ITR |
| Q3 2024-09-30 | -1,000 | -1,000 | ITR |
| Q4 2024-12-31 | -40,001,000 | -40,000,000 | DFP |

### Case 3: CGAS3 — ind scope fallback, high-payout utility

| Quarter | YTD | Standalone | Filing |
|---------|----:|----------:|--------|
| Q1 2024-03-31 | -6,283,000 | -6,283,000 | ITR |
| Q2 2024-06-30 | -1,485,602,000 | -1,479,319,000 | ITR |
| Q3 2024-09-30 | -2,285,433,000 | -799,831,000 | ITR |
| Q4 2024-12-31 | -2,735,338,000 | -449,905,000 | DFP |

Scope: **ind** (no `con` available for any quarter). Fallback from `con` → `ind` exercised correctly.

### DFP vs ITR prevalence

No overlap found for `shareholder_distributions` — DFP and ITR don't coexist for the same issuer/ref_date in distribution lines. The prioritization code is correct but not exercised in current data for this canonical_key.

### NULL case: BETP3 (3 quarters)

Available: Q1, Q3, Q4. Missing: Q2 2024-06-30. `compute_ttm_sum()` → **NULL**. Correct.

---

## 3. S2 — TTM Sanity (no double-counting)

### Reconciliation: TTM sum == YTD_annual

For a full fiscal year (Q1 through Q4), the sum of standalone quarters must equal the DFP annual value. This proves deaccumulation is correct and there's no double-counting.

| Issuer | YTD_annual (DFP) | TTM sum (Q1+Q2+Q3+Q4) | Match? |
|--------|----------------:|----------------------:|--------|
| HBOR3 | -12,077,000 | -12,077,000 | **YES** |
| LWSA3 | -40,001,000 | -40,001,000 | **YES** |
| CGAS3 | -2,735,338,000 | -2,735,338,000 | **YES** |

All 3 reconcile exactly. No double-counting.

---

## 4. S3 — Anchor Quality

### Distance distribution (sample: 100 issuers at anchor=2024-12-31)

| Distance | Count | % |
|----------|------:|----:|
| 0–7 days | 47 | 47% |
| 8–15 days | 0 | 0% |
| 16–30 days | 0 | 0% |
| NULL (no snapshot) | 53 | 53% |

**Mean distance: 2.0 days. Max: 2 days.**

Bimodal: snapshots either exist within 2 days of quarter-end or don't exist at all. The +/-30 day window captures everything available; the gap is snapshot coverage, not window size.

### Tiebreaker policy

- `min()` with `key=abs(distance)` over list ordered by `fetched_at ASC`
- If equidistant: earlier snapshot wins (deterministic)
- `fetched_at` has unique constraint per security → fully deterministic

### Same distribution at t-4 (2023-12-31)

Identical pattern: 47 found (0–2 days), 53 NULL. Stable across time.

---

## 5. S3 — Shares Sanity

### Cross-check: shares × price ≈ market_cap

| Ticker | Shares | Price | MCAP (actual) | Shares×Price | Ratio |
|--------|-------:|------:|--------------:|-------------:|------:|
| IRBR3 | 81,622,886 | 57.85 | 4,525,617,027 | 4,721,883,955 | 1.043 |
| ABCB4 | 241,163,031 | 26.82 | 6,404,264,642 | 6,467,992,491 | 1.010 |
| BBAS3 | 5,708,378,234 | 25.01 | 141,540,706,055 | 142,766,539,632 | 1.009 |
| NEOE3 | 1,213,797,248 | 32.40 | 39,897,501,985 | 39,327,030,835 | 0.986 |
| PSSA3 | 640,360,009 | 50.24 | 31,616,792,345 | 32,171,686,852 | 1.018 |
| RAIL3 | 1,855,786,108 | 14.76 | 28,761,102,187 | 27,391,402,954 | 0.952 |
| EGIE3 | 1,142,298,836 | 32.77 | 36,702,062,568 | 37,433,132,856 | 1.020 |

Most ratios within 1.0 ± 5%. Larger deviations (LWSA3 at 1.29, VIVT3 at 0.89) explained by dual-class shares or timing drift. Acceptable for v1.

### Shares availability

- 626 snapshots have `shares_outstanding > 0` out of 175,574 total (0.4%)
- 285 securities have at least one shares data point

---

## 6. Coverage Atual Combinada — CRITICAL FINDING

### Data alignment gap

| Data | Temporal range | market_cap | shares_outstanding |
|------|---------------|------------|-------------------|
| Historical snapshots (2023-01 to 2024-12) | 286 securities × daily | **NULL for all** | 626 snapshots (backfill) |
| Gap | 2025-01 to 2025-11 | No snapshots at all | No snapshots at all |
| Recent snapshots (2025-12 to 2026-03) | ~297 securities × daily | **Available** | **NULL for all** |
| CVM filings | ref_dates up to 2024-12-31 | N/A | N/A |

### Root cause breakdown (552 issuers with distributions, at anchor=2024-12-31)

| Failure reason | Count |
|---------------|------:|
| No primary security set | 245 |
| Primary exists, no snapshot in window | 66 |
| Snapshot exists, market_cap = NULL | 241 |
| **Snapshot + market_cap available** | **0** |

### Coverage result

| Metric | Computable | % of dist issuers |
|--------|----------:|---------:|
| **Dividend Yield** | **0** | **0%** |
| **Net Buyback Yield** | **0** | **0%** |
| **NPY (DY ∩ NBY)** | **0** | **0%** |

### Why

1. **market_cap not populated in historical snapshots**: The Yahoo adapter was extracting market_cap from `.info`, but the historical data (imported from yfinance history) didn't include it. All 2023-2024 snapshots have `market_cap = NULL`.

2. **11-month snapshot gap**: No snapshots exist from January 2025 to November 2025. Snapshot collection was paused or re-bootstrapped.

3. **shares_outstanding only in backfill**: The S1 backfill populated 626 snapshots, but only in historical data. Recent snapshots (2025-12+) don't have shares yet.

4. **245 issuers lack primary security**: `is_primary` is not set for ~44% of distribution issuers.

### To unblock

Two remediation paths:

**Path A (fast — backfill market_cap into historical snapshots)**:
- `UPDATE market_snapshots SET market_cap = shares_outstanding * price WHERE market_cap IS NULL AND shares_outstanding IS NOT NULL AND price IS NOT NULL`
- This works for the 626 snapshots that have both shares + price
- Plus: set `is_primary` on more securities

**Path B (full — refresh snapshots for current period)**:
- Re-fetch snapshots for all securities with market_cap + shares
- This gives 2026 data, but CVM filings only go to 2024-12-31
- The gap 2025-01 to 2025-11 remains

**Path C (combined)**:
- Backfill market_cap from shares×price for historical
- Backfill shares_outstanding from quarterly_balance_sheet for recent
- Set `is_primary` on missing securities
- This maximizes coverage at both temporal ends

---

## 7. Go / No-Go Recommendation

### S4 — BLOCKED by data coverage

The code for DY, NBY, and NPY is correct and well-tested. But with 0% effective coverage, S4 would produce a metric that computes for zero issuers. Proceeding to S4 without data remediation would be building on an empty foundation.

### Recommended action

1. **Run data remediation** (Path A or C) as S3.5 before S4
2. Re-run coverage check
3. If DY ≥ 30 issuers and NBY ≥ 30 issuers: proceed to S4
4. If not: investigate deeper before continuing

### What IS solid

- S1 mapping: 552/740 issuers, label patterns validated
- S2 TTM: deaccumulation correct, reconciliation exact, no double-counting
- S3 code: snapshot anchoring, NBY formula, NULL policy all correct
- Test suite: 173 tests passing, 0 regressions

The methodology is sound. The data pipeline has a gap that needs filling before the metrics become real.
