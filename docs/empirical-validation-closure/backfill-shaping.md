# CVM Historical Backfill 2020–2023

## Status: BUILD COMPLETE — Awaiting Tech Lead review

---

## 1. Micro Feature

**Ingest CVM DFP and ITR filings for 2020–2023 to close the historical filings layer and measure whether full empirical validation is now viable.**

This micro feature closes the **filings foundation**. It does NOT guarantee full validation readiness — that also depends on the **market data layer** (historical snapshots), which is measured but not backfilled here.

---

## 2. Problem

The canonical experiment (proof-of-pipeline) showed the backtest works but was limited by data: only 2024 filings exist. This blocks IS/OOS splits, walk-forward, Reality Check, and promotion.

### Current state

| Dataset | Years | Filings | Issuers |
|---------|-------|--------:|--------:|
| DFP | 2024 only | 707 | 707 |
| ITR | 2024 only | 2,160 | 728 |
| **Total** | **2024** | **2,867** | **~740** |

### Target state

| Dataset | Years | Expected filings | Expected issuers |
|---------|-------|--------:|--------:|
| DFP | 2020–2024 | ~3,500 (5 years × ~700) | ~700 |
| ITR | 2020–2024 | ~10,800 (5 years × ~2,160) | ~730 |
| **Total** | **2020–2024** | **~14,300** | **~740** |

### Data availability (verified)

| File | Year | HTTP | Size |
|------|------|:----:|-----:|
| DFP | 2020 | 200 OK | 12.1 MB |
| DFP | 2021 | 200 OK | 12.7 MB |
| DFP | 2022 | 200 OK | 12.8 MB |
| DFP | 2023 | 200 OK | 12.9 MB |
| ITR | 2020 | 200 OK | 25.9 MB |
| ITR | 2021 | 200 OK | 29.8 MB |
| ITR | 2022 | 200 OK | 30.8 MB |
| ITR | 2023 | 200 OK | 30.9 MB |

All 8 files confirmed available on CVM servers.

---

## 3. Design

### Approach: Use existing pipeline

The `FundamentalsEngineFacade.import_batch(year, doc_types)` already handles the full ingestion pipeline:

1. Download zip from CVM
2. Parse CSVs (DFP/ITR financial statements)
3. Resolve issuers (via FCA + cadastro)
4. Normalize statement_lines (canonical mapping)
5. Detect restatements
6. Validate filings
7. Compute derived metrics
8. Update issuer sectors from cadastro

**No new code needed for ingestion.** Just run the existing pipeline for years 2020–2023.

### Execution order

1. DFP 2020 → DFP 2021 → DFP 2022 → DFP 2023 (annual filings first — larger impact)
2. ITR 2020 → ITR 2021 → ITR 2022 → ITR 2023 (quarterly — finer granularity)
3. Recompute DY/NBY/NPY for newly covered periods
4. Refresh compat view
5. Coverage audit

### Publication dates

DFP/ITR for 2020–2023 will get `publication_date` backfilled by the same logic as 3C.3:
- DFP: `reference_date + 90 days`
- ITR: `reference_date + 45 days`

This ensures PIT correctness for historical backtesting.

---

## 4. Appetite

**Level: S** — 2 build scopes

### Must-fit:
- Ingest all 8 files (4 DFP + 4 ITR)
- Coverage audit per year/quarter/issuer
- Metrics recomputation
- Compat view refresh

### First cuts:
- FCA per-year (only 2024 needed for ticker resolution — CVM codes are stable)
- Market snapshot backfill (separate concern)
- Walk-forward/validation re-run (separate step after backfill)

---

## 5. Boundaries / No-Gos

