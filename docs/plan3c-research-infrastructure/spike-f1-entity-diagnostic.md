# Spike F1 — Entity Linkage Diagnostic Report

## Status: COMPLETE

---

## A. Current State

| Metric | Count |
|--------|------:|
| Total issuers | 741 |
| Issuers with securities | 356 |
| Issuers WITHOUT securities (orphans) | 385 |
| Total securities | 879 |
| Securities with `is_primary=true` | 711 |
| Securities with `valid_to IS NULL` (current) | 879 |
| Securities with `valid_to IS NOT NULL` (superseded) | 0 |
| Issuers with exactly 1 primary | 1 |
| Issuers with 2+ primaries | 355 |
| Issuers with completed filings | 740 |
| Issuers with computed_metrics | 740 |
| Issuers with shareholder_distributions | 552 |

### Security creation timeline

| Date | Securities created | Nature |
|------|-------------------:|--------|
| 2020-01-01 | 439 | Original seed/import |
| 2026-03-09 | 439 | Re-import (identical tickers, no dedup) |
| 2000-01-01 | 1 | Outlier (INDEX) |

### Market snapshot distribution

- Original securities (2020-01-01): **175,574 snapshots**
- Duplicate securities (2026-03-09): **0 snapshots**

### Ticker distribution per issuer (current, deduped)

| Distinct tickers | Issuers |
|-----------------:|--------:|
| 1 | 278 |
| 2 | 72 |
| 3 | 6 |

### Security class column

`security_class` is NULL for 878 of 879 securities. Only 1 record has `security_class = 'INDEX'`. The column was never populated.

---

## B. Data Taxonomy

### B.1 — The "355 multiple primaries" problem

**Root cause: Duplicate import, not dual-class.**

All 355 issuers with "multiple primaries" have the **exact same ticker** duplicated — one record from 2020-01-01 and one from 2026-03-09. These are NOT ON+PN pairs.

Evidence:
- 0 issuers have multiple DISTINCT tickers marked as primary
- The 2026-03-09 set has 0 market snapshots (dead records)
- `is_primary=true` was set blanket on ALL securities

**Resolution**: Delete the 439 duplicate securities from 2026-03-09. This is safe because they have no snapshots.

### B.2 — Real dual-class issuers (ON + PN)

72 issuers have 2 distinct tickers (e.g., PETR3 + PETR4). 6 issuers have 3 (e.g., SANB3 + SANB4 + SANB11).

These are legitimate. They need a **primary selection rule** to pick one security per issuer for metric computation.

Currently, since `is_primary=true` on all, the compat view produces duplicate rows per issuer (one per security). This inflates counts but doesn't corrupt metric values (both securities share the same `computed_metrics` via `issuer_id`).

### B.3 — Orphan issuers (385 without securities)

| Category | Count | Description |
|----------|------:|-------------|
| Likely listed (has distributions) | 235 | Companies paying dividends, probably have B3 tickers |
| SPE/Holding Transport | 30 | Concession SPEs (Autopista, etc.) |
| Securitizadora | 22 | SPVs — structurally no equity ticker |
| SPE/Holding Energy | 20 | Transmission/generation SPEs |
| SPE/Holding Saneamento | 8 | Water/sanitation SPEs |
| Other with filings | 70 | Mixed: some private, some subsidiaries |

**Key insight**: Many "likely listed" orphans are actually **subsidiaries of listed groups**, not independently listed companies. Examples:

- CEMIG DISTRIBUICAO (subsidiary of CEMIG — CMIG3/4)
- COPEL DISTRIBUIÇÃO, COPEL GERAÇÃO E TRANSMISSÃO (subsidiary of COPEL — CPLE3/6)
- ENERGISA MATO GROSSO, PARAÍBA, SERGIPE (subsidiaries of ENERGISA — ENGI3/11)
- EQUATORIAL GOIÁS, MARANHÃO (subsidiaries of EQUATORIAL — EQTL3)
- LIGHT ENERGIA, LIGHT SERVIÇOS (subsidiaries of LIGHT — LIGT3)

These file CVM individually but trade under the parent ticker. They can't get their own security record — they'd need to be linked to the parent's security, which creates a different data model challenge.

**Independently listed orphans** (confirmed B3 tickers): ~20 found by name matching, including Cielo, Marfrig, Movida, Algar Telecom, Alubar, Aura Minerals.

### B.4 — Orphan distribution

| Has distributions? | Likely listed | SPE/Subsidiary | Total |
|--------------------|-------------:|---------------:|------:|
| Yes | ~155 | ~80 | 235 |
| No | ~80 | ~70 | 150 |

Of the ~155 "likely listed" orphans with distributions, many are subsidiaries. Realistic independently-linkable estimate: **50-80 issuers**.

---

## C. Historical Rule Inference

### How `is_primary` was assigned

**There was no primary selection rule.**

