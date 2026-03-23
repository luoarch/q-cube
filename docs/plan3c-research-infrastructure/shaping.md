# Plan 3C — NPY Research Dataset & Coverage Infrastructure

## Status: PRD RECEIVED — Awaiting micro-feature decomposition

---

## 1. Objective

Transform NPY from a technically correct metric into a research-grade metric with:

- Scientific reproducibility
- Complete auditability
- Point-in-time consistency
- Sufficient coverage for Q3 ranking usage

Plan 3C does NOT alter the NPY formula.
It improves the data infrastructure that feeds the calculation.

---

## 2. Methodological Principles

### 2.1 Point-in-Time Integrity

All calculations must use only data available up to the reference date.

Example: `reference_date = 2024-12-31` can only use filings published, snapshots available, and shares known up to that date. No future data contamination.

### 2.2 Source Hierarchy

Every input classified by reliability tier:

| Tier | Name | Examples |
|------|------|----------|
| A | Official | CVM ITR/DFP/DFC filings, official share counts from filings |
| B | Market provider | Historical price, provider market_cap, provider shares_outstanding |
| C | Derived | `market_cap = shares * price`, temporal propagation, fills |

**Rule**: Published calculation uses A+B. C enters only when A/B are missing, and must be marked.

### 2.3 Mandatory Provenance

Every value must record:

- `source_tier`
- `source_table`
- `source_row_id`
- `source_timestamp`
- `derivation_rule`
- `dataset_version`

---

## 3. Canonical Entity Objects

### 3.1 issuer_master

Canonical issuer table. Each issuer appears exactly once.

Fields: `issuer_id`, `cvm_code`, `issuer_name`, `sector`, `country`, `is_active`, `created_at`

### 3.2 security_master

Canonical securities table.

Fields: `security_id`, `ticker`, `issuer_id`, `share_class`, `is_primary`, `currency`, `listing_exchange`, `created_at`

### 3.3 issuer_security_map

Explicit linkage table with versioning.

Fields: `issuer_id`, `security_id`, `primary_flag`, `primary_rule_version`, `start_date`, `end_date`

Resolves: ON/PN duplication, primary class changes, mergers, spin-offs.

---

## 4. Deterministic Primary Security Rule

Priority order:

1. Class with highest historical liquidity
2. Class with highest market cap
3. Class with longest trading continuity
4. Documented manual fallback

Each decision recorded with `primary_rule_version` and `primary_rule_score`.

---

## 5. Point-in-Time Market Panel

New table: `market_panel_pti`

Fields: `security_id`, `snapshot_date`, `price`, `shares_outstanding`, `market_cap`, `data_source`, `source_tier`, `snapshot_version`, `created_at`

Rules:
- Snapshots are never overwritten
- Corrections create new version
- History remains intact

---

## 6. NPY Research Panel

Central table of Plan 3C: `npy_research_panel`

Fields:
- `issuer_id`, `security_id`, `reference_date`
- `dividend_yield`, `net_buyback_yield`, `net_payout_yield`
- `dy_source_tier`, `nby_source_tier`, `npy_source_tier`
- `shares_source_tier`, `market_cap_source_tier`
- `filing_ids`, `snapshot_ids`
- `formula_version`, `dataset_version`
- `quality_flag`, `created_at`

This table becomes the official scientific dataset.

---

## 7. Panel Generation Pipeline

Executed per `reference_date`:

```
build_npy_panel(reference_date=2024-12-31)
```

Steps:
1. Select active issuers
2. Resolve primary security
3. Load filings available up to reference_date
4. Extract distributions TTM
5. Load shares snapshots
6. Calculate DY
7. Calculate NBY
8. Compose NPY
9. Classify source tiers
10. Record provenance
11. Save with dataset_version

---

## 8. Dataset Versioning

Each execution generates: `dataset_version = YYYYMMDD_runN`

Example: `npy_dataset_20241231_v1`

If pipeline changes: `npy_dataset_20241231_v2`

Enables: historical replay, version comparison, external audit.

---

## 9. Quality Flags

| Flag | Meaning |
|------|---------|
| A | All inputs Tier A |
| B | Mix of Tier A/B |
| C | Any Tier C present |
| D | Incomplete |

Ranking can decide to use only A+B.

---

## 10. Coverage Expansion Strategy

Plan 3C does NOT inflate coverage artificially. It improves coverage via:

- Issuer-security linkage completion
- Complete historical shares
- Consistent market snapshots
- Correct share class handling

Expected: NPY coverage ~70-85% without weak heuristics.

---

## 11. External Audit

Select 20-30 issuers. For each:
- Open CVM filings
- Extract dividends manually
- Verify shares
- Verify buybacks
- Recalculate NPY
- Compare with dataset

Expected error: < 0.1%.

---

## 12. Scientific Release Gates

| Gate | Criterion |
|------|-----------|
| G11 | Point-in-time integrity: 0 violations |
| G12 | Source tier distribution: Tier A+B >= 70% |
| G13 | Dataset reproducibility: re-execution produces identical results |
| G14 | Manual replication: external audit approved |

---

## 13. Q3 Integration

Only after Plan 3C completion:
- NPY usable in ranking
- Ranking consumes `npy_research_panel`, not compat_view

Before Plan 3C: NPY = experimental metric.

---

## 14. No-Gos

- No new metrics
- No NPY formula changes
- No UI
- No ranking changes
- No manual RI scraping

Focus exclusively on scientific data infrastructure.

---

## 15. Deliverables

Plan 3C is complete when:

1. `issuer_master` consolidated
2. `security_master` consolidated
3. `issuer_security_map` versioned
4. `market_panel_pti` complete
5. `npy_research_panel` generated
6. `dataset_version` published
7. Manual audit report
8. Coverage >= 70%

---

## 16. Build Phases (Tech Lead proposed)

| Phase | Objective |
|-------|-----------|
| F1 | Entity & linkage hardening |
| F2 | Point-in-time market panel |
| F3 | Research panel generation |
| F4 | External replication audit |
| F5 | Scientific release gates |

---

## 17. Current Status

- [x] PRD received from Tech Lead
- [ ] Micro-feature decomposition (F1 is too broad — needs slicing)
- [ ] Current system mapping for Plan 3C
- [ ] Appetite setting
- [ ] Build

**Next action**: Decompose F1 into micro-features following Shape Up discipline.

---

## 18. Pre-Build Analysis (pending)

Before starting F1, need to understand:

1. Current state of `issuers` and `securities` tables (coverage, gaps, duplicates)
2. Which 245 issuers lack securities and why
3. Which 355 issuers have multiple primaries and what share classes exist
4. What data sources are available for resolving linkage (CVM cadastro, B3 data, yfinance)
5. What the `is_primary` column currently means and how it was set
