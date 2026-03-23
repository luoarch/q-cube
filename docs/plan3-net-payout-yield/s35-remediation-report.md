# S3.5 — Data Remediation Report

## Status: GATE PASSED

---

## Remediation Steps Executed

### Step 1: Backfill market_cap from shares × price

Historical snapshots (2023-2024) had price and shares_outstanding (from S1 yfinance backfill) but no market_cap. Derived `market_cap = shares_outstanding × price`.

- **Updated**: 552 snapshots → initial run
- **Updated**: 84,839 snapshots → after shares propagation
- **Provenance**: Derived value, not provider-native

### Step 2: Backfill shares_outstanding from annual balance_sheet

yfinance `quarterly_balance_sheet` only covers 7 quarters (from 2024-06). For t-4 dates (2023 and earlier), used `yf.Ticker.balance_sheet` (annual), which goes back to 2021.

- **Source**: yfinance annual `balance_sheet["Ordinary Shares Number"]`
- **Updated**: 848 snapshots (one per security per annual date)
- **Provenance**: yfinance annual balance sheet, not quarterly

### Step 3: Backfill shares_outstanding from market_cap / price

Recent snapshots (2025-12+) had market_cap but no shares. Derived `shares = market_cap / price`.

- **Updated**: 30,585 snapshots
- **Provenance**: Derived value, not provider-native

### Step 4: Propagate shares to nearby snapshots

The backfill scripts populated ONE snapshot per security per quarter window, but `find_anchored_snapshot` returns the CLOSEST to quarter-end. Daily snapshots (~40 per window) meant the backfill target and the anchor target could be different snapshots.

Solution: propagate `shares_outstanding` from any populated snapshot to all nearby snapshots of the same security (within 90-day radius, using nearest-neighbor matching).

- **Propagated**: 85,221 snapshots
- **Provenance**: Same as source snapshot (nearest in time)

### Step 5: Derive market_cap for newly-filled snapshots

After shares propagation, many snapshots gained shares but still lacked market_cap. Re-ran `market_cap = shares × price`.

- **Updated**: 84,839 snapshots

---

## Post-Remediation Coverage

| Metric | Before | After | Gate (≥30) |
|--------|-------:|------:|:----------:|
| **DY** | 0 | **178** (32.2%) | **PASSED** |
| **NBY** | 0 | **233** (42.2%) | **PASSED** |
| **NPY (DY ∩ NBY)** | 0 | **176** (31.9%) | **PASSED** |

### DY NULL reasons (374 remaining)

| Reason | Count |
|--------|------:|
| No 4 quarters of distribution data | 184 |
| No primary security (not in securities table) | 156 |
| No snapshot in anchor window | 33 |
| Snapshot has no market_cap | 1 |

### NBY NULL reasons (319 remaining)

| Reason | Count |
|--------|------:|
| No primary security | 245 |
| No snapshot at t | 66 |
| No shares at t-4 | 4 |
| No shares at t | 2 |
| No snapshot at t-4 | 2 |

### Structural ceiling

245 distribution issuers have no entry in the `securities` table at all. These are CVM-only issuers without market data linkage. This is the primary coverage ceiling — fixing it requires creating security records and fetching market data, which is outside Plan 3A scope.

---

## Shares Sanity (post-remediation)

| Quarter-end | Issuers with shares | Issuers with mcap | Total |
|-------------|-------------------:|------------------:|------:|
| 2023-12-31 | 279 | 277 | 286 |
| 2024-03-31 | 281 | 280 | 286 |
| 2024-06-30 | 35 | 35 | 287 |
| 2024-09-30 | 284 | 283 | 287 |
| 2024-12-31 | 285 | 285 | 288 |

Q2 2024 coverage is low (35) because annual balance sheet doesn't align to Q2, and quarterly_balance_sheet starts at Q2 2024 with sparse coverage.

---

## Tiebreaker policy (confirmed)

- `find_anchored_snapshot` returns the snapshot closest to anchor_date
- List ordered by `fetched_at ASC`, `min()` by absolute distance
- If equidistant: earlier snapshot wins
- Deterministic via unique constraint on `(security_id, fetched_at)`

---

## Scripts used

| Script | Purpose |
|--------|---------|
| `scripts/backfill_market_cap.py` | market_cap = shares × price |
| `scripts/backfill_shares_annual.py` | shares from yfinance annual balance_sheet |
| `scripts/s35_data_remediation.py` | Combined remediation + coverage audit |

---

## Go / No-Go

**S4 — APPROVED**

All three gates passed:
- DY ≥ 30 → 178
- NBY ≥ 30 → 233
- NPY ≥ 30 → 176

Test suite: 173 tests passing, 0 regressions.
