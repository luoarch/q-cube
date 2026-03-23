# S1 Mini Review — DFC Mapping + Shares Column

## Status: SPIKE DONE

## DFC Shareholder Distributions Mapping

### Results

| Metric | Value | Gate |
|--------|-------|------|
| Lines matched | 1,895 (aggregated from 2,361 raw matches) | - |
| Multi-line groups aggregated | 379 (dividends + JCP summed per filing) | - |
| Distinct issuers | 552 | **>30 PASSED** |
| Sectors covered | 53 | No sector missing |
| False positive rate | ~18 lines positive-value (BRKM3 sign anomaly, CASN3 AFAC edge case) | Acceptable |

### Label matching patterns

Top 5 matched labels (correct):
- "Dividendos pagos" (409)
- "Pagamento de dividendos" (194)
- "Dividendos Pagos" (162)
- "Dividendos e juros sobre capital proprio pagos" (90)
- "Dividendos e juros sobre o capital proprio pagos" (86)

Top 5 excluded labels (correct):
- "Aumento de capital" (313)
- "Captacao de emprestimos e financiamentos" (215)
- "Aumento de Capital" (191)
- "Adiantamento para futuro aumento de capital" (189)
- "Partes relacionadas" (171)

"Recompra de acoes" (126 lines) correctly excluded — tracked separately.
"Dividendos recebidos" (15 lines) correctly excluded — income, not distribution.

### Sign convention

- 1,236 negative (65% — correct, cash outflow)
- 18 positive (1% — edge cases, handled by abs() in DY strategy)
- 641 zero (34% — filings with no distributions in period)

### Tests

- 29/29 normalization tests passing (18 new DFC tests)
- 123/123 fundamentals-engine tests passing (zero regression)

---

## Shares Outstanding Backfill

### Results

| Metric | Value | Gate |
|--------|-------|------|
| Securities processed | 711 | - |
| Securities with shares data | 285 (40%) | - |
| Securities with 2+ data points | 284 | **Sufficient for NBY** |
| Total snapshots updated | 626 | - |
| Failures | 0 | - |

### Data source

- `yf.Ticker.quarterly_balance_sheet["Ordinary Shares Number"]`
- Quarterly-anchored, company-wide total shares (ON + PN for dual-class)
- Validated against known companies: PETR4 (12.89B), BBAS3 (5.71B), ITSA4 (11.21B), VALE3 (4.27B), MGLU3 (0.77B)

### ADR update

- raw_json was empty ({}) for all 175k snapshots — backfill from raw_json impossible
- Adapter now extracts sharesOutstanding from .info for future snapshots
- Historical backfill used quarterly_balance_sheet (cleaner, quarterly-aligned)

---

## Files Changed

| File | Change |
|------|--------|
| `packages/shared-models-py/src/q3_shared_models/entities.py` | Added CanonicalKey.shareholder_distributions, 3 MetricCodes, MarketSnapshot.shares_outstanding |
| `services/fundamentals-engine/src/.../canonical_mapper.py` | Label-based DFC matching (include/exclude regex) |
| `services/fundamentals-engine/src/.../pipeline.py` | Pass label + statement_type to mapper |
| `services/fundamentals-engine/src/.../providers/base.py` | sharesOutstanding in YahooInfoPayload + MarketSnapshotData |
| `services/fundamentals-engine/src/.../providers/yahoo/adapter.py` | Extract sharesOutstanding |
| `services/fundamentals-engine/src/.../tasks/fetch_snapshots.py` | Persist shares_outstanding |
| `apps/api/src/db/schema.ts` | sharesOutstanding column in marketSnapshots |
| `services/quant-engine/alembic/versions/20260319_0015_*.py` | Migration: shares_outstanding column |
| `services/fundamentals-engine/tests/test_normalization.py` | 18 new DFC mapping tests |
| `services/fundamentals-engine/tests/fixtures/yahoo_payloads.py` | sharesOutstanding in PETR4 fixture |
| `services/fundamentals-engine/scripts/remap_dfc_distributions.py` | One-time remapping script |
| `services/fundamentals-engine/scripts/backfill_shares_outstanding.py` | One-time backfill script |

## Known Gaps for Release

- DFC coverage: 552/741 issuers (74%). Some issuers have no DFC sub-accounts.
- Shares coverage: 285/711 securities (40%). yfinance quarterly_balance_sheet not available for all.
- Shares 4-quarter spread: only 2 securities have 4+ data points. Most have 2-3.
  - This means NBY will use the available spread (may be <4 quarters for v1).
  - Future snapshot refreshes will accumulate more data points.

## Verdict

S1 spike done criteria met. Safe to proceed to S2 (TTM engine + Dividend Yield).
