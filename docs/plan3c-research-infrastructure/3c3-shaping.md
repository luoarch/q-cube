# 3C.3 — Point-in-Time Integrity + Dataset Governance

## Status: APPROVED — Follow-ups F1-F4 complete

## Goal

Harden point-in-time enforcement for the NPY research panel, formalize dataset
lifecycle governance, and ensure replayability and audit readiness.

## Problem Statement

### PIT violation identified

DY at reference_date=2024-12-31 uses DFP 2024 filing data — but CVM doesn't
publish DFP until ~March of the following year. An investor on 2024-12-31 would
NOT have this data. This is a systemic look-ahead bias.

Quantified: **176 of 178 DY metrics at 2024-12-31 use DFP 2024 data.**

### Root cause

`ttm.load_quarterly_ytd_values()` queries filings by `reference_date` only.
It does not check when the filing was actually available (publication date).
Since CVM filings have a ~90-day publication lag, the TTM computation for any
quarter-end date includes filings from that same quarter that wouldn't be
publicly available yet.

### What "point-in-time" means here

For a research panel row at `reference_date=2024-12-31`:
- **Filings**: only filings with CVM publication date <= 2024-12-31
- **Snapshots**: only snapshots with fetched_at <= 2024-12-31

## Must-fit Scopes

### S1 — CVM publication date estimation

Add `publication_date` (estimated) to filings based on CVM regulatory deadlines:
- DFP: reference_date + 90 days (CVM deadline for annual filings)
- ITR: reference_date + 45 days (CVM deadline for quarterly filings)

Conservative: use deadline as upper bound. Actual publication may be earlier.
This is a derived field, not official CVM data — must be documented as such.

### S2 — PIT-aware TTM computation

Add `knowledge_date` parameter to `compute_ttm_sum()` and downstream:
- Only use filings where `publication_date <= knowledge_date`
- knowledge_date defaults to None (no PIT filter, backward compat)
- Existing non-PIT path preserved for product use

### S3 — PIT-aware research panel builder

Update `build_npy_research_panel()` to:
- Accept `knowledge_date` parameter
- Check PIT compliance of existing computed_metrics against filing publication dates
- Record `pit_mode`, `knowledge_date`, and `pit_compliant` per row

### S4 — Dataset lifecycle governance

Add `npy_dataset_versions` table:
- dataset_version (PK)
- reference_date, knowledge_date, pit_mode (strict/relaxed)
- formula_version, row_count, quality_distribution
- created_at, frozen_at (NULL until frozen)

Builder creates version record. **Frozen versions cannot be rebuilt.**

### S5 — PIT flag in research panel

Add `pit_compliant` boolean to npy_research_panel:
- true = all inputs pass PIT check (filings published + snapshots fetched by knowledge_date)
- false = at least one input uses future data

## Out of scope
- Actual CVM API for real publication dates (use estimates)
- Full historical backfill across all dates
- Parent-subsidiary mapping
- Coverage expansion
- Formula changes
- UI

---

## Validation Evidence

### V1 — PIT Compliance Detection

PIT-mode panel (knowledge_date=2024-12-31):
- **178 PIT compliant** (rows without DY, or with only NBY/snapshots data)
- **178 PIT violations** (rows with DY using DFP 2024, pub_date=2025-03-31)

This correctly identifies the systemic look-ahead bias: DFP 2024 would not
be published until ~March 2025.

### V2 — Dataset Version Governance

- `npy_panel_2024q4_v1` (relaxed): created, 356 rows
- `npy_panel_2024q4_pit_v1` (strict): created, 356 rows, knowledge_date=2024-12-31
- Frozen version rebuild: correctly rejected with ValueError

### V3 — Metric Identity Preserved

NPY = DY + NBY check: **0 mismatches** (unchanged from 3C.2)

### V4 — Backward Compatibility

All 220 tests pass (209 existing + 11 new). TTM and metric computation
work identically when knowledge_date=None (default).

### V5 — Publication Date Backfill

All 2867 filings have publication_date populated:
- DFP 2024-12-31 → pub_date 2025-03-31 (90 days)
- ITR 2024-09-30 → pub_date 2024-11-14 (45 days)

---

## Close Summary

### Delivered

1. **S1 — publication_date on filings**: Migration `20260321_0019`, backfilled 2867 filings
2. **S2 — PIT-aware TTM**: `knowledge_date` parameter on `compute_ttm_sum()`, `compute_dividend_yield()`, `compute_net_buyback_yield()`, `find_anchored_snapshot()`
3. **S3 — PIT-aware builder**: `build_npy_research_panel()` accepts `knowledge_date`, records `pit_compliant` per row
4. **S4 — Dataset governance**: `npy_dataset_versions` table, freeze protection, version metadata
5. **S5 — PIT flag**: `pit_compliant` + `knowledge_date` columns on research panel
6. **Tests**: 11 new PIT tests (quarter dates, publication rules, compliance checks)
7. **Models**: Filing.publication_date, NpyDatasetVersion, NpyResearchPanel.pit_compliant/knowledge_date

