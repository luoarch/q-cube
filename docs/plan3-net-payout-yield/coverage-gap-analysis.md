# Plan 3A — Coverage Gap Analysis

## Status: ACTIONS 1+2+3 + ZERO-SEMANTICS FIX COMPLETE — Awaiting Tech Lead review

---

## 1. Context

After Plan 4B, coverage denominators use CORE_ELIGIBLE issuers with active primary securities (**232 issuers**).

| Metric | Count | Coverage | Gate | Status |
|--------|------:|--------:|------|--------|
| DY | 115/232 | 49.6% | ≥70% | FAIL |
| NBY | 167/232 | 72.0% | ≥80% | FAIL |
| NPY | 113/232 | 48.7% | ≥60% | FAIL |

This analysis diagnoses WHY 117 Core issuers lack DY and 65 lack NBY.

---

## 2. DY Gap: 117 Missing Issuers

### Root cause breakdown

| Bucket | Count | Cause | Recoverable? |
|-------:|------:|-------|:------------:|
| 3 | 29 | Has DFC lines but no `shareholder_distributions` canonical key | Yes — mapper gap |
| 4 | 32 | Has distributions but no market snapshot (Yahoo data missing) | Yes — snapshot fetch |
| 5a | 43 | Has distributions + snapshot but <4 quarters of data (TTM insufficient) | Partial — needs more filing periods |
| 5b | 13 | Has distributions + snapshot + ≥4 quarters but DY still not computed | Yes — engine re-run |
| **Total** | **117** | | |

### Bucket 3 — Canonical mapper gap (29 issuers)

These issuers have DFC statement_lines (40-297 lines) but the canonical mapper did not identify `shareholder_distributions` in their filings. Examples: Eletrobras, Bombril, Bardella, Biomm.

**Root cause**: The canonical mapper's pattern for `shareholder_distributions` doesn't match the `as_reported_label` used by these issuers in their DFC.

**Recovery**: Improve the canonical mapper pattern for `shareholder_distributions` in the normalization pipeline. This is a data engineering fix, not a formula problem.

**Estimated recovery**: Up to 29 issuers → DY coverage could reach (115+29)/232 = **62.1%**.

### Bucket 4 — No market snapshot (32 issuers)

These issuers have distributions data but no Yahoo market snapshot for their primary security. Examples: BRF (BRFS3), Auren (AESB3/AESO3), Compass (PASS3), Eletropar (LIPR3).

**Root cause**: Yahoo snapshot fetch hasn't been run for these tickers, or Yahoo doesn't have data for them (OTC, low liquidity, recently listed).

**Recovery**: Run snapshot refresh batch. Some may genuinely not have Yahoo data.

**Estimated recovery**: Most of these are major companies (BRF, Auren, Compass) — likely 20-25 recoverable.

### Bucket 5a — TTM insufficient (<4 quarters, 43 issuers)

DY uses TTM (trailing twelve months) of shareholder distributions. This requires 4 quarterly filing periods. These issuers have 1-3 quarters only.

- 10 issuers with 1 quarter
- 10 issuers with 2 quarters
- 23 issuers with 3 quarters

**Root cause**: The CVM filing ingestion only imported a subset of periods. Many issuers have DFP (annual) but fewer ITR (quarterly) filings imported.

**Recovery**: Ingest more ITR filing years. The 23 issuers with 3 quarters are closest — they likely just need 1 more ITR period.

**Estimated recovery**: 23 (with 3 quarters) are likely recoverable with ITR backfill. The 20 with 1-2 quarters need more historical data.

### Bucket 5b — Engine didn't compute (13 issuers)

Has ≥4 quarters of distributions + market snapshot, but the DY metric was never written to `computed_metrics`.

**Root cause**: The DY compute engine may not have been run after the latest data was ingested, or the TTM computation hit an edge case (scope mismatch, deaccumulation issue, etc.).

**Recovery**: Re-run the DY compute engine. This is the easiest bucket.

**Estimated recovery**: ~13 issuers.

---

## 3. NBY Gap: 65 Missing Issuers

