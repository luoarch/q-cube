# B-lite — Free-Source Trail Exposure in Asset Detail

## Status: BUILD COMPLETE (API + UI) — Awaiting Tech Lead review

---

## 1. Micro Feature

**Add `payoutYield` section to the asset detail API response with both trails (exact + free-source), sourced exclusively from `computed_metrics`, with distinct field names per trail and `referenceDate` per trail.**

---

## 2. Problem

The free-source trail exists in `computed_metrics` but is invisible to the product. Asset detail shows only the legacy `dividendYield` (computed ad-hoc in the service). No NBY, NPY, or proxy metrics are exposed.

---

## 3. Design

### Response shape

```typescript
payoutYield: {
  exact: {
    referenceDate: "2024-12-31",
    dividendYield: 0.052,
    netBuybackYield: 0.031,
    netPayoutYield: 0.083,
    trail: "exact",
  },
  freeSource: {
    referenceDate: "2024-12-31",
    dividendYield: 0.052,
    nbyProxyFree: 0.034,
    npyProxyFree: 0.086,
    trail: "free-source",
  },
}
```

### Field name separation (B1 fix)

- **Exact trail**: `dividendYield`, `netBuybackYield`, `netPayoutYield`
- **Free trail**: `dividendYield`, `nbyProxyFree`, `npyProxyFree`

Field names are **different per trail**. No shared generic schema. This makes silent substitution structurally impossible — a consumer accessing `netBuybackYield` gets exact, `nbyProxyFree` gets proxy. Never ambiguous.

### referenceDate per trail (B2 fix)

Each trail carries its own `referenceDate`. If exact metrics are at `2024-12-31` and proxy metrics are at `2024-12-31`, both show it. If they ever differ (e.g., different filing lags), the consumer sees the difference.

### Single source of truth: `computed_metrics` (B3 fix)

**All payout metrics** in the `payoutYield` block come from `computed_metrics`. No compat view, no ad-hoc calculation.

### Single anchor date per trail (B1-v3 fix)

Each trail is assembled from **one anchor date only**. No cross-date mixing.

**Algorithm:**

1. Query all 5 metric codes for the issuer from `computed_metrics`
2. For **exact trail**: find the latest `reference_date` where at least one **trail-specific** metric (`net_buyback_yield` or `net_payout_yield`) exists. Then populate the trail using ONLY metrics at that date — including `dividend_yield` at that date if available. If neither NBY nor NPY exact exists at any date, `exact = null`.
3. For **free-source trail**: find the latest `reference_date` where at least one **trail-specific** metric (`nby_proxy_free` or `npy_proxy_free`) exists. Then populate using ONLY that date — including `dividend_yield` at that date if available. If neither proxy metric exists at any date, `freeSource = null`.

**Key rule:** `dividend_yield` participates in a trail's composition but does NOT define a trail's existence. A trail only materializes when its own specific metrics exist.

4. Both trails may resolve to **different anchor dates**. The `referenceDate` field on each trail makes this visible.

```sql
-- Step 1: get all payout metrics for the issuer
SELECT metric_code, value, reference_date
FROM computed_metrics
WHERE issuer_id = :issuer_id
  AND metric_code IN (
    'dividend_yield', 'net_buyback_yield', 'net_payout_yield',
    'nby_proxy_free', 'npy_proxy_free'
  )

-- Step 2 (in code): group by reference_date, pick anchor per trail
```

### Legacy `dividendYield` contract (B2-v3 fix)

The existing top-level `dividendYield` field stays as-is (backward compat, from compat view).

**Contract:**

> `payoutYield` is the canonical analytical payout surface. It sources all values from `computed_metrics` at a single anchor date per trail. The legacy top-level `dividendYield` remains for backward compatibility — it is computed ad-hoc from the compat view and may differ in source, date, or value from `payoutYield.*.dividendYield`. New consumers should prefer `payoutYield`.

### Trail enum (not string)

```typescript
const payoutYieldTrailEnum = z.enum(["exact", "free-source"]);
```

---

## 4. Schema

### shared-contracts: `asset.ts`

```typescript
const payoutYieldTrailEnum = z.enum(["exact", "free-source"]);

const exactPayoutYieldSchema = z.object({
  referenceDate: z.string(),
  dividendYield: z.number().nullable(),
  netBuybackYield: z.number().nullable(),
  netPayoutYield: z.number().nullable(),
  trail: z.literal("exact"),
});

const freeSourcePayoutYieldSchema = z.object({
  referenceDate: z.string(),
  dividendYield: z.number().nullable(),
  nbyProxyFree: z.number().nullable(),
  npyProxyFree: z.number().nullable(),
  trail: z.literal("free-source"),
});

const payoutYieldSchema = z.object({
  exact: exactPayoutYieldSchema.nullable(),
  freeSource: freeSourcePayoutYieldSchema.nullable(),
});

// Add to assetDetailSchema:
payoutYield: payoutYieldSchema.nullable(),
```

### NestJS: `asset.service.ts`

Single query to `computed_metrics` for the 5 metric codes. Group results. Build both trail objects.

---

## 5. Appetite

**Level: XS** — 1 build scope

---

## 6. Boundaries / No-Gos

- Do NOT change the compat view
- Do NOT change ranking
- Do NOT remove or rename existing `dividendYield` top-level field
- Do NOT use proxy as fallback for exact
- Do NOT source `payoutYield` from compat view or ad-hoc calculations
- Do NOT change PIT/backtest

---

## 7. Build Scope

### S1 — Schema + API

