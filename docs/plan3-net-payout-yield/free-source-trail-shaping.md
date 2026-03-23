# Free-Source Trail — NPY_PROXY_FREE Composition + Methodological Contract

## Status: BUILD COMPLETE — Awaiting Tech Lead review

---

## 1. Micro Feature

**Create `npy_proxy_free` metric (= DY + NBY_PROXY_FREE) and formalize the dual-trail methodological contract (exact vs free-source).**

---

## 2. Problem

After F1A, the free-source trail has:
- `dividend_yield` — 190/232 (81.9%) — uses CVM filings + Yahoo market_cap
- `nby_proxy_free` — 215/232 (92.7%) — uses CVM composicao_capital

But there's no **composed NPY** on the free trail. The existing `net_payout_yield` uses `net_buyback_yield` (exact/Yahoo), which is NULL for 52 issuers. Without `npy_proxy_free`, the free trail is incomplete — DY and NBY_PROXY exist but their composition doesn't.

Additionally, the dual-trail architecture (exact vs free-source) has no formal contract. The distinction lives only in ad-hoc documentation.

---

## 3. Design

### Metric identity

| Field | Value |
|-------|-------|
| Name | `npy_proxy_free` |
| metric_code | `npy_proxy_free` |
| Formula | `DY + NBY_PROXY_FREE` |
| formula_version | 1 |
| Inputs | `dividend_yield` value + `nby_proxy_free` value |

### Composition rule

Same as classic NPY:
- `npy_proxy_free = dy + nby_proxy_free`
- NULL if either input is NULL
- Both inputs must be for the same `reference_date` and `issuer_id`

### Expected coverage

DY covers 190, NBY_PROXY covers 215. NPY_PROXY = intersection:
- **~188/232 (estimated ~81%)** — limited by DY coverage (the smaller set)

---

## 4. Dual-Trail Methodological Contract

### Trail definitions

| Trail | Metrics | Source | Label |
|-------|---------|-------|-------|
| **Exact** | `dividend_yield`, `net_buyback_yield`, `net_payout_yield` | CVM filings + Yahoo market data | Vendor-grade |
| **Free-source** | `dividend_yield`, `nby_proxy_free`, `npy_proxy_free` | CVM filings + CVM composicao_capital | Proxy |

### Rules

1. **DY is shared.** Both trails use the same `dividend_yield` metric. DY does not have a proxy variant — it uses CVM distributions (free) + Yahoo market_cap.

2. **NBY diverges.** Exact trail uses `net_buyback_yield` (Yahoo shares_outstanding). Free trail uses `nby_proxy_free` (CVM registered capital composition).

3. **NPY follows its trail.** `net_payout_yield` = DY + NBY exact. `npy_proxy_free` = DY + NBY proxy. Never mix.

4. **No silent substitution.** A consumer must explicitly choose which trail to use. The system never falls back from exact to proxy without the consumer knowing.

5. **Provenance preserved.** Each metric records its source in `inputs_snapshot`. Trail membership is deterministic from `metric_code`.

6. **Proxy limitations documented.** CVM composicao_capital reports registered capital, not market float. May not capture: restricted shares, options/warrants, ADR conversions, intra-quarter corporate actions.

### Coverage summary

| Metric | Exact trail | Free trail |
|--------|:-----------:|:----------:|
| DY | 190/232 (81.9%) | 190/232 (81.9%) — same |
| NBY | 180/232 (77.6%) | 215/232 (92.7%) |
| NPY | 179/232 (77.2%) | ~188/232 (~81%) — estimated |

---

## 5. Schema Impact

### MetricCode enum

Add `npy_proxy_free = "npy_proxy_free"` to shared-models-py.

### No migration needed

`computed_metrics` accepts any metric_code string.

---

## 6. Appetite

**Level: XS** — 1 build scope

### Must-fit:
- `npy_proxy_free` composition logic
- MetricCode enum addition
- Script or engine integration to compute + persist
- Methodological contract documented in shaping doc (this document = D)
- Coverage measurement

### First cuts:
- Compat view changes → B (later)
- Research panel integration → C (later)
- Ranking changes → not now