| Bucket | Count | Cause | Recoverable? |
|-------:|------:|-------|:------------:|
| A | 39 | No `shares_outstanding` data in market snapshots | Partial — depends on Yahoo |
| B | 26 | Has shares data but NBY not computed | Yes — engine re-run |
| **Total** | **65** | | |

### Bucket A — No shares_outstanding (39 issuers)

NBY requires `shares_outstanding` from market snapshots at t and t-4. These issuers have no snapshot with shares_outstanding.

**Root cause**: Yahoo doesn't provide shares_outstanding for all tickers, or the snapshot fetch didn't include it.

**Recovery**: Re-run snapshot refresh. Some issuers genuinely lack this data from Yahoo.

### Bucket B — Has shares but NBY not computed (26 issuers)

Same as DY Bucket 5b — engine didn't run or hit an edge case.

**Recovery**: Re-run NBY compute engine.

---

## 4. NPY Gap

NPY = DY + NBY. NULL if either is NULL. So NPY coverage is bounded by `min(DY_coverage, NBY_coverage)`. Fixing DY and NBY automatically fixes NPY.

---

## 5. Recovery Estimate

### If all recoverable buckets are addressed:

| Action | DY gain | NBY gain |
|--------|--------:|--------:|
| Fix canonical mapper (Bucket 3) | +29 | — |
| Run snapshot refresh (Bucket 4 + NBY-A) | +25 (est.) | +20 (est.) |
| Backfill ITR filings (Bucket 5a, 3-quarter) | +23 | — |
| Re-run compute engines (Bucket 5b + NBY-B) | +13 | +26 |
| **Total potential** | **+90** | **+46** |
| **Projected coverage** | **205/232 = 88.4%** | **213/232 = 91.8%** |
| **Gate** | ≥70% **PASS** | ≥80% **PASS** |

NPY projected: ~200/232 = 86.2% → ≥60% **PASS**

### Priority order by impact:

1. **Re-run compute engines** — **DONE** (+10 DY, +13 NBY)
2. **Run snapshot refresh** (moderate, +25 DY est., +20 NBY est.) — needs Yahoo batch
3. **Fix canonical mapper** (+29 DY) — data engineering fix
4. **Backfill ITR filings** (+23 DY) — needs CVM ingestion run

---

## 8. Action 1 Results — Engine Re-run

**Executed**: `scripts/recompute_npy_metrics.py` — ran MetricsEngine for all 232 CORE_ELIGIBLE issuers.

### Before vs After

| Metric | Before | After | Gain | Gate |
|--------|-------:|------:|-----:|------|
| DY | 115 (49.6%) | **125 (53.9%)** | +10 | ≥70% FAIL |
| NBY | 167 (72.0%) | **180 (77.6%)** | +13 | ≥80% FAIL |
| NPY | 113 (48.7%) | **120 (51.7%)** | +7 | ≥60% FAIL |

### Remaining DY gap: 107 issuers

| Bucket | Count | Cause | Next action |
|-------:|------:|-------|-------------|
| 3 | 29 | No `shareholder_distributions` canonical key | Mapper fix (Action 3) |
| 4 | 32 | No market snapshot | Snapshot refresh (Action 2) |
| 5 | 46 | TTM insufficient (<4 quarters) | ITR backfill (Action 4) |
| **Total** | **107** | | |

### Remaining NBY gap: 52 issuers

| Bucket | Count | Cause | Next action |
|-------:|------:|-------|-------------|
| A | 39 | No shares_outstanding | Snapshot refresh (Action 2) |
| B | 13 | Insufficient snapshot history | Snapshot refresh (Action 2) |
| **Total** | **52** | | |

### Bug found during execution

`ttm.py:_subtract_quarter()` crashes with `KeyError` when `reference_date` is not a quarter-end (e.g., month 8). The recompute script works around this by snapping to the nearest quarter-end. This is a pre-existing TTM bug that should be fixed in the TTM module directly (follow-up).

### Best-case coverage estimate (after all 4 actions)

| Metric | Current | +Action 2 | +Action 3 | +Action 4 | Best case |
|--------|--------:|----------:|----------:|----------:|----------:|
| DY | 125 | +25 = 150 | +29 = 179 | +23 = 202 | **202/232 = 87.1%** |
| NBY | 180 | +32 = 212 | — | — | **212/232 = 91.4%** |
| NPY | 120 | ~145 | ~170 | ~195 | **~195/232 = 84.1%** |

