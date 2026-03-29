# Follow-Up Ledger

Central registry of follow-ups across all micro features.

| ID | Origin MF | Severity | Category | Description | Absorbed by |
|----|-----------|----------|----------|-------------|-------------|
| FU-P3A-1 | Plan 3A | blocking | feature | NBY coverage 77.6% < 80% gate — Yahoo structural gap for ~39 issuers | Plan 5 |
| FU-P3A-2 | Plan 3A | degraded | feature | Plan 3B ranking integration blocked until coverage sufficient | Plan 6 |
| FU-P3A-3 | Plan 3A | cleanup | technical | is_primary deduplication (resolved by 3C.1) | Plan 3C.1 |
| FU-P3A-4 | Plan 3A | cleanup | technical | Securitizacao sector 0% NPY coverage — structural (SPVs) | — |
| FU-P3C1-1 | Plan 3C.1 | cleanup | investigation | 385 orphan issuers without securities — genuinely unlisted (spike proved) | — |
| FU-P4-1 | Plan 4 | degraded | operational | Coverage DY 49.6%, NBY 72.0%, NPY 48.7% post-filter — all gates FAIL | — |
| FU-P5-1 | Plan 5 | degraded | feature | Deprecar nby_proxy_free / npy_proxy_free apos validacao de NBY v2 | Plan 5B (pendente) |
| FU-P5-2 | Plan 5 | blocking | feature | DY coverage 49.6% is now sole bottleneck for NPY — requires DFC label matching improvement | — |
| FU-P5-3 | Plan 5 | cleanup | investigation | CVM scale variable (~79 issuers in thousands) — document for future absolute shares usage | — |
| FU-P5-4 | Plan 5 | cleanup | operational | 7 NO_T issuers gain coverage when DFP 2024 filings arrive | — |
| FU-P6-1 | Plan 6 | degraded | feature | Frontend needs adaptation to consume primaryRanking/secondaryRanking instead of data[] | — |
| FU-P6-2 | Plan 6 | cleanup | technical | ranking.py (gates) and engine.py (backtest) still have if has_npy branch — align with split-model | Plan 6 (resolved) |
| FU-RT01A-1 | MF-RT-01A | blocking | feature | Wire pilot pipeline to real scheduler (Celery beat) — MF-RUNTIME-01B | — |