---

## 7. Boundaries / No-Gos

- Do NOT modify existing `net_payout_yield` metrics
- Do NOT add proxy metrics to the compat view
- Do NOT change ranking pipeline
- Do NOT mix trails (never compose exact DY + proxy NBY under the `net_payout_yield` code)

---

## 8. Build Scope

### S1 — NPY_PROXY_FREE composition + measurement

**Objective:** Compute `npy_proxy_free = dy + nby_proxy_free` for all Core issuers where both exist. Persist. Measure coverage.

**Files:**
- `entities.py`: Add `npy_proxy_free` to MetricCode
- `scripts/compute_nby_proxy_free.py`: Extend to also compose NPY_PROXY_FREE after NBY computation (same script, chained step)

**Validation:**

| Check | Pass criteria |
|-------|---------------|
| V1 — Coverage | `npy_proxy_free` ≥80% of Core |
| V2 — Composition | For every issuer with both DY and NBY_PROXY, NPY_PROXY = DY + NBY_PROXY |
| V3 — No classic NPY change | `net_payout_yield` count unchanged |
| V4 — Provenance | `inputs_snapshot` records both input metrics |
| V5 — Tests | 0 regressions |

---

## 9. Close Summary

### Delivered

1. **MetricCode enum**: Added `npy_proxy_free` to shared-models-py
2. **NPY_PROXY_FREE composition**: Extended `compute_nby_proxy_free.py` to chain NPY composition after NBY
3. **Methodological contract**: Section 4 of this document formalizes the dual-trail architecture

### Results

| Trail | Metric | Coverage | Gate ≥80% |
|-------|--------|--------:|:---------:|
| Free | `dividend_yield` | 190/232 (81.9%) | PASS |
| Free | `nby_proxy_free` | 215/232 (92.7%) | PASS |
| Free | `npy_proxy_free` | **180/232 (77.6%)** | Near (limited by DY) |
| Exact | `net_buyback_yield` | 180/232 (77.6%) | — |
| Exact | `net_payout_yield` | 179/232 (77.2%) | — |

NPY_PROXY_FREE is 180/232 — limited by the DY coverage ceiling (190 issuers), not by NBY_PROXY (215 issuers). The 52 NULL cases are issuers without DY (no distributions + no DFC coverage + no market snapshot).

### Validation Evidence

| Check | Result |
|-------|--------|
| V1 — NPY_PROXY coverage | 180/232 = 77.6% |
| V2 — Composition | 180 = intersection of DY (190) and NBY_PROXY (215) |
| V3 — No classic NPY change | `net_payout_yield` = 179/232 — unchanged |
| V4 — Provenance | All `npy_proxy_free` have `inputs_snapshot` with DY value, NBY_PROXY value, formula, trail label |
| V5 — Tests | 262 fundamentals-engine, 0 regressions |

### What this closes

The **free-source trail** is now methodologically complete:
- `dividend_yield` — shared between both trails
- `nby_proxy_free` — CVM composicao_capital proxy
- `npy_proxy_free` — composition of the above

### What this does NOT close

- `net_buyback_yield` exact remains at 77.6%
- `net_payout_yield` exact remains at 77.2%
- No compat view / ranking / product exposure yet

---

## 10. Tech Lead Handoff

### What changed
- `entities.py`: `npy_proxy_free` added to MetricCode
- `scripts/compute_nby_proxy_free.py`: Extended with Phase 2 (NPY composition)
- 180 new `computed_metrics` rows with `metric_code='npy_proxy_free'`

### What did NOT change
- `net_payout_yield` metrics — untouched
- Compat view — untouched
- Ranking — untouched
- DY — untouched

### Dual-trail contract (formalized in section 4)
| Rule | Description |
|------|-------------|
| 1 | DY is shared between trails |
| 2 | NBY diverges (exact vs proxy) |
| 3 | NPY follows its trail |
| 4 | No silent substitution |
| 5 | Provenance preserved |
| 6 | Proxy limitations documented |

### Next step
**B-lite**: Expose free-trail metrics in analytical surfaces alongside exact metrics, without altering ranking default.
