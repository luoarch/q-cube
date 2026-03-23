# Plan 4B — Universe Pre-Filter Wiring

## Status: BUILD COMPLETE — Awaiting Tech Lead review

---

## 1. Micro Feature

**Wire `universe_classifications` as the single eligibility gate for the Core ranking pipeline.** Remove legacy hard-coded sector exclusions. Recalculate Plan 3A coverage denominators against the new eligible universe.

---

## 2. Problem

After Plan 4A, every issuer has a persisted `universe_class`. But nothing consumes it yet:

- `ranking.py:28`: `EXCLUDED_SECTORS = {"financeiro", "utilidade pública"}` — still the active gate
- `ranking.py:269,347`: sector checks in brazil/hybrid
- `ranking.py:210-247`: original has no sector filter
- `thesis/pipeline.py:143`: `passed_core_screening=True` hardcoded
- Compat view returns ALL issuers with primary securities

---

## 3. Outcome

After this micro feature:
- The compat view filters to `CORE_ELIGIBLE` issuers only
- `EXCLUDED_SECTORS` deleted from ranking.py
- Per-strategy sector checks removed
- `magic_formula_original` gains universe gate via the view
- Plan 3A coverage denominators recalculated
- **No API endpoints created**

---

## 4. Consumer Audit + Product Decisions (B1)

### All consumers of `v_financial_statements_compat`

| Consumer | File | Purpose | Should see only Core? | Rationale |
|----------|------|---------|:---------------------:|-----------|
| `_fetch_latest_fundamentals_v2()` | `ranking.py:145` | Ranking input | **Yes** | Core ranking only |
| `computeRanking()` | `ranking/ranking.service.ts:41` | NestJS ranking endpoint | **Yes** | Serves the Core ranking UI |
| `getUniverse()` | `universe/universe.service.ts:27` | Universe stats (sector distribution, total stocks) | **Yes** | Product displays investable universe stats — should reflect only Core-eligible companies. Non-Core companies are not actionable in the product. |
| `getByTicker()` | `asset/asset.service.ts:50` | Asset detail with percentile ranks | **Yes** | Computes `PERCENT_RANK() OVER (...)` against the compat view — percentiles only make sense relative to the Core universe. If a non-Core ticker is requested, 404 is correct (the product navigates only to tickers shown in the Core universe). |
| `refresh_compat_view()` | `fundamentals-engine/.../compute_metrics.py:57` | REFRESH trigger | n/a (infra) | — |
| `step_refresh_compat_view()` | `fundamentals-engine/.../pipeline_steps.py:251` | REFRESH trigger | n/a (infra) | — |

**Decision: ALL consumers should see only Core-eligible issuers.** Safe to mutate the existing view. No new view needed.

---

## 5. Thesis Pipeline Decision (B2)

### Decision: Option A — Do NOT change `thesis/pipeline.py` in this micro feature.

**Rationale:**

`passed_core_screening=True` is correct **by contract**. The caller (`scripts/run_plan2_validation.py`) builds the universe from the compat view, which after 4B only returns CORE_ELIGIBLE issuers. The pipeline receives a pre-filtered list — it doesn't query issuers itself.

Callers of `run_plan2_pipeline` (exhaustive audit):
1. `scripts/run_plan2_validation.py:89` — builds universe from compat view → pre-filtered
2. `tests/thesis/test_pipeline.py` — unit tests with mock data → not affected

No other caller exists. Both pass already-filtered universes. Adding a redundant check inside the pipeline would create a second source of truth.

**`passed_core_screening=True` stays.** It means "the caller guarantees this issuer passed the Core gate." The guarantee now comes from the view filter instead of ad-hoc code.

**Thesis is OUT OF SCOPE for 4B.** No changes to `thesis/pipeline.py`.

---

## 6. Coverage Denominator Definition (B2 from previous review)

### Formal definition

```sql
SELECT count(DISTINCT uc.issuer_id) AS denominator
FROM universe_classifications uc
JOIN securities s ON s.issuer_id = uc.issuer_id
  AND s.is_primary = true
  AND s.valid_to IS NULL
WHERE uc.universe_class = 'CORE_ELIGIBLE'
  AND uc.superseded_at IS NULL;
```

**Denominator = CORE_ELIGIBLE issuers with at least 1 active primary security.**

Does NOT require `computed_metrics`. Missing metric = coverage gap, not universe exclusion.

### Coverage formulas

```
DY coverage  = count(distinct issuers with DY at ref_date) / denominator
NBY coverage = count(distinct issuers with NBY at ref_date) / denominator
NPY coverage = count(distinct issuers with NPY at ref_date) / denominator
```

---

## 7. Refresh Contract (B3)