### Key Design Decisions

- **PIT check is post-hoc validation, not recomputation**: Builder reads existing computed_metrics and validates their source provenance against knowledge_date. This avoids recomputation divergence.
- **publication_date is estimated**: Uses CVM regulatory deadlines (DFP+90, ITR+45). Documented as derived, not official. Conservative upper bound.
- **Non-PIT path preserved**: knowledge_date=None means no PIT filter. Existing product path unaffected.
- **Frozen versions are immutable**: Attempting to rebuild raises ValueError. This is the governance foundation.

### What This Means Scientifically

The PIT flag answers: "Was this NPY calculated only with information available on the analysis date?"

For `reference_date=2024-12-31` with `knowledge_date=2024-12-31`:
- 178 rows are PIT-**violating** (use DFP 2024 data not yet published)
- 178 rows are PIT-**compliant** (use only ITR data and market snapshots)
- This is a real and important finding for any backtest or academic use

### What 3C.3 Does NOT Solve

- Does not recompute metrics in PIT mode (validates existing ones)
- Does not solve coverage — PIT-strict mode will further reduce usable rows
- Does not provide actual CVM publication timestamps (uses estimates)
- Full PIT recomputation pipeline would be a separate initiative

---

## Follow-Up: Tech Lead Required Items (post-approval)

### F1 — Drizzle Schema Alignment

**Status: DONE**

Added to `apps/api/src/db/schema.ts`:
- `publicationDate` column on `filings` table
- `npyResearchPanel` table (21 columns, FK to issuers + securities, unique constraint)
- `npyDatasetVersions` table (8 columns, PK on dataset_version)

Both ORMs (Drizzle + SQLAlchemy) now mirror the same tables and columns.

### F2 — Formal Date Semantics: `reference_date` vs `knowledge_date`

**Two dates, two meanings.** These must never be conflated:

| Field | Semantics | Example |
|-------|-----------|---------|
| `reference_date` | **Economic cut date.** The date of the financial snapshot being analyzed. Determines which quarter/year the panel describes. | `2024-12-31` = "Q4 2024 panel" |
| `knowledge_date` | **Information availability date.** The date at which the analyst (or system) could have known the data. Only filings with `publication_date <= knowledge_date` and snapshots with `fetched_at <= knowledge_date` are PIT-compliant. | `2024-12-31` = "only data publicly available by year-end" |

**Key rule:** `knowledge_date` can differ from `reference_date`. Common valid combinations:
- `reference_date=2024-12-31, knowledge_date=2024-12-31` — strict real-time PIT (many DFP violations expected)
- `reference_date=2024-12-31, knowledge_date=2025-03-31` — allows DFP 2024 filing lag
- `reference_date=2024-12-31, knowledge_date=None` — relaxed mode, no PIT check (product use)

Both fields are recorded on `npy_research_panel` and `npy_dataset_versions` to ensure full traceability.

### F3 — Official PIT Consumption Policy

**Policy decision:** The official approach is **full dataset with PIT flag + strict-PIT derived view**.

| Output | Contents | Use Case |
|--------|----------|----------|
| **Full panel** (`pit_mode=relaxed` or `strict`) | All rows, `pit_compliant` column present | Product display, coverage analysis, full audit |
| **Strict-PIT subset** | Only rows where `pit_compliant=true` | Backtesting, academic research, scientific validation |

**Rules:**
1. The builder always produces the full panel (never excludes rows based on PIT status)
2. `pit_compliant=false` rows are **flagged, not deleted** — information preservation
3. Consumers (backtests, research exports) filter on `pit_compliant=true` when scientific rigor is required
4. The `npy_dataset_versions.pit_mode` field records whether the build was PIT-aware
5. Frozen datasets cannot be rebuilt — the PIT state at build time is permanent

### F4 — Publication Date: Methodological Note

**`publication_date` on the `filings` table is an estimated regulatory deadline, not an observed event timestamp.**

Estimation rules (v1):
- **DFP (annual):** `reference_date + 90 calendar days` (CVM regulatory deadline)
- **ITR (quarterly):** `reference_date + 45 calendar days` (CVM regulatory deadline)

**What this means:**
- The estimate is a **conservative upper bound** — actual publication may be earlier
- This is sufficient for PIT compliance checking (if a filing wouldn't pass even at the deadline, it certainly wouldn't pass at the actual date)
- The field name `publication_date` is acceptable as v1 shorthand, but any external documentation or research export must note: *"Estimated publication date based on CVM regulatory filing deadlines (DFP+90d, ITR+45d). Not observed from CVM publication timestamps."*

**Future upgrade path:** If/when CVM API or scraping provides actual `published_at` timestamps, those should populate a separate `observed_publication_date` column. The estimated field remains as fallback.