Evidence:
1. ALL 879 securities have `is_primary=true`
2. `security_class` is NULL for 878/879 records
3. No evidence of share class logic in the import pipeline
4. The 2026-03-09 import duplicated records without checking for existing securities

**Inference**: The original import (2020-01-01) created one security per ticker found in market data, set `is_primary=true` on all of them, and never set `security_class`. The 2026-03-09 re-import ran the same logic without deduplication.

### How securities were created

The securities were likely created from a market data provider ticker list (yfinance), not from CVM data. Evidence:
- 356 issuers have securities (the ones with yfinance data)
- 385 issuers don't (CVM-only, no market data match)
- This explains the gap perfectly: the import only created securities for tickers it could find on Yahoo

---

## D. Candidate Deterministic Rule

### For duplicate cleanup

**Rule: Keep the security record with market snapshots. Delete the other.**

```sql
-- Delete 2026-03-09 duplicates (0 snapshots, dead records)
DELETE FROM securities WHERE valid_from = '2026-03-09';
```

Safe because: 0 snapshots reference these records. No computed_metrics reference security_id (they use issuer_id).

### For dual-class primary selection

**Rule: Prefer the most liquid class by ticker suffix convention.**

Brazilian market convention:
- PN (suffix 4) is typically more liquid for legacy companies
- ON (suffix 3) is the norm for post-2000 IPOs and corporate governance reforms
- UNIT (suffix 11) is a bundle — prefer the underlying class

**Proposed deterministic rule**:

1. If issuer has only 1 ticker: that's the primary
2. If issuer has multiple tickers:
   a. Pick the ticker with the most market snapshots (proxy for liquidity/data availability)
   b. Tiebreak: prefer suffix 3 (ON) over 4 (PN) over 11 (UNIT)
   c. Record `primary_rule_version = 'v1-snapshot-count'`

**Why snapshot count**: We don't have trading volume history. But snapshot count reflects how consistently the security was tracked, which correlates with liquidity.

### For orphan linkage

**Two distinct populations**:

1. **Independently listed companies** (~50-80): Need ticker lookup (CVM code → B3 ticker mapping or yfinance search by name)
2. **Subsidiaries of listed groups** (~100+): Cannot get their own security. Need a `parent_issuer_id` linkage or remain unlinked.

**Recommendation for 3C.1**: Only link independently listed orphans. Subsidiary linkage is a different data model problem (out of scope for entity hardening).

---

## E. Build Recommendation

### 3C.1 Shape: Entity Hardening

**3 surgical scopes, ordered by impact:**

#### Scope 1: Dedup securities (safe, immediate)

- Delete 439 duplicate securities from 2026-03-09
- Verify 0 snapshots or foreign keys affected
- Result: 1 security per ticker per issuer. Compat view drops from 710 to ~440 rows.
- Risk: LOW

#### Scope 2: Primary selection for dual-class (72 issuers)

- For issuers with multiple distinct tickers: select primary by snapshot count, tiebreak by suffix
- Set `is_primary=false` on non-primary securities
- Populate `security_class` from ticker suffix (3→ON, 4→PN, 5→PNA, 6→PNB, 11→UNIT)
- Record selection rule in a new column or metadata
- Result: Clean 1:1 issuer→primary_security mapping
- Risk: MEDIUM (some edge cases in suffix inference)

#### Scope 3: Orphan linkage (50-80 issuers, ticker lookup)

- For independently listed orphans: attempt CVM code → ticker resolution
- Use yfinance or B3 data to find tickers
- Create security records for confirmed matches
- Result: NPY coverage increase from ~24% to ~35-40%
- Risk: MEDIUM-HIGH (requires external data lookup, manual verification)

### What enters 3C.1

- Scope 1 (dedup) — must-do
- Scope 2 (primary selection) — must-do
- Scope 3 (orphan linkage) — best-effort, gated by data availability

### What stays out of 3C.1

- `issuer_security_map` table (not needed yet — `securities` table with `is_primary` is sufficient)
- `market_panel_pti` (belongs in 3C.2)
- Subsidiary-to-parent linkage (different data model, Plan 3D or beyond)
- `security_class` from CVM FRE (requires new data source)
- Point-in-time enforcement (belongs in 3C.3)

### Risk principal

Scope 3 (orphan linkage) is the riskiest because it requires **external data resolution** (CVM code → ticker). If this blocks, Scopes 1-2 still deliver significant cleanup value.

### Expected coverage after 3C.1

| Metric | Before | After Scope 1+2 | After Scope 1+2+3 |
|--------|-------:|----------------:|--------------------|
| NPY | 176 (23.8%) | 176 (23.8%) | ~230-260 (~31-35%) |
| Compat view rows | 710 | ~440 | ~490-520 |
| Unique primary per issuer | 1/356 | 356/356 | 400-430/741 |

Note: Coverage increase is modest because the biggest gap (245 distribution issuers without securities) is dominated by subsidiaries, not independently listed companies. The structural ceiling remains until subsidiary linkage is addressed.