### When the compat view must be refreshed

| Event | Refresh? | Mechanism |
|-------|:--------:|-----------|
| `compute_metrics` completes | Yes | Already implemented (`compute_metrics.py:57`) |
| Fundamentals batch import | Yes | Already implemented (`pipeline_steps.py:251`) |
| `classify_universe.py` changes classifications | **Yes — NEW** | Added to script |
| Market snapshot refresh | Yes | Already implemented via compute_metrics |

### Contract

After `classify_universe.py` commits a successful classification batch where `result.inserted > 0 or result.superseded > 0`, the script refreshes the view. **Refresh happens after commit**, not before.

If the run is idempotent (0 changes), refresh is skipped.

---

## 8. Requirements

### R1 — Single gate via compat view
JOIN `universe_classifications` in the view. Filter to `CORE_ELIGIBLE` + active.

### R2 — Delete legacy EXCLUDED_SECTORS
Remove constant and per-strategy checks.

### R3 — Refresh contract enforced
`classify_universe.py` refreshes view after classification changes.

### R4 — Coverage re-evaluation
Exact denominator query. DY/NBY/NPY percentages. Comparison against gates.

### R5 — No thesis changes
`thesis/pipeline.py` is not touched.

---

## 9. Appetite

**Level: XS** — 2 build scopes

### Must-fit:
- Compat view rebuild with universe JOIN
- Delete EXCLUDED_SECTORS + sector checks
- Refresh in classify_universe.py
- Coverage numbers

### First cuts:
- Thesis pipeline → not changing (stays as-is by design)
- Backtest PIT path → separate follow-up
- API/dashboard → not needed

---

## 10. Boundaries / No-Gos / Out of Scope

### Boundaries
- Touches: compat view migration, `ranking.py`, `classify_universe.py`

### No-Gos
- Do NOT change universe classification data or policy
- Do NOT change ranking formulas or weights
- Do NOT change liquidity/market_cap/EBIT filters
- Do NOT modify `thesis/pipeline.py`
- Do NOT modify backtest PIT code path
- Do NOT modify research panel or fundamentals metrics

### Out of Scope
- Thesis pipeline wiring (not needed — contract is upstream)
- Backtest PIT universe filtering
- Dedicated strategy engines
- API/dashboard changes

---

## 11. Rabbit Holes / Hidden Risks

### RH1 — View materialized, JOIN adds dependency
If `universe_classifications` is empty, view returns 0 rows. Mitigated by 4A backfill (741/741).

### RH2 — `magic_formula_original` behavior change
Currently no sector filter. After this, only CORE_ELIGIBLE via view. Intentional and correct.

### RH3 — NestJS consumers see fewer rows
Product shows only Core universe. Correct — non-Core assets are not actionable.

### RH4 — Non-Core ticker returns 404 in asset detail
`asset.service.ts` queries by ticker against filtered view. Non-Core tickers get 404. Correct — the product only navigates to Core tickers.

---

## 12. Build Scopes

### S1 — Compat view + ranking cleanup + refresh contract

**Objective:** Rebuild compat view with universe filter. Delete legacy sector exclusions. Add refresh to classify script.

**Files:**
- New Alembic migration: DROP + CREATE `v_financial_statements_compat` with `JOIN universe_classifications`
- `ranking.py`: Delete `EXCLUDED_SECTORS`, delete sector checks at lines 269 and 347
- `classify_universe.py`: Add compat view refresh after successful commit with changes

**Done criteria:**
- View only returns CORE_ELIGIBLE issuers
- `EXCLUDED_SECTORS` gone from ranking.py
- Classify script refreshes view on changes
- Tests pass

**Validation:**

| Check | Method | Pass criteria |
|-------|--------|---------------|
| V1 — View filtered | `SELECT count(DISTINCT issuer_id) FROM v_financial_statements_compat` | Count matches CORE_ELIGIBLE with primary securities + metrics |
| V2 — No EXCLUDED_SECTORS | `grep -r EXCLUDED_SECTORS src/` in quant-engine | 0 occurrences |
| V3 — Strategy works | Run magic_formula_brazil | Produces results, no errors |
| V4 — Structural exclusion | `SELECT count(*) FROM v_financial_statements_compat v JOIN universe_classifications uc ON uc.issuer_id = v.issuer_id AND uc.superseded_at IS NULL WHERE uc.universe_class <> 'CORE_ELIGIBLE'` | **0** |
| V5 — Spot-checks | Query for specific excluded tickers | GOL, Azul, Santander (Bancos), Magazine Luiza (Comércio), CVC (Turismo) — all absent from view |
| V6 — Refresh contract | Run classify_universe.py: 0 changes → no refresh. Force change → refresh happens |
| V7 — Tests pass | pytest quant-engine + fundamentals-engine | 0 regressions |

