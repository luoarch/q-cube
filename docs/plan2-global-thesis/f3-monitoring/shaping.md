# Shape Up — F3.1: Plan 2 Monitoring Foundation

## 1. Micro Feature

**Request:** Backend monitoring endpoints for Plan 2 governance — coverage dashboard data, drift detection between runs, rubric aging, review queue.

**Framing:** "De qualquer run, a equipe precisa responder rapidamente 4 perguntas:
1. Qual a qualidade da evidencia que sustenta esse ranking?
2. O que mudou desde o ultimo run?
3. Quais rubrics precisam de revisao?
4. Onde esta o risco?"

## 2. Problem

Plan 2 is operationally complete (v2) with 100% trio coverage across 98 issuers, but there's no way to programmatically monitor evidence quality, detect drift between runs, identify stale rubrics, or surface review priorities. The CLI validation script (`run_plan2_validation.py`) computes useful metrics but they're not persisted or exposed via API.

## 3. Outcome

4 new FastAPI endpoints on quant-engine that compute monitoring data from already-persisted Plan 2 data:
- **Run monitoring summary**: coverage, provenance, confidence, evidence quality aggregations
- **Run drift**: bucket changes, top-N changes, fragility deltas vs previous run
- **Rubric aging**: stale rubrics by dimension and issuer
- **Review queue**: prioritized list of rubrics needing human attention

## 4. Current System Summary

### What exists
- `plan2_runs` table: persists bucket_distribution_json, total_eligible/ineligible per run
- `plan2_thesis_scores` table: persists all scores + `feature_input_json` (contains provenance per dimension)
- `plan2_rubric_scores` table: persists per-dimension rubrics with source_type, confidence, assessed_at, assessed_by
- `thesis/coverage.py`: computes CoverageSummary (provenance breakdown + evidence quality) per issuer
- `thesis/validation/evidence_sanity.py`: checks top-N evidence quality
- `thesis/validation/distribution.py`: structural alerts (bucket concentration, score spread)
- `thesis/validation/face_validity.py`: golden set checks
- `thesis/validation/sensitivity.py`: weight perturbation analysis
- `thesis/router.py`: 4 GET endpoints (list runs, get run, get ranking with coverage, get issuer detail)
- `run_plan2_validation.py`: CLI script that runs all 5 validation blocks, saves JSON report

### What's missing
- No per-run monitoring endpoint (coverage/provenance aggregated across dimensions)
- No drift computation between two runs
- No rubric aging computation
- No review queue endpoint
- Validation results not persisted per-run or exposed via API

### Key constraint
All data needed for monitoring is already persisted. The monitoring endpoints compute on-the-fly from:
- `plan2_thesis_scores.feature_input_json.provenance` → coverage/provenance/evidence
- Two runs' `plan2_thesis_scores` → drift
- `plan2_rubric_scores.assessed_at` → aging
- `plan2_rubric_scores.confidence` + aging + drift → review queue

## 5. Requirements

R1. Run monitoring summary endpoint: given a run_id, return aggregate coverage by dimension, provenance mix, confidence distribution, evidence quality distribution.

R2. Run drift endpoint: given two run_ids (or latest vs previous), return bucket changes, top-10/20 membership changes, per-issuer fragility delta, new/dropped issuers.

R3. Rubric aging endpoint: return stale rubrics (assessed_at > N days ago) grouped by dimension and issuer, with configurable staleness threshold.

R4. Review queue endpoint: return prioritized list combining low-confidence rubrics, old rubrics, and issuers with material bucket/rank changes.

R5. All endpoints read-only. No automated alerts, no UI. "Observabilidade primeiro."

R6. Return JSON suitable for future dashboard consumption.

## 6. Selected Shape

4 new endpoints on the existing `thesis/router.py` (FastAPI quant-engine):

```
GET /plan2/runs/{run_id}/monitoring     → R1
GET /plan2/runs/{run_id}/drift          → R2 (query param: vs_run_id, or auto-detect previous)
GET /plan2/rubrics/aging                → R3 (query param: stale_days=30)
GET /plan2/rubrics/review-queue         → R4
```

New module `thesis/monitoring.py` with pure computation functions (no DB access).
Router handles DB queries and passes data to monitoring functions.