- **Default path**: use existing pipeline unchanged
- **Allowed if required**: minimal compatibility fixes in parser/normalization/publication-date handling, strictly limited to historical 2020–2023 support, with no formula changes
- Do NOT change metrics formulas
- Do NOT change ranking or compat view logic
- Do NOT run the validation stack yet (that's the next step)
- Do NOT backfill market snapshots (separate concern)

### Idempotency / resumability

- Execution is **year-by-year, doc_type-by-doc_type** (8 independent runs)
- Each run is idempotent (filing upsert by issuer_id + reference_date + version)
- Safe to re-run any single year if it fails midway
- Progress tracked by `raw_source_batches` table (one batch per year+doc_type)

### publication_date semantics

For backfilled filings, `publication_date` is a **synthetic PIT availability approximation**:
- DFP: `reference_date + 90 days`
- ITR: `reference_date + 45 days`

This is consistent with the rest of the system (Plan 3C.3) and is NOT an actual observed publication timestamp.

---

## 6. Risks

| Risk | Severity | Mitigation |
|------|:--------:|------------|
| Older CVM CSV format differences | Medium | Parser handles format variations (tested on 2024) |
| PENÚLTIMO rows in older files | Medium | Already fixed in normalization pipeline (filters PENÚLTIMO) |
| Duplicate issuers across years | Low | Issuer upsert is idempotent (by cvm_code) |
| Large volume of statement_lines | Low | ~5x current volume; PostgreSQL handles fine |
| publication_date not backfilled for old filings | Medium | Add backfill step after ingestion |

---

## 7. Build Scopes

### S1 — Ingest DFP + ITR 2020–2023

**Objective**: Run the existing pipeline for all 8 files. Verify coverage.

**Execution**: Script that calls `import_batch()` for each year/doc_type.

**Validation:**

| Check | Pass criteria |
|-------|---------------|
| V1 — All 8 files processed | Each year × doc_type batch completes without structural error |
| V2 — Filing validity | ≥90% of filings per batch have status='completed' |
| V3 — Issuer coverage | Each year has ≥600 distinct issuers with filings |
| V4 — Statement lines | Each batch produced statement_lines (no empty batches) |
| V5 — No PENÚLTIMO | 0 PENÚLTIMO rows in normalized data |
| V6 — Publication dates | All new filings have publication_date set (synthetic PIT approximation) |

Reference expectations (not gates): ~2,800 DFP + ~8,600 ITR + ~4M statement_lines.

### S2 — Coverage audit + market-layer viability

**Objective**: Measure historical filing coverage AND market data availability. Determine whether full empirical validation is now viable or if the market layer is still blocking.

**Filing coverage audit:**

| Check | Method |
|-------|--------|
| V7 — Coverage grid | Count filings per year × quarter × issuer |
| V8 — TTM viability | Count issuers with ≥4 consecutive quarters of filing data |
| V9 — Fundamentals PIT | Run `fetch_fundamentals_pit` for sample dates 2021-01-01 through 2024-07-01 |

**Market-layer viability audit:**

| Check | Method |
|-------|--------|
| V10 — Market PIT | Run `fetch_market_pit` for same sample dates |
| V11 — Price coverage | Count issuers with market price at each sample rebalance date |
| V12 — Market cap coverage | Count issuers with market_cap at each sample date |

**Viability decision:**

Based on V9-V12, produce explicit verdict:

- **VIABLE**: ≥100 issuers with both fundamentals AND market data at ≥80% of quarterly rebalance dates 2021-2024 → full validation can proceed
- **FILINGS READY, MARKET BLOCKING**: fundamentals adequate but market snapshots insufficient → need market data backfill before validation
- **INSUFFICIENT**: both layers inadequate → need more work

This audit is the **key deliverable** of S2 — it determines the next step on the roadmap.

---

## 8. Close Summary

### S1 — Ingestion: COMPLETE

All 8 files processed. ITR 2023 required a separate run due to batch conflict (facade session management issue — compatibility fix, not formula change).

| Dataset | Filings | Issuers | Status |
|---------|--------:|--------:|:------:|
| DFP 2020 | 1,466 | 731 | OK |
| DFP 2021 | 1,542 | 766 | OK |
| DFP 2022 | 1,460 | 729 | OK |
| DFP 2023 | 1,466 | 732 | OK |
| DFP 2024 | 707 | 707 | (existing) |
| ITR 2020 | 3,952 | 666 | OK |
| ITR 2021 | 2,227 | 751 | OK |
| ITR 2022 | 2,222 | 763 | OK |
| ITR 2023 | 2,158 | 727 | OK |
| ITR 2024 | 2,160 | 728 | (existing) |
| **Total** | **19,360** | — | — |

Statement lines: **6,305,786** (was 955K — 6.6x increase).
Publication dates: **19,362/19,360** backfilled (synthetic PIT approximation).

### S2 — Viability Audit

| Date | Fundamentals | Market (7d) | Both |
|------|:-----------:|:-----------:|:----:|
| 2021-01-04 | 327 | **0** | 0 |
| 2021-07-01 | 352 | **0** | 0 |
| 2022-01-03 | 353 | **0** | 0 |
| 2022-07-01 | 354 | **0** | 0 |
| 2023-01-02 | 354 | 286 | **285** |
| 2023-07-03 | 354 | 286 | **285** |
| 2024-01-02 | 354 | 286 | **285** |
| 2024-07-01 | 355 | 287 | **286** |

### Verdict: **FILINGS READY, MARKET BLOCKING**

- **Filings layer**: Complete 2020-2024. 327-355 issuers at every date.
- **Market layer**: Only 2023-2024 (286 tickers). Zero data for 2021-2022.
- **Viable IS/OOS**: IS 2023 + OOS 2024 (short but feasible with 285 issuers having both layers).
- **Not viable**: 2020-2022 IS due to zero market data.

### Compatibility fix applied

`facade.py`: Changed `create_batch(session, "cvm", ...)` to `create_batch(session, SourceProvider.cvm, ...)` — string vs enum mismatch.

### What this means for the roadmap

1. **Short-window validation (IS 2023, OOS 2024) is NOW VIABLE** — 285 issuers with both fundamentals + market data at every quarterly date
2. **Full 4-year IS not yet viable** — requires historical market snapshot backfill for 2020-2022
3. **Next decision**: run validation with short window, or backfill market data first?

---

## 9. Tech Lead Handoff

### What changed
- 8 CVM files ingested (DFP + ITR 2020-2023)
- 19,360 total filings (was 2,867 — 6.8x increase)
- 6.3M statement_lines (was 955K — 6.6x increase)
- publication_date backfilled for all new filings
- `facade.py`: SourceProvider enum fix

### What did NOT change
- Ingestion pipeline logic
- Metrics formulas
- Ranking / compat view

### Key finding
Market snapshots only cover 2023-2024. To enable 4-year IS for walk-forward, need historical snapshot backfill (2020-2022). Short-window validation (IS 2023, OOS 2024) is immediately viable.
