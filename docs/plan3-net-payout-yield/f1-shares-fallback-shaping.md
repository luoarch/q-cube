# F1A — NBY_PROXY_FREE via CVM Composição do Capital

## Status: APPROVED — Build complete

---

## 1. Micro Feature

**Create `NBY_PROXY_FREE` metric using share counts from CVM DFP/ITR `composicao_capital` CSVs.** This is a free, CVM-official data source that provides total shares and treasury shares per issuer per quarter — exactly what NBY needs.

---

## 2. Problem

NBY coverage is 180/232 (77.6%). Gate is ≥80% (needs ≥186). Gap: **6 issuers.**

The gap exists because Yahoo doesn't provide `shares_outstanding` for 37 Core issuers. Investigation proved that no free Yahoo endpoint covers them.

### Discovery: CVM `composicao_capital`

CVM DFP/ITR zips contain `composicao_capital` CSVs with:

| Field | Content |
|-------|---------|
| `QT_ACAO_TOTAL_CAP_INTEGR` | Total shares (integrated capital) |
| `QT_ACAO_TOTAL_TESOURO` | Treasury shares |
| `CNPJ_CIA` | Company CNPJ |
| `DT_REFER` | Reference date (quarter-end) |

**Net shares = total - treasury.**

### Coverage proof

| Dataset | Companies | Dates | NBY-missing coverage |
|---------|----------:|-------|:--------------------:|
| DFP 2024 | 707 | 2024-12-31 | **33/37** NO_SNAP issuers |
| ITR 2024 | 728 | Q1-Q3 2024 | **37/37** NO_SNAP issuers |
| DFP 2023 | 732 | 2023-12-31 | For t-4 |
| ITR 2023 | 727 | Q1-Q3 2023 | For t-4 |
| **Total** | | | **52/52** NBY-missing issuers, 51 with ≥2 dates |

This is **free, CVM-official, issuer-centric data** available for every CVM-reporting company.

---

## 3. Design

### Metric identity

| Field | Value |
|-------|-------|
| Name | `NBY_PROXY_FREE` |
| metric_code | `nby_proxy_free` |
| Method | `share_count_delta_cvm_composicao` |
| Formula | `(shares_t4 - shares_t) / shares_t4` (same as NBY) |
| Source | CVM `composicao_capital` CSV (net = total - treasury) |
| formula_version | 1 |

### Separation from NBY

- **`net_buyback_yield`** (existing): uses Yahoo `shares_outstanding` from market snapshots. Vendor-grade.
- **`nby_proxy_free`** (new): uses CVM `composicao_capital` share counts. Free, CVM-official. Proxy.

Both coexist in `computed_metrics`. They are **separate metric codes**. Never conflated.

### NPY impact

`NPY = DY + NBY`. If NBY is NULL but NBY_PROXY_FREE exists, NPY stays NULL (uses only the exact metric). A separate `NPY_PROXY_FREE = DY + NBY_PROXY_FREE` could be created, but is **out of scope** for this micro feature.

### Why "proxy"

CVM `composicao_capital` reports **registered capital composition**, not market-traded float. It doesn't account for:
- Restricted shares
- Options/warrants not yet exercised
- ADR conversions
- Corporate actions between filing dates

For most companies, `total - treasury` closely approximates outstanding shares, but it's not identical to Yahoo's `sharesOutstanding` (which reflects market float). The "proxy" label is methodologically honest.

---

## 4. Data pipeline

```
CVM DFP/ITR zips (download)
  → extract composicao_capital CSV
  → match by CNPJ to issuers
  → compute net_shares = total - treasury per (issuer, reference_date)
  → store as computed_metrics with metric_code='nby_proxy_free'
```

### Not stored in market_snapshots

CVM share counts are **filing-based data**, not market snapshots. Storing them in `market_snapshots` would pollute the market data layer with regulatory data. Instead, the proxy computation reads CSV data and writes directly to `computed_metrics`.

### `fetched_at` semantics preserved

No change to `market_snapshots.fetched_at`. CVM data stays in the metrics layer.

---

## 5. Schema impact

### No migration needed

`computed_metrics` table already supports any `metric_code` string. The new `nby_proxy_free` code fits existing schema.

### MetricCode enum

Add `nby_proxy_free = "nby_proxy_free"` to the MetricCode enum in shared-models-py.

---

## 6. Limitations (explicit)

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Registered capital ≠ market float | Minor for most companies | Label as proxy, document in provenance |
| Quarterly granularity only | t and t-4 at quarter-ends only | Matches NBY's quarterly anchor model |
| Corporate actions between quarters | May distort if split/grouping occurs | Sanity check: skip if ratio >5x or <0.2x |
| Treasury shares may lag | Minor — most companies update quarterly | Accept as-is for v1 |
| No real-time data | Regulatory filing lag (DFP+90d, ITR+45d) | Acceptable for proxy |

---

## 7. Appetite

**Level: XS** — 2 build scopes

### Must-fit:
- Script to download CVM composicao_capital + compute NBY_PROXY_FREE
- MetricCode enum addition
- Coverage measurement

### First cuts:
- NPY_PROXY_FREE → out of scope
- Auto-ingestion pipeline → future
- Historical backfill beyond 2023-2024 → future

---

## 8. Boundaries / No-Gos / Out of Scope

