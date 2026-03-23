# 3C.2 — Source Tier Tagging + Research Panel MVP

## Status: BUILD COMPLETE — Awaiting Tech Lead review

## Goal

Formalize NPY as a research-grade dataset for the already-linked universe.
No formula changes, no coverage expansion, no compat-view replacement.

## Must-fit Scopes

### S1 — Source-tier derivation rules
Centralized Python module with explicit rules to infer tier per metric component.

### S2 — Research panel table + migration
`npy_research_panel` table keyed by (issuer_id, reference_date, dataset_version).

### S3 — Quality flags
A/B/C/D classification based on tier composition and completeness.

### S4 — Dataset versioning MVP
Deterministic dataset_version identifier. Same inputs = same outputs.

### S5 — Builder command
`build_npy_research_panel()` — idempotent, reads computed_metrics, does not recompute.

## Out of scope
- Parent-subsidiary mapping
- Orphan coverage expansion
- Formula changes
- Ranking integration
- UI
- Replacing compat view

## Source Tier Rules (from provenance analysis)

### Current data reality
- DY: distributions from CVM filings (A) + market_cap from Yahoo/brapi snapshot (B)
- NBY: shares_outstanding from Yahoo/brapi snapshot at t and t-4 (B)
- NPY: pure composition of DY + NBY

### Tier assignment
- `dy_source_tier`: worst(distributions_tier, market_cap_tier)
  - distributions_tier = A if source_filing_ids non-empty, else D
  - market_cap_tier = B if from provider snapshot, C if derived
- `nby_source_tier`: worst(shares_t_tier, shares_t4_tier)
  - shares_tier = B if from provider snapshot, C if derived
- `market_cap_source_tier`: B (provider) or C (derived)
- `shares_source_tier`: B (provider) or C (derived)
- `npy_source_tier`: worst(dy_source_tier, nby_source_tier)

### Quality flags
- A: all components tier A/B, no NULL, all A
- B: mix of A/B, no C, no NULL
- C: any component tier C
- D: NPY is NULL or any critical component missing

---

## Validation Evidence

### V1 — Row Identity
356 rows, 356 unique (issuer_id, reference_date, dataset_version) keys. **PASS**

### V2 — Metric Identity
0 mismatches where NPY != DY + NBY (tolerance 1e-12). **PASS**

### V3 — Tier Correctness

| npy_source_tier | quality_flag | count |
|-----------------|-------------|------:|
| B | B | 176 |
| D | D | 180 |

Sub-tier breakdown for B rows: all have dy=B, nby=B, mcap=B, shares=B. **PASS**

D-quality breakdown:
- 95 rows: dy=D, nby=D (no DY or NBY data)
- 83 rows: dy=D, nby=B (have NBY but not DY — missing distributions TTM)
- 2 rows: dy=B, nby=D (have DY but not NBY — missing shares snapshots)

### V4 — Sample Audit (top 5 NPY)

| Issuer | DY | NBY | NPY | Tier | Quality |
|--------|---:|----:|----:|------|---------|
| SYN PROP & TECH | 0.8980 | 0.0000 | 0.8980 | B | B |
| ALLIED TECNOLOGIA | 0.4173 | -0.0090 | 0.4083 | B | B |
| LOG COMMERCIAL | 0.1657 | 0.1335 | 0.2992 | B | B |
| ELEKTRO REDES | 0.2836 | 0.0000 | 0.2836 | B | B |
| EVEN CONSTRUTORA | 0.2380 | 0.0090 | 0.2469 | B | B |

### V5 — Reproducibility
Two runs with same dataset_version: 356 before, 356 after, **0 diffs**. **PASS**

### Regression Tests
- fundamentals-engine: **209 passed** (184 existing + 25 new), 0 failed

---

## Close Summary

### Delivered
1. **Source tier rules** (`research/source_tiers.py`): SourceTier enum, worst_tier(), derive_dy_tiers(), derive_nby_tiers(), derive_npy_tier()
2. **Quality flags** (`research/quality_flags.py`): QualityFlag enum, assign_quality_flag()
3. **Panel model** (`entities.py`): NpyResearchPanel with 19 fields
4. **Migration** (`20260321_0018`): npy_research_panel table with unique constraint
5. **Panel builder** (`research/panel_builder.py`): build_npy_research_panel() — idempotent, deterministic
6. **Builder script** (`scripts/build_research_panel.py`): CLI entry point
7. **Tests**: 25 new (15 source tier + 10 quality flag)
8. **First panel**: npy_panel_2024q4_v1, 356 rows, 176 quality B, 180 quality D

### Key Design Decisions
- **Builder reads computed_metrics, does NOT recompute** — zero divergence risk
- **Tier C not present in current data** — all market data from providers (B), all CVM data from filings (A)
- **D-quality rows included** — issuers with securities but missing NPY still get a panel row. Incompleteness is preserved, not hidden.
- **Delete + insert idempotency** — same dataset_version always produces identical output
- **formula_version = "npy_v1_dy_plus_nby"** — explicit, versioned, persistent

### What This Enables
- Research-grade NPY dataset separate from product output
- Formal provenance per row
- Dataset reproducibility
- Quality-filtered analysis (e.g., "only quality B rows")
- Foundation for paper/TCC/audit
