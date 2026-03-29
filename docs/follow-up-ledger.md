# Follow-Up Ledger

Central registry of follow-ups across all micro features.

## Resolved

| ID | Origin MF | Description | Resolved by |
|----|-----------|-------------|-------------|
| FU-P3A-1 | Plan 3A | NBY coverage 77.6% < 80% gate | Plan 5 (CVM primary, 92.0%) |
| FU-P3A-2 | Plan 3A | Ranking integration blocked | Plan 6 (NPY as core factor) |
| FU-P3A-3 | Plan 3A | is_primary deduplication | Plan 3C.1 |
| FU-P3A-4 | Plan 3A | Securitizacao sector 0% NPY — structural (SPVs) | Closed: by design, no action needed |
| FU-P3C1-1 | Plan 3C.1 | 385 orphan issuers without securities | Closed: genuinely unlisted (spike proved) |
| FU-P4-1 | Plan 4 | Coverage gates post-filter | Closed: DY 80.2% PASS, NBY 95.4% PASS. Gates updated. |
| FU-P5-1 | Plan 5 | Deprecar nby_proxy_free / npy_proxy_free | Closed: enum deleted, asset.service.ts cleaned (2026-03-29) |
| FU-P5-3 | Plan 5 | CVM scale variable (~79 issuers in thousands) | Closed: documented, NBY scale-invariant, no code action |
| FU-P5-4 | Plan 5 | 7 NO_T issuers when DFP 2024 arrives | Closed: pipeline dependency, not code. 10 issuers still without DFP 2024. |
| FU-P6-1 | Plan 6 | Frontend adaptation to split-model ranking | FU-P6-1 build (2026-03-26) |
| FU-P6-2 | Plan 6 | ranking.py and engine.py if has_npy branch | Plan 6 build (rank_model_group) |
| FU-RT01A-1 | MF-RT-01A | Wire pilot to real scheduler | MF-RUNTIME-01B (Celery beat, 2026-03-26) |

## Open

(none)

## Structural (documented)

| ID | Description | Investigation |
|----|-------------|---------------|
| FU-P5-2 | 27 tickers without market_cap after B3 backfill. | Was 42, Plan 7 resolved 15 via B3 COTAHIST. Remaining 27 are: ticker mismatches (CELP3→EQPA3, STPB3→STBP3, B3→B3SA3, SC303→invalid), delisted, or OTC/non-negotiated. Root cause: securities table ticker quality. Fix: ticker cleanup MF. |

## Debt

| Item | Origin | Impact | Status |
|------|--------|--------|--------|
| Frontend ranking tests | FU-P6-1 | No component tests for ranking page or 3D scenes | Open |
| Beat retry | MF-RT-01B | take_daily_snapshot has no autoretry_for | Open |
| sys.path hack in fetch_b3_daily | Plan 7 | quant-engine task imports fundamentals-engine via sys.path. Move to shared lib or HTTP endpoint. | Open |
| CVM scale × price = bad mcap | Plan 7 | 6 micro-caps with CVM shares in thousands produce inflated DY. Do NOT derive mcap for CVM-scale-unknown issuers without validation. | Documented |
| ~~Compat view auto-refresh~~ | ~~Plan 6~~ | ~~Manual REFRESH required~~ | **Resolved** — beat task 17:50 seg-sex |
| ~~paginatedRankingSchema~~ | ~~Plan 6~~ | ~~Legacy schema in shared-contracts~~ | **Resolved** — deleted |