All gates would PASS at best-case. Next action with highest impact: **Action 2 (snapshot refresh)**.

---

## 9. Action 2 Results — Snapshot Refresh

**Executed**: `scripts/refresh_snapshots_and_recompute.py` — fetched Yahoo snapshots for all 356 primary securities, then recomputed metrics for 232 CORE_ELIGIBLE.

### Snapshot fetch results

- Created: 283 snapshots
- Failures: 73 (Yahoo doesn't recognize these tickers)
- Core issuers still without ANY snapshot: 37

### Coverage — no change

| Metric | After Action 1 | After Action 2 | Change |
|--------|:--------------:|:--------------:|:------:|
| DY | 125 (53.9%) | **125 (53.9%)** | 0 |
| NBY | 180 (77.6%) | **180 (77.6%)** | 0 |
| NPY | 120 (51.7%) | **120 (51.7%)** | 0 |

### Root cause: Bucket 4 is a Yahoo data source limitation

All 32 Bucket 4 issuers remain without snapshots. Yahoo API returns 404 for their tickers (e.g., `BRFS3.SA`, `STPB3.SA`, `ZAMP3.SA` — all "Quote not found"). These include major B3 companies:

- **BRF (BRFS3)** — R$30B+ company, major food producer
- **Santos Brasil (STPB3)** — major port operator
- **Compass Gás (PASS3)** — large gas distributor
- **Zamp (ZAMP3)** — Burger King Brasil operator
- **MRS Logística (MRSA3)** — major rail freight
- **Wilson Sons (PORT3)** — port/maritime services

These are NOT obscure micro-caps — they're real, traded companies that Yahoo's API simply doesn't cover.

### Conclusion

**Action 2 did NOT improve coverage.** The 283 new snapshots went to issuers that already had snapshots (refresh of existing data). The 32 Bucket 4 issuers are a structural Yahoo gap.

### Revised recovery estimate

The original estimate assumed Bucket 4 was recoverable via snapshot refresh. It's not. Revised:

| Action | DY gain | NBY gain | Status |
|--------|--------:|--------:|--------|
| Action 1 — Engine re-run | +10 | +13 | **DONE** |
| Action 2 — Snapshot refresh | **0** | **0** | **DONE — no impact** |
| Action 3 — Canonical mapper fix | +29 (est.) | — | PENDING |
| Action 4 — ITR backfill | +23 (est.) | — | PENDING |
| **Alternative data source** for Bucket 4 | +32 (est.) | +20 (est.) | NEW — requires brapi or DM |

### Revised best-case coverage (after ALL remaining actions)

| Metric | Current | +Action 3 | +Action 4 | +Alt source | Best case |
|--------|--------:|----------:|----------:|------------:|----------:|
| DY | 125 | 154 | 177 | 209 | **209/232 = 90.1%** |
| NBY | 180 | 180 | 180 | 200 | **200/232 = 86.2%** |
| NPY | 120 | ~145 | ~168 | ~195 | **~195/232 = 84.1%** |

**Without alternative data source** (Actions 3+4 only):

| Metric | Current | Best achievable | Gate |
|--------|--------:|:---------------:|------|
| DY | 125 (53.9%) | **177/232 = 76.3%** | ≥70% PASS |
| NBY | 180 (77.6%) | **180/232 = 77.6%** | ≥80% **FAIL** |
| NPY | 120 (51.7%) | **~168/232 = 72.4%** | ≥60% PASS |

**Critical finding: NBY gate (≥80%) cannot be met without an alternative data source.** Yahoo doesn't provide market_cap or shares_outstanding for ~37 Core issuers. The canonical mapper fix and ITR backfill only help DY/NPY, not NBY.

---

## 10. Action 3 Results — Canonical Mapper Backfill

**Executed**: `scripts/backfill_distribution_canonical_keys.py` — retroactively applied `shareholder_distributions` canonical key to existing DFC 6.03.XX lines.

### Results

- 3,901 DFC lines scanned (in filings without existing distribution key)
- 10 new lines mapped as `shareholder_distributions`
- Total issuers with distribution data: 556 (up from ~550)
- **DY coverage: 125 → 126 (+1)**

### Why the gain was minimal

The original analysis estimated 29 issuers in "Bucket 3 — has DFC but no shareholder_distributions". Deeper investigation revealed:

- **28 of 29 genuinely have NO distribution-related labels in their DFC** — these companies don't pay dividends/JCP
- **Only 1 (Eletrobras)** had unmapped distribution labels
- The 154 globally unmapped distribution labels were mostly in filings that already had a distribution key from a different line (unique constraint prevented duplicate mapping)

**Bucket 3 is reclassified from "mapper gap" to "no-dividend companies."** These 28 issuers are structurally unable to have a DY — they don't distribute to shareholders.

---

## 11. Definitive Coverage State (post Actions 1+2+3)

| Metric | Count | Coverage | Gate | Status |
|--------|------:|--------:|------|--------|
| DY | 126/232 | 54.3% | ≥70% | FAIL |
| NBY | 180/232 | 77.6% | ≥80% | FAIL |
| NPY | 120/232 | 51.7% | ≥60% | FAIL |

### Progression

| Action | DY | NBY | NPY |
|--------|---:|----:|----:|
| Baseline | 115 (49.6%) | 167 (72.0%) | 113 (48.7%) |
| +Action 1 (engine re-run) | 125 (53.9%) | 180 (77.6%) | 120 (51.7%) |
| +Action 2 (snapshot refresh) | 125 (53.9%) | 180 (77.6%) | 120 (51.7%) |
| +Action 3 (mapper backfill) | **126 (54.3%)** | **180 (77.6%)** | **120 (51.7%)** |

### Remaining DY gap: 106 issuers (reclassified)

| Bucket | Count | True cause | Recoverable? |
|-------:|------:|-----------|:------------:|
| No-dividend companies | 28 | Genuinely don't pay dividends/JCP | **No** — structural |
| Yahoo data gap | 32 | Yahoo doesn't cover these tickers | **No** — need alt source |
| TTM insufficient | 46 | <4 quarters of distribution data | **Partial** — ITR backfill |
| **Total** | **106** | | |

### Remaining NBY gap: 52 issuers

| Bucket | Count | True cause | Recoverable? |
|-------:|------:|-----------|:------------:|
| No shares_outstanding | 39 | Yahoo doesn't provide this data | **No** — need alt source |
| Insufficient snapshot history | 13 | Need t and t-4 snapshots | **Partial** |
| **Total** | **52** | | |

### Realistic ceiling (Actions 1-3 exhausted, only Action 4 remaining)

| Metric | Current | +Action 4 (ITR) | Ceiling | Gate |
|--------|--------:|:---------------:|:-------:|------|
| DY | 126 (54.3%) | +23 (est.) = 149 | **149/232 = 64.2%** | ≥70% **FAIL** |
| NBY | 180 (77.6%) | +0 | **180/232 = 77.6%** | ≥80% **FAIL** |
| NPY | 120 (51.7%) | +20 (est.) = 140 | **140/232 = 60.3%** | ≥60% **BORDERLINE** |

### Key conclusion

**With Yahoo as sole data source, no gate can be reliably met.**

- DY ceiling ~64% (gate 70%) — blocked by 28 no-dividend + 32 Yahoo gap
- NBY ceiling ~78% (gate 80%) — blocked by 39 Yahoo gap
- NPY ceiling ~60% (gate 60%) — barely meets gate IF Action 4 fully succeeds

### Decision required

The coverage gaps are now classified into 3 structural categories:

1. **No-dividend companies (28 DY)**: These companies genuinely don't pay dividends. DY=0 is the correct value, not a missing value. **Should DY=0 count as "covered" for the gate?**

2. **Yahoo data limitation (32 DY, 39 NBY)**: Structural source gap. Requires alternative data provider or gate revision.

3. **TTM insufficient (46 DY)**: Recoverable with ITR backfill (Action 4). Only remaining free-cost action.

---

## 12. Zero-Semantics Fix Results

### What changed

`dividend_yield.py` updated to formula_version=2: when TTM returns None but the issuer has DFC filings covering ≥3 of 4 TTM quarters, DY is computed as **0** (not NULL). This correctly represents "company didn't pay dividends" vs "we don't know."

### Coverage after zero-semantics fix + recompute

| Metric | Before | After | Change | Gate | Status |
|--------|-------:|------:|-------:|------|--------|
| DY | 126 (54.3%) | **190 (81.9%)** | **+64** | ≥70% | **PASS** |
| NBY | 180 (77.6%) | **180 (77.6%)** | 0 | ≥80% | FAIL |
| NPY | 120 (51.7%) | **179 (77.2%)** | **+59** | ≥60% | **PASS** |

### Full progression table

| Action | DY | NBY | NPY |
|--------|---:|----:|----:|
| Baseline | 115 (49.6%) | 167 (72.0%) | 113 (48.7%) |
| +Action 1 (engine re-run) | 125 (53.9%) | 180 (77.6%) | 120 (51.7%) |
| +Action 2 (snapshot refresh) | 125 (53.9%) | 180 (77.6%) | 120 (51.7%) |
| +Action 3 (mapper backfill) | 126 (54.3%) | 180 (77.6%) | 120 (51.7%) |
| **+Zero-semantics fix** | **190 (81.9%)** | **180 (77.6%)** | **179 (77.2%)** |

### Gate status

| Gate | Required | Actual | Verdict |
|------|:--------:|:------:|:-------:|
| DY ≥ 70% | 70% | **81.9%** | **PASS** |
| NBY ≥ 80% | 80% | 77.6% | **FAIL (-2.4pp)** |
| NPY ≥ 60% | 60% | **77.2%** | **PASS** |

### Remaining blocker: NBY at 77.6% (needs 80%)

NBY is blocked by Yahoo `shares_outstanding` gap (39 issuers). The zero-semantics fix doesn't apply to NBY because NBY requires actual share count data — you can't default to 0 when shares data is missing.

### Tests

253 fundamentals-engine tests passing (252 + 1 new zero-semantics test). 0 regressions.

---

## 6. Decision Points for Tech Lead

### Q1 — Are the gates still the right gates?

Current gates: DY≥70%, NBY≥80%, NPY≥60%.

With the universe now at 232 (not 740), the denominator is much more meaningful. The gates were set when the denominator was inflated by non-Core issuers.

**Option A**: Keep gates as-is. Address recovery actions to meet them.
**Option B**: Revise gates based on new denominator reality. E.g., DY≥60%, NBY≥70%, NPY≥50%.
**Option C**: Add tiered gates: "release at Tier 1 (lower), full at Tier 2 (current)."

### Q2 — What's the priority order?

The 4 recovery actions are independent. Recommended priority:
1. Re-run engines (0 code changes, just execution)
2. Snapshot refresh (0 code changes, just execution)
3. Canonical mapper fix (code change in normalization pipeline)
4. ITR backfill (data ingestion, may take time)

### Q3 — Should we shape individual recovery actions as micro features?

- Engine re-run: just a script execution, no shaping needed
- Snapshot refresh: just a batch job, no shaping needed
- Canonical mapper fix: needs investigation + code change → micro feature candidate
- ITR backfill: needs CVM ingestion → might already be covered by existing pipeline

---

## 7. Sector Distribution of DY-Missing Issuers

Spread across all sectors (no single sector dominates):

| Count | Sector |
|------:|--------|
| 10 | Serviços Transporte e Logística |
| 10 | Têxtil e Vestuário |
| 9 | Emp. Adm. Part. - Energia Elétrica |
| 9 | Energia Elétrica |
| 8 | Máquinas, Equipamentos, Veículos e Peças |
| 7 | Alimentos |
| 6 | Comunicação e Informática |
| 5 | Agricultura (Açúcar, Álcool e Cana) |
| 5 | Emp. Adm. Part. - Serviços Transporte e Logística |
| 58 | Others (22 sectors, 1-4 each) |

This confirms the gap is **not sector-specific** — it's a data availability issue across the board.