### No-Gos
- Do NOT overwrite or modify existing `net_buyback_yield` metrics
- Do NOT store CVM share data in `market_snapshots`
- Do NOT rename proxy to `net_buyback_yield`
- Do NOT create `NPY_PROXY_FREE` in this micro feature
- Do NOT change ranking pipeline

### Out of Scope
- Auto-ingestion of composicao_capital in fundamentals pipeline
- NPY_PROXY_FREE composition
- Compat view changes
- PIT/backtest integration

---

## 9. Rabbit Holes / Hidden Risks

### RH1 — CNPJ format mismatch
DB stores digits-only CNPJ. CVM CSV uses formatted (XX.XXX.XXX/XXXX-XX). **Mitigation:** Normalize to digits before matching.

### RH2 — Split/grupamento distortion
If shares_t4 and shares_t differ by >5x, likely a corporate action occurred. **Mitigation:** Skip and flag, don't compute proxy.

### RH3 — Non-standard FYE
CAML3 has November FYE. CVM composicao_capital includes non-standard dates (2024-11-30). **Mitigation:** Map to nearest quarter-end, same as TTM fix.

---

## 10. Build Scopes

### S1 — CVM composicao_capital enrichment script + metric

**Objective:** Download DFP/ITR 2023+2024 composicao_capital. Compute `nby_proxy_free` for all Core issuers. Persist in `computed_metrics`.

**Files:**
- `shared-models-py/entities.py`: Add `nby_proxy_free` to MetricCode enum
- `fundamentals-engine/scripts/compute_nby_proxy_free.py`: Download, match, compute, persist

**Done criteria:**
- MetricCode enum includes `nby_proxy_free`
- Script produces `nby_proxy_free` metrics for Core issuers
- Coverage report

### S2 — Validation + measurement

**Validation:**

| Check | Pass criteria |
|-------|---------------|
| V1 — Coverage | `nby_proxy_free` coverage ≥80% of Core issuers |
| V2 — Provenance | All metrics have `formula_version=1`, `inputs_snapshot` records CVM source |
| V3 — No NBY overwrite | `net_buyback_yield` count unchanged |
| V4 — Split sanity | 0 metrics with ratio >5x or <0.2x |
| V5 — Spot-check | BRF, Santos Brasil, Eletropar have `nby_proxy_free` |
| V6 — Tests pass | 0 regressions |

---

## 11. Close Summary

### Delivered

1. **MetricCode enum**: Added `nby_proxy_free` to shared-models-py
2. **Enrichment script**: `scripts/compute_nby_proxy_free.py` — downloads CVM DFP/ITR composicao_capital (2023+2024), matches by CNPJ, computes proxy, persists
3. **Split detection**: 11 issuers skipped for suspicious share ratio (>5x or <0.2x)

### Validation Evidence

| Check | Result |
|-------|--------|
| V1 — Coverage | **215/232 = 92.7%** — PASS (gate ≥80%) |
| V2 — Provenance | All metrics have `source=CVM_composicao_capital`, shares_t/t4/treasury in inputs_snapshot |
| V3 — No NBY overwrite | `net_buyback_yield` = 180/232 — **unchanged** |
| V4 — Split sanity | **0** suspicious ratios in computed metrics |
| V5 — Spot-checks | BRF: 3.4% buyback, Santos Brasil: 0.4%, Eletropar: 0.0% — all plausible |
| V6 — Tests | 262 fundamentals-engine + 415 quant-engine = **677 tests, 0 regressions** |

### Distribution

- Computed: 215
- Skipped (no t data): 5
- Skipped (no t-4 data): 1
- Skipped (split/corporate action): 11

### Split-detected issuers (skipped)

| CVM | Company | Ratio | Likely cause |
|-----|---------|------:|-------------|
| 025160 | Sequoia Logística | 0.06 | Reverse split |
| 015423 | Fictor Alimentos | 1000.0 | Grupamento |
| 025399 | Neogrid | 0.04 | Reverse split |
| 025283 | Aeris | 0.05 | Reverse split |
| 025879 | Kora Saúde | 100.1 | Grupamento |
| 027057 | Vitru Educação | 0.07 | Reverse split |
| 003158 | Coteminas | 0.20 | Split |
| 026077 | TC S.A. | 0.14 | Reverse split |
| 025984 | CBA Alumínio | 0.00 | Extreme change |
| 025950 | Três Tentos | 1000.1 | Grupamento |
| 018414 | Padtec | 1003.2 | Grupamento |

### What this does NOT close

- `net_buyback_yield` (exact/vendor) remains at 180/232 (77.6%) — **unchanged**
- NBY_PROXY_FREE is a **separate proxy metric**, not a replacement for NBY exact
- NPY_PROXY_FREE not created (out of scope)
- Ranking pipeline not changed

---

## 12. Tech Lead Handoff

### What changed
- `entities.py`: `nby_proxy_free` added to MetricCode enum
- New script: `scripts/compute_nby_proxy_free.py`
- 215 new `computed_metrics` rows with `metric_code='nby_proxy_free'`

### What did NOT change
- `net_buyback_yield` metrics — untouched
- `market_snapshots` — untouched
- Ranking pipeline — untouched
- DY/NPY — untouched

### Where to start review
1. Script `compute_nby_proxy_free.py` — download, match, compute logic
2. Split detection thresholds (>5x or <0.2x)
3. Coverage report output
4. Spot-check: BRF=3.4%, Santos Brasil=0.4%, Eletropar=0.0%
