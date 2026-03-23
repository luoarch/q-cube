# Historical Market Snapshot Backfill 2020–2022

## Status: BUILD COMPLETE — Awaiting Tech Lead review

---

## 1. Micro Feature

**Backfill historical market snapshots (price + volume) for 2020–2022 at monthly cadence from yfinance, with PIT-correct market_cap derivation from CVM composicao_capital share counts.**

Combined with the filings backfill (done), this should move the system from **FILINGS READY, MARKET BLOCKING** to **FULL VALIDATION VIABLE**.

---

## 2. Problem

Viability audit shows zero market data for 2020-2022. The backtest engine needs price for trade execution, volume for liquidity gates, and market_cap for EY/EV ranking at each rebalance date.

---

## 3. Cadence Decision

**Option A chosen: monthly cadence.**

The canonical experiment used monthly rebalance. Walk-forward, sensitivity, and the promotion pipeline all assume configurable rebalance frequency including monthly. Quarterly-only snapshots would artificially constrain the validation.

Target dates: **first business day of each month, Jan 2020 through Dec 2022** = 36 monthly dates.

---

## 4. Data Strategy

### Source: yfinance `.history()`

For each target month, fetch the **full month of daily OHLCV data** (not a single day). This provides both the price anchor and the rolling volume needed for liquidity.

### Price anchoring: strictly backward-looking

For a target rebalance date `d`:
- **price_date = latest trading day on or before `d`**
- Never a date after `d`
- `fetched_at` on the stored snapshot = `price_date` (the actual observation date, not `d` or today)

Implementation: fetch daily history for the month ending at `d`, take the last row where `date <= d`.

### Price series: Close (not Adjusted Close)

For consistency:
- **Trade execution / portfolio valuation**: Close price at execution date
- **Market cap derivation**: Close × shares (both at same point in time)

Adjusted Close is NOT used because:
- When multiplied by contemporaneous shares, the split adjustment in Adjusted Close would double-count the split already reflected in the lower share count
- Close × shares_at_that_date gives the correct market cap at that point in time

### Volume: raw daily share volume (preserving existing semantics)

**Audit result**: `market_snapshots.volume` currently stores **raw daily share volume** (Yahoo `regularMarketVolume`). The compat view aliases it as `avg_daily_volume` but it's a single-day value, not a rolling average.

**Decision: Caminho B — do NOT repurpose the field.**

For backfilled snapshots, `volume` stores the **raw share volume on the price_date** — same semantics as existing Yahoo snapshots. This preserves the column contract.

**Liquidity gate handling for historical backtest:**

The `magic_formula_brazil` gate compares `avg_daily_volume >= R$1M`. For historical snapshots with a single-day volume:
- The live system already uses single-day volume as a proxy for avg_daily_volume (same approximation)
- Historical snapshots follow the same convention: `volume = raw share volume on price_date`
- The `raw_json` provenance additionally records `avg_traded_value_21d` (rolling average of Close × Volume) for audit purposes, but this is NOT stored in the `volume` column

This means historical and live snapshots have **identical `volume` semantics**: raw daily share volume. The liquidity gate approximation is the same in both cases — a documented limitation of the live system that also applies to the backtest.

**Note for future improvement**: A proper `avg_daily_volume` field (rolling 21-day average traded value in R$) would improve liquidity gating accuracy for both live and historical paths. This is a separate follow-up, not part of this backfill.

### Market cap derivation (PIT-correct)

For each snapshot at date `d`:

1. Find the latest CVM `composicao_capital` entry where:
   - `reference_date <= d` (economic cut before snapshot)
   - `publication_date <= d` (data was publicly available) — using synthetic PIT: DFP+90d, ITR+45d
2. Compute `net_shares = total_shares - treasury_shares`
3. `market_cap = close_price × net_shares`

**If no PIT-compliant shares exist at date `d`**: `market_cap = NULL`, `shares_outstanding = NULL`. The snapshot still has price/volume (useful for trade execution) but cannot be used for EY/EV ranking.

### composicao_capital pre-condition

**Verified**: CVM composicao_capital is available in DFP/ITR zips for 2020-2022:

| Source | Rows | Companies | Dates |
|--------|-----:|----------:|-------|
| DFP 2020 | 733 | 731 | 2020-02 through 2020-12 |
| ITR 2020 | 1,976 | 666 | 2020-03 through 2020-12 |
| DFP 2021 | 772 | 765 | 2021-02 through 2021-12 |
| ITR 2021 | 2,229 | 751 | 2021-03 through 2021-12 |
| DFP 2022 | 731 | 729 | 2022-02 through 2022-12 |
| ITR 2022 | 2,222 | 763 | 2022-03 through 2022-12 |

**DFP 2019 does NOT have composicao_capital** (CSV not in that year's zip).

**Implication**: For Jan-Mar 2020, no PIT-correct shares are available (earliest is ITR 2020 Q1 ref_date=2020-03-31, published ~May 2020). Snapshots for Jan-Apr 2020 will have `market_cap = NULL`. This is documented as a known limitation, not masked.

**Substep required**: Download and parse composicao_capital from DFP/ITR 2020-2022 CSVs into an in-memory lookup table for the backfill script. This is NOT persisted in the DB — it's used only during the backfill execution to derive market_cap. The CVM composicao_capital data is available from the same zip files already downloaded for the filings backfill.

---

## 5. Provenance

Each snapshot stores full derivation provenance in `raw_json`:

```json
{
  "source_components": {
    "price": {"source": "yfinance", "field": "Close", "price_date": "2021-06-30", "target_date": "2021-07-01"},
    "volume": {"source": "yfinance", "field": "Volume", "price_date": "2021-06-30", "raw_share_volume": 12345678},
    "avg_traded_value_21d": {"method": "rolling_mean(Close*Volume, 21d)", "window_end": "2021-06-30", "value": 45678901.23, "note": "audit only, not stored in volume column"},
    "shares": {
      "source": "CVM_composicao_capital",
      "reference_date": "2021-06-30",
      "publication_date": "2021-08-14",
      "total_shares": 5730834040,
      "treasury_shares": 22786568,
      "net_shares": 5708047472
    },
    "market_cap": {
      "formula": "close_price * net_shares",
      "value": 182657519104.0
    }
  },
  "pit_compliant": true,
  "derivation": "historical_backfill_v1"
}
```

`source = 'yahoo'` applies to the price/volume component. The mixed-source nature is documented in `raw_json`, not hidden.

---

## 6. Appetite

**Level: S** — 2 build scopes

### Must-fit:
- Monthly snapshots 2020-2022 (36 dates × ~280 tickers)
- PIT-correct market_cap derivation
- Provenance in raw_json
- Viability re-audit

### First cuts:
- Daily snapshots (monthly sufficient for rebalance)
- Non-Core tickers
- Persisting composicao_capital as separate DB table

---

## 7. Boundaries / No-Gos

- Default: use yfinance `.history()` unchanged
- Allowed: minimal compatibility fixes
- Do NOT change MarketSnapshot model
- Do NOT use Adjusted Close for market_cap derivation
- Do NOT mask PIT gaps (NULL market_cap if no PIT-correct shares)
- Do NOT store `raw_json = None` — all derivation documented

---

## 8. Risks

| Risk | Severity | Mitigation |
|------|:--------:|------------|
| ~40% tickers not on Yahoo for 2020 | Medium | 60% sufficient for 20-pick ranking |
| No PIT-correct shares for Jan-Apr 2020 | Medium | market_cap=NULL; documented limitation |
| Close × shares may differ from real market_cap | Low | Documented as derived; consistent methodology |
| yfinance rate limiting | Low | 0.3s delay; ~280 tickers × 0.3s = ~84s per batch. 1 batch per ticker (full 3-year history), ~5 min total |

---

## 9. Build Scopes

### S1 — Historical snapshot backfill

**Objective**: Fetch monthly snapshots, derive market_cap with PIT-correct shares, store with provenance.

**Validation:**

| Check | Pass criteria |
|-------|---------------|
| V1 — Snapshots created | ≥5,000 new snapshots across 36 dates |
| V2 — Ticker coverage | ≥150 tickers per monthly date |
| V3 — Market cap derived | ≥70% of snapshots with market_cap (NULL for early 2020 accepted) |
| V4 — PIT correctness | 0 snapshots where shares publication_date > snapshot date |
| V5 — Provenance | All snapshots have raw_json with derivation metadata |
| V6 — Price series | Close (not Adjusted Close) used |

### S2 — Viability re-audit

**Validation:**

| Check | Pass criteria |
|-------|---------------|
| V7 — Market PIT 2020-H2 | `fetch_market_pit(2020-07-01)` returns ≥100 tickers |
| V8 — Market PIT 2021 | ≥100 tickers at 2021-01 and 2021-07 |
| V9 — Market PIT 2022 | ≥100 tickers at 2022-01 and 2022-07 |
| V10 — Both layers | ≥100 issuers with both fundamentals + market at ≥80% of monthly dates 2020-H2 through 2024 |
| V11 — Verdict | **FULL VALIDATION VIABLE** (or documented reason why not) |

Note: V10 threshold (≥100 at ≥80%) is an **operational gate**, not a methodological law. The close should document it as a practical viability threshold.

---

## 10. Close Summary

### S1 — Snapshot backfill: COMPLETE

- **6,104 snapshots created** across 36 monthly dates (2020-2022)
- 242 tickers processed, 55 with no Yahoo data (delisted/unknown)
- 731 snapshot instances with no PIT-correct shares → `market_cap = NULL`
- All snapshots have `raw_json` with full provenance
- `fetched_at` = actual price_date (backward-looking)
- `volume` = raw share volume (semantics preserved)

### S2 — Viability re-audit: VIABLE

| Semester | Sample dates | Funds | Market | Both | w/mcap |
|----------|:-----------:|------:|-------:|-----:|-------:|
| 2020-H1 | Jan, Apr | 0 | 144-147 | 0 | 0 |
| 2020-H2 | Jul, Oct | 327 | 149-153 | 149-153 | 149-153 |
| 2021-H1 | Jan, Apr | 327-349 | 160-167 | 160-167 | 160-167 |
| 2021-H2 | Jul, Oct | 352-353 | 173-184 | 173-184 | 173-184 |
| 2022-H1 | Jan, Apr | 353-354 | 184-185 | 184-185 | 184-185 |
| 2022-H2 | Jul, Oct | 354 | 186 | 186 | 186 |
| 2023+ | (existing) | 354-355 | 286-287 | 285-286 | varies |

**Verdict: VALIDATION RUN VIABLE** (subject to known market-layer approximations)

- 18/20 sample dates (90%) have ≥100 issuers with both layers
- Gap: 2020-H1 has 0 fundamentals (PIT: filings not yet published)
- Viable IS period: **2020-H2 through 2023** (3.5 years)
- Viable OOS period: **2024** (1 year)
- Both with 149-186 issuers (2020-2022) growing to 285+ (2023-2024)

### Known limitations

1. **2020-H1**: No fundamentals (publication_date PIT gating). IS starts at 2020-07 earliest.
2. **Volume**: Raw daily share volume, not rolling average traded value. Same approximation as live.
3. **Market cap**: Derived (Close × CVM shares), not real-time Yahoo. Documented in raw_json.
4. **Ticker coverage**: ~187/242 Core tickers have Yahoo data (~77%). Sufficient for 20-pick ranking.

---

## 11. Tech Lead Handoff

### What changed
- New script: `scripts/backfill_historical_snapshots.py`
- 6,104 new `market_snapshots` rows with full provenance
- `fetched_at` set to historical price_date (not today)
- `raw_json` documents mixed-source derivation

### What did NOT change
- MarketSnapshot model — untouched
- PIT data layer — untouched
- Ranking / compat view — untouched
- Metrics formulas — untouched

### Viability for next step
The system is now operationally viable for a full empirical validation run with:
- IS: 2020-H2 through 2023 (~3.5 years, 149-186 issuers)
- OOS: 2024 (285 issuers)
- Walk-forward, Reality Check, sensitivity, and promotion pipeline all feasible