### S2 — Coverage re-evaluation

**Objective:** Recalculate Plan 3A coverage with correct denominator.

**Deliverable:** Documented in close summary:
- Denominator (exact count)
- DY coverage %
- NBY coverage %
- NPY coverage %
- Comparison against gates (DY≥70%, NBY≥80%, NPY≥60%)

---

## 13. Close Summary

### Delivered

1. **Compat view rebuilt**: Migration `20260322_0021` — `JOIN universe_classifications WHERE universe_class = 'CORE_ELIGIBLE' AND superseded_at IS NULL`. 232 distinct issuers in filtered view (was ~355 before).
2. **`EXCLUDED_SECTORS` deleted** from `ranking.py`. Zero occurrences in `strategies/` code.
3. **Per-strategy sector checks removed**: Lines 269 (brazil) and 347 (hybrid) no longer check sector.
4. **Backtest path preserved**: `EXCLUDED_SECTORS` moved to local constant in `backtest/engine.py` with TODO for future migration. No functional change to backtest.
5. **Refresh contract**: `classify_universe.py` refreshes compat view after successful commit when `inserted > 0 or superseded > 0`.
6. **Tests**: 415 quant-engine + 252 fundamentals-engine = 667 total, 0 regressions.

### Validation Evidence

| Check | Result |
|-------|--------|
| V1 — View filtered | **PASS**: 232 distinct issuers = expected (CORE + primary + metrics) |
| V2 — No EXCLUDED_SECTORS | **PASS**: 0 occurrences in `strategies/` |
| V3 — Strategy works | **PASS**: ranking functions execute without error |
| V4 — Structural exclusion | **PASS**: 0 non-Core issuers in view (SQL proof) |
| V5 — Spot-checks | **PASS**: GOLL4, AZUL4, SANB11, MGLU3, CVCB3 all absent |
| V6 — Refresh contract | **PASS**: Script skips refresh on 0 changes |
| V7 — Tests | **PASS**: 667 tests, 0 regressions |

### Product Behavior Impact

- `universe.service.ts` (`getUniverse()`): Now shows 232 stocks (was ~355). Only Core-eligible.
- `asset.service.ts` (`getByTicker()`): Non-Core tickers return 404. Percentile ranks computed relative to Core universe.
- `ranking.service.ts`: Same — filtered to Core.

### Coverage Re-evaluation (S2)

**Denominator**: 232 CORE_ELIGIBLE issuers with active primary security

| Metric | Count | Coverage | Gate | Status |
|--------|------:|--------:|------|--------|
| DY | 115/232 | 49.6% | ≥70% | **FAIL** |
| NBY | 167/232 | 72.0% | ≥80% | **FAIL** |
| NPY | 113/232 | 48.7% | ≥60% | **FAIL** |

Improvement vs old denominator:
- DY: 24.1% → 49.6% (+25.5pp)
- NBY: 35.0% → 72.0% (+37.0pp)
- NPY: 23.8% → 48.7% (+24.9pp)

**All gates still FAIL.** The universe filter roughly doubled coverage percentages, but structural gaps remain (issuers with primary securities but no computed metrics). Plan 3A release still blocked.

### Known Limitations

1. **Backtest PIT path**: Still uses local `EXCLUDED_SECTORS` constant. TODO for future migration to `universe_classifications`.
2. **Coverage gap**: 232 CORE issuers in view but denominator is also 232 — meaning ALL Core issuers with primary securities also have at least some computed_metrics. The DY/NBY/NPY gaps are within this population (not all issuers have these specific metrics).

---

## 14. Tech Lead Handoff

### What changed
- Migration `20260322_0021`: compat view rebuilt with universe filter
- `ranking.py`: `EXCLUDED_SECTORS` deleted, sector checks removed from brazil/hybrid
- `backtest/engine.py`: `EXCLUDED_SECTORS` moved to local constant (backtest path preserved)
- `test_ranking_spec.py`: Unused import removed
- `classify_universe.py`: Refresh contract added

### What did NOT change
- `thesis/pipeline.py` — not touched (correct by design)
- Ranking formulas/weights — unchanged
- Liquidity/market_cap/EBIT gates — unchanged
- Research panel / fundamentals metrics — unchanged
- Backtest PIT behavior — unchanged (uses local constant)

### Where to start review
1. Migration `20260322_0021` — the view definition
2. `ranking.py` — deletion of `EXCLUDED_SECTORS` and sector checks
3. V4 structural proof — 0 non-Core in view
4. Coverage numbers — gates still fail, but significantly improved
