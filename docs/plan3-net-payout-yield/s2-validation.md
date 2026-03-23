# S2 Validation Note — TTM Engine + Dividend Yield

## Status: VALIDATED

---

## 1. Three Issuers with Full 4-Quarter TTM

### HBOR3 — Paid dividends only in Q2

| Quarter | YTD | Standalone |
|---------|-----|-----------|
| Q1 2024-03-31 | 0.00 | 0.00 |
| Q2 2024-06-30 | -12,077,000 | -12,077,000 |
| Q3 2024-09-30 | -12,077,000 | 0.00 |
| Q4 2024-12-31 (DFP) | -12,077,000 | 0.00 |
| **TTM** | | **-12,077,000** |

Scope: con. Filing types: ITR Q1-Q3, DFP Q4. Deaccumulation correct — Q3 and Q4 are zero because YTD didn't change.

### LWSA3 — Bulk payout in Q4

| Quarter | YTD | Standalone |
|---------|-----|-----------|
| Q1 2024-03-31 | 0.00 | 0.00 |
| Q2 2024-06-30 | 0.00 | 0.00 |
| Q3 2024-09-30 | -1,000 | -1,000 |
| Q4 2024-12-31 (DFP) | -40,001,000 | -40,000,000 |
| **TTM** | | **-40,001,000** |

Scope: con. Classic pattern — company pays almost all dividends in Q4 after annual results.

### CGAS3 — Comgás (high-payout utility)

| Quarter | YTD | Standalone |
|---------|-----|-----------|
| Q1 2024-03-31 | -6,283,000 | -6,283,000 |
| Q2 2024-06-30 | -1,485,602,000 | -1,479,319,000 |
| Q3 2024-09-30 | -2,285,433,000 | -799,831,000 |
| Q4 2024-12-31 (DFP) | -2,735,338,000 | -449,905,000 |
| **TTM** | | **-2,735,338,000** |

Scope: **ind** (no con available — scope fallback exercised). Comgás is a utility with substantial quarterly payouts. TTM = R$ 2.74B.

---

## 2. DFP Prevails Over ITR

No DFP+ITR overlap found in the current dataset for `shareholder_distributions`. All Q4 dates (month=12) have either DFP or ITR, not both.

**Why**: CVM filing rules mean DFP (annual) is filed separately from ITR (quarterly). For Q4, companies file a DFP, not an ITR Q4. The code correctly handles the theoretical overlap via `CASE` priority (`DFP=1, ITR=2`) + `ROW_NUMBER`, but in practice this path isn't exercised for distributions.

This will be more relevant for other canonical keys (DRE, BPA) if TTM is extended.

---

## 3. Scope Fallback (con → ind)

**CGAS3** demonstrates this correctly:

- All 4 quarters have **only `ind`** scope (no `con` available)
- `extract_standalone_quarters(preferred_scope=con)` → tries con, fails, falls back to ind → **SUCCESS**
- All 4 quarters use the same `ind` scope — no mixing

Scope distribution across all distribution lines:
- `con`: 1,368 lines (72%)
- `ind`: 527 lines (28%)
- 5 issuers have only `ind` scope

---

## 4. NULL Case — Incomplete Quarters

**BETP3** has only 3 quarters (Q1, Q3, Q4 — missing Q2):

| Quarter | Available? |
|---------|-----------|
| Q1 2024-03-31 | Yes (0.00) |
| Q2 2024-06-30 | **Missing** |
| Q3 2024-09-30 | Yes (0.00) |
| Q4 2024-12-31 | Yes (0.00) |

`compute_ttm_sum()` → **NULL** (correct). The engine correctly refuses to compute TTM when any quarter is missing.

5 issuers in total have <4 quarters of distribution data.

---

## Summary

| Validation Item | Result |
|----------------|--------|
| 3 issuers with full 4-quarter TTM | HBOR3, LWSA3, CGAS3 — all correct |
| DFP prevails over ITR | No overlap in current data; code handles it via priority |
| Scope fallback con → ind | CGAS3 (ind-only) — fallback works correctly |
| NULL on incomplete quarters | BETP3 (3 quarters) — correctly returns NULL |

## Test counts

- 30 new tests (22 TTM + 8 DY)
- 158 total tests passing, 0 regressions