**Files:**
- `packages/shared-contracts/src/domains/asset.ts`: Add payout yield schemas
- `apps/api/src/asset/asset.service.ts`: Query `computed_metrics`, build both trails
- Build: `pnpm --filter @q3/shared-contracts build`

**Validation:**

| Check | Pass criteria |
|-------|---------------|
| V1 — Schema | `assetDetailSchema` accepts `payoutYield` with both trail shapes |
| V2 — Exact trail | Issuer with NBY exact → `payoutYield.exact` populated with `referenceDate` |
| V3 — Free trail | Issuer with NBY_PROXY → `payoutYield.freeSource` populated with `referenceDate` |
| V4 — Both trails | Issuer with both → both populated, each with own `referenceDate` |
| V5 — Missing trail | Issuer missing a trail → that trail is `null` |
| V6 — Source | All payout metrics sourced from `computed_metrics`, not compat view |
| V7 — No regression | Existing `dividendYield` top-level field unchanged |
| V8 — Typecheck | `pnpm typecheck` passes |

---

## 8. Close Summary

### Delivered

1. **Schema**: `exactPayoutYieldSchema`, `freeSourcePayoutYieldSchema`, `payoutYieldSchema` added to `shared-contracts/domains/asset.ts`. Distinct field names per trail. `referenceDate` per trail. `trail` as literal enum.
2. **API**: `buildPayoutYield()` in `asset.service.ts` — queries `computed_metrics`, applies single-anchor-date-per-trail rule, DY-does-not-materialize-trail rule.
3. **Contract**: `payoutYield` is the canonical analytical surface. Legacy `dividendYield` top-level remains for backward compat and may differ.

### Trail materialization rule

- **Exact trail**: exists only if `net_buyback_yield` or `net_payout_yield` present at any date
- **Free trail**: exists only if `nby_proxy_free` or `npy_proxy_free` present at any date
- `dividend_yield` participates in composition but does NOT define trail existence
- Each trail uses one anchor date (latest with trail-specific metrics)

### Validation Evidence

| Check | Result |
|-------|--------|
| V1 — Schema | **PASS** — `assetDetailSchema` accepts `payoutYield` with both trail shapes |
| V2 — Exact trail | **PASS** — ABEV3: `exact` populated, referenceDate=2024-12-31, DY/NBY/NPY all present |
| V3 — Free trail | **PASS** — AESB3: `freeSource` populated, referenceDate=2024-12-31, nbyProxyFree=-0.248 |
| V4 — Both trails | **PASS** — ABEV3: both populated, each with referenceDate, NBY exact≈NBY proxy (6th decimal diff) |
| V5 — Missing trail | **PASS** — AESB3 exact=null, AERI3 freeSource=null, ATED3 payoutYield=null (DY alone) |
| V6 — No regression | **PASS** — Legacy `dividendYield` top-level unchanged (ABEV3: same value from both paths) |
| V7 — Typecheck | **PASS** — `pnpm --filter @q3/shared-contracts --filter @q3/api typecheck` clean |
| V8 — Build | **PASS** — `pnpm --filter @q3/api build` clean |

### Runtime test cases (against live DB)

**Case 1 — ABEV3 (exact + free):**
```
exact:      refDate=2024-12-31  DY=0.0176  NBY=0.00137  NPY=0.0190
freeSource: refDate=2024-12-31  DY=0.0176  nbyProxy=0.00137  npyProxy=0.0190
```
Both trails present. Values nearly identical (Yahoo vs CVM differ at 6th decimal).

**Case 2 — AESB3 (free only):**
```
exact:      null
freeSource: refDate=2024-12-31  DY=null  nbyProxy=-0.248  npyProxy=null
```
No exact trail (no Yahoo NBY). Free trail shows dilution. DY null at this date.

**Case 3 — AERI3 (exact only):**
```
exact:      refDate=2024-12-31  DY=0.0  NBY=-0.0012  NPY=-0.0012
freeSource: null
```
No free trail (split-detected, skipped by proxy script). Exact trail shows slight dilution.

**Case 4 — ATED3 (DY only, no trail-specific):**
```
payoutYield: null
```
DY exists but no NBY/NPY exact or proxy → neither trail materializes. **Critical test passes.**

---

## 9. Tech Lead Handoff

### What changed
- `packages/shared-contracts/src/domains/asset.ts`: 3 new schemas + `payoutYield` field on `assetDetailSchema`
- `apps/api/src/asset/asset.service.ts`: `buildPayoutYield()` method, queries `computed_metrics`

### What did NOT change
- Compat view — untouched
- Ranking — untouched
- Legacy `dividendYield` field — untouched
- No proxy used as fallback for exact

### UI delivery

**File:** `apps/web/app/(dashboard)/assets/[ticker]/page.tsx`

Added "Payout Yield" section between key metrics grid and factor analysis:
- Two-column layout when both trails present, single column otherwise
- **EXACT** badge (blue) with referenceDate + DY/NBY/NPY
- **FREE-SOURCE** badge (purple) with referenceDate + DY/NBY Proxy/NPY Proxy
- Labels explicitly differ: "NBY" vs "NBY Proxy", "NPY" vs "NPY Proxy"
- Section only renders when `payoutYield` is non-null
- Follows existing page style patterns (inline styles, MetricCard conventions)

Typecheck: `pnpm --filter @q3/web typecheck` clean.

### Where to start review
1. Schema in `asset.ts` — distinct shapes per trail, literal trail enum
2. `buildPayoutYield()` — trail materialization logic, anchor date selection
3. UI in `assets/[ticker]/page.tsx` — Payout Yield section, labels, layout
4. Contract: `payoutYield` = canonical analytical surface, `dividendYield` top-level = legacy
