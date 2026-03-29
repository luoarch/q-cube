# Follow-Up Ledger

Central registry of follow-ups across all micro features.

## Resolved

| ID | Origin MF | Description | Resolved by |
|----|-----------|-------------|-------------|
| FU-P3A-1 | Plan 3A | NBY coverage 77.6% < 80% gate — Yahoo structural gap | Plan 5 (CVM primary, 92.0%) |
| FU-P3A-2 | Plan 3A | Plan 3B ranking integration blocked until coverage sufficient | Plan 6 (NPY as core factor) |
| FU-P3A-3 | Plan 3A | is_primary deduplication | Plan 3C.1 |
| FU-P6-1 | Plan 6 | Frontend needs adaptation to split-model ranking | FU-P6-1 build (2026-03-26) |
| FU-P6-2 | Plan 6 | ranking.py and engine.py if has_npy branch | Plan 6 build (rank_model_group) |
| FU-RT01A-1 | MF-RT-01A | Wire pilot pipeline to real scheduler | MF-RUNTIME-01B (Celery beat) |

## Open

| ID | Origin MF | Severity | Category | Description |
|----|-----------|----------|----------|-------------|
| FU-P3A-4 | Plan 3A | cleanup | technical | Securitizacao sector 0% NPY coverage — structural (SPVs), not a bug |
| FU-P3C1-1 | Plan 3C.1 | cleanup | investigation | 385 orphan issuers without securities — genuinely unlisted (spike proved) |
| FU-P4-1 | Plan 4 | degraded | operational | Coverage gates post-filter — STALE: DY now 80.2%, NBY 95.4%. Needs ledger update after next recompute. |
| FU-P5-1 | Plan 5 | degraded | feature | Deprecar nby_proxy_free / npy_proxy_free — deferred to Plan 5B |
| FU-P5-2 | Plan 5 | degraded | feature | DY 80.2% (gate PASSES). 43/47 missing issuers have NO market_cap (Yahoo gap). Fix = snapshot refresh. |
| FU-P5-3 | Plan 5 | cleanup | investigation | CVM scale variable (~79 issuers in thousands) — document for future absolute shares usage |
| FU-P5-4 | Plan 5 | cleanup | operational | 7 NO_T issuers gain coverage when DFP 2024 filings arrive |

## Debt (from session 2026-03-26)

| Item | Origin | Impact |
|------|--------|--------|
| Frontend ranking tests | FU-P6-1 | No component tests for ranking page or 3D scenes |
| Beat retry | MF-RT-01B | take_daily_snapshot has no autoretry_for — lost day if quant-engine down |
| Compat view auto-refresh | Plan 6 | Materialized view requires manual REFRESH — no cron/trigger |
| paginatedRankingSchema | Plan 6 | Legacy schema still exported in shared-contracts (no consumer, but confusing) |
