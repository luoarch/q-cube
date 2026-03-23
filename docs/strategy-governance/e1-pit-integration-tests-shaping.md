# E1 — PIT Integration Tests

## Status: BUILD COMPLETE

---

## 1. Micro Feature

**Integration tests verifying PIT correctness against the real PostgreSQL database with production data.** Covers fundamentals, market data, universe survivorship, frozen policy, and strategy registry.

---

## 2. Problem

The PIT data layer had unit tests (SQLite in-memory) but no integration tests against real data. The methodological review identified this as a quality gap: PIT correctness was claimed but not independently verified against production.

---

## 3. Design

### Test classes (5)

| Class | Tests | What it verifies |
|-------|------:|-----------------|
| TestPITFundamentals | 5 | publication_date gating, no future leaks, monotonic count, latest ref_date |
| TestPITMarket | 5 | staleness window, no future snapshots, backfilled dates are historical |
| TestPITUniverse | 2 | survivorship via valid_from/valid_to, delisted exclusion |
| TestFrozenPolicyUniverse | 2 | CORE_ELIGIBLE count, no financials in core |
| TestStrategyRegistry | 4 | 3 entries, frontrunner/control states, partial unique constraint |

### Execution

- **Default**: skipped (`addopts = -m 'not integration'`)
- **Run**: `python -m pytest tests/test_pit_integration.py -v -m integration`
- **Requires**: running PostgreSQL with q3 database populated

---

## 4. Results

17 passed, 1 skipped (no delisted securities in current data), 0 failures.

Key assertions verified:
- `fetch_fundamentals_pit(2020-01-01)` returns 0 (no filings published yet)
- `fetch_fundamentals_pit(2025-06-01)` returns >100 issuers
- Count is non-decreasing over time (2020 <= 2022 <= 2025)
- No future snapshots leak into historical queries
- Backfilled 2021 snapshots have 2021 dates, not 2026
- 521 CORE_ELIGIBLE issuers, 0 financials in core
- Strategy registry: hybrid_20q = FRONTRUNNER+BLOCKED, controls = CONTROL+REJECTED

---

## 5. Tech Lead Handoff

### Files
- New: `tests/test_pit_integration.py` (18 tests)
- Modified: `pyproject.toml` (integration marker + addopts)

### Run command
```bash
cd services/quant-engine
source .venv/bin/activate
python -m pytest tests/test_pit_integration.py -v -m integration
```