### Appetite
- Level: Small (1 session)
- Why: All data already persisted, just computation + endpoint wiring
- Must-fit: R1 (monitoring summary) + R2 (drift) + R3 (aging) + R4 (review queue)
- First cuts if exceeded: sensitivity recomputation, UI, automated alerts

### Boundaries / No-gos
- No Alembic migration (no schema changes)
- No new tables
- No UI changes
- No automated alerting
- No changes to pipeline.py or scoring.py
- No NestJS proxy (quant-engine endpoints only for now)

### Rabbit Holes
- **Drift with different universe sizes**: Runs may have different issuers. Must handle new/dropped issuers.
- **Provenance JSON shape**: feature_input_json has nested provenance. Already handled in router.py `_provenance_from_json`.
- **Rubric aging with superseded_at**: Only count active rubrics (superseded_at IS NULL). Already filtered in pipeline._load_rubrics.

## 7. Build Scopes

### Scope 1: monitoring.py — pure computation functions
- `compute_run_monitoring(scores_data) -> RunMonitoringSummary`
- `compute_run_drift(current_scores, previous_scores) -> RunDrift`
- `compute_rubric_aging(rubrics, stale_days) -> RubricAgingReport`
- `compute_review_queue(rubrics, drift, stale_days) -> ReviewQueue`
- Done: functions exist, return typed dataclasses, unit-tested

### Scope 2: router endpoints + wiring
- Add 4 endpoints to thesis/router.py
- Wire DB queries to monitoring functions
- Done: endpoints return JSON, tested with existing DB data

### Scope 3: tests
- Unit tests for monitoring.py functions
- Done: tests pass, edge cases covered

## 8. Current Status

**Phase: Build complete — all 3 scopes done.**

### Scope 1: monitoring.py — DONE
- 4 pure computation functions: `compute_run_monitoring`, `compute_run_drift`, `compute_rubric_aging`, `compute_review_queue`
- 10 typed dataclasses for structured results
- 24 unit tests passing

### Scope 2: router endpoints — DONE
- `GET /plan2/runs/{run_id}/monitoring` — coverage, provenance mix, confidence, evidence quality
- `GET /plan2/runs/{run_id}/drift` — bucket changes, top-N changes, fragility deltas (auto-detects previous run)
- `GET /plan2/rubrics/aging` — stale rubrics by dimension/issuer (configurable `stale_days`)
- `GET /plan2/rubrics/review-queue` — prioritized queue (HIGH/MEDIUM/LOW) combining aging + confidence + drift

### Scope 3: tests — DONE
- 24 unit tests for monitoring.py (all 4 blocks + edge cases)
- 391 total quant-engine tests passing (0 regression)
- Ruff lint clean

### Validation evidence
- `python -m pytest` — 391 passed in 1.64s
- `python -m ruff check src/q3_quant_engine/thesis/` — All checks passed

## 9. Files changed

- `services/quant-engine/src/q3_quant_engine/thesis/monitoring.py` — NEW (4 computation functions + 10 dataclasses)
- `services/quant-engine/src/q3_quant_engine/thesis/router.py` — MODIFIED (4 new endpoints + 3 helper functions)
- `services/quant-engine/tests/thesis/test_monitoring.py` — NEW (24 tests)

## 10. Close Summary

F3.1 delivers 4 read-only monitoring endpoints on the quant-engine FastAPI router.
All computation is pure (no side effects, no schema changes, no migrations).
Data is computed on-the-fly from already-persisted plan2_runs, plan2_thesis_scores, and plan2_rubric_scores.

**What answers what:**
1. Evidence quality? → `/plan2/runs/{id}/monitoring` (coverage by dimension, provenance mix, evidence quality dist)
2. What changed? → `/plan2/runs/{id}/drift` (bucket changes, top-N, fragility deltas, new/dropped)
3. What needs review? → `/plan2/rubrics/aging` (stale rubrics by dimension/issuer)
4. Where is the risk? → `/plan2/rubrics/review-queue` (prioritized: HIGH=low-conf+stale or bucket-changed, MEDIUM=low-conf-only or stale-only, LOW=AI_ASSISTED periodic)

**Cuts:**
- No UI dashboard (future F3.2)
- No automated alerts (future F3.3)
- No NestJS proxy (endpoints are on quant-engine :8100 only for now)
- No historical trend storage (compute on-the-fly from existing runs)
