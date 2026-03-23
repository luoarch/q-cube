# Strategy Status Governance

## Status: BUILD COMPLETE (Registry + Exposure) — Awaiting Tech Lead review

---

## 1. Micro Feature

**Create a strategy status registry as single source of truth for empirical validation outcomes.** Two orthogonal dimensions: methodological role + promotion status.

---

## 2. Problem

Empirical verdicts exist only in markdown docs. The system has no formal concept of strategy role or promotion state.

---

## 3. Schema

### Enums (2 orthogonal dimensions)

```python
class StrategyRole(str, Enum):
    CONTROL = "CONTROL"           # Baseline for comparison, not intended for promotion
    CANDIDATE = "CANDIDATE"       # Under evaluation
    FRONTRUNNER = "FRONTRUNNER"   # Best performer so far, lead research candidate

class PromotionStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"  # No validation run yet
    BLOCKED = "BLOCKED"              # Evaluated, does not pass all checks
    PROMOTED = "PROMOTED"            # Passes all promotion checks
    REJECTED = "REJECTED"            # Evaluated, definitively rejected
```

This cleanly separates role from promotion:

| strategy_key | role | promotion_status |
|-------------|------|:----------------:|
| ctrl_original_20m | CONTROL | REJECTED |
| ctrl_brazil_20m | CONTROL | REJECTED |
| hybrid_20q | FRONTRUNNER | BLOCKED |

### Table: `strategy_status_registry`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `strategy_key` | VARCHAR(100) | Human alias ("hybrid_20q") |
| `strategy_fingerprint` | VARCHAR(64) | SHA-256 hash of canonical config (deterministic identity) |
| `strategy_type` | enum strategy_type | Reuses existing pgEnum from schema |
| `role` | enum StrategyRole | Methodological role |
| `promotion_status` | enum PromotionStatus | Validation outcome |
| `config_json` | JSONB | Full canonical config (top_n, rebalance_freq, cost_model, etc.) |
| `evidence_summary` | TEXT | Human-readable verdict |
| `experiment_ids` | JSONB | List of experiment_id hashes linked to this verdict |
| `is_sharpe_avg` | NUMERIC | Avg IS Sharpe across validation splits |
| `oos_sharpe_avg` | NUMERIC | Avg OOS Sharpe across validation splits |
| `promotion_checks` | JSONB | Per-check: {result, observed, threshold, note} |
| `decided_at` | TIMESTAMPTZ | When verdict was set |
| `decided_by` | enum DecisionSource | Who/what decided |
| `superseded_at` | TIMESTAMPTZ | NULL = current |

### Partial unique index

```sql
CREATE UNIQUE INDEX uq_strategy_status_active
ON strategy_status_registry (strategy_fingerprint)
WHERE superseded_at IS NULL;
```

Note: keyed by `strategy_fingerprint` (not `strategy_key`), because the fingerprint is the true canonical identity.

### Additional enums

```python
class DecisionSource(str, Enum):
    TECH_LEAD_REVIEW = "TECH_LEAD_REVIEW"
    AUTOMATED_PIPELINE = "AUTOMATED_PIPELINE"
```

### Strategy fingerprint

Deterministic SHA-256 hash of the canonical config:

```python
def compute_fingerprint(config: dict) -> str:
    canonical = json.dumps({
        "strategy_type": config["strategy_type"],
        "top_n": config["top_n"],
        "rebalance_freq": config["rebalance_freq"],
        "cost_model_proportional": config["cost_model"]["proportional"],
        "cost_model_slippage": config["cost_model"]["slippage_bps"],
        "equal_weight": config["equal_weight"],
        "universe_policy_version": config.get("universe_policy_version", "v1"),
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

The fingerprint is the **true link** between the registry entry and the experiment artifacts. `strategy_key` is just a human label.

### Promotion checks format

```json
{
  "pit_validated": {
    "result": "PASS",
    "observed": true,
    "threshold": true,
    "note": "publication_date PIT throughout"
  },
  "oos_real": {
    "result": "PASS",
    "observed": 1.2048,
    "threshold": 0.3,
    "note": "avg OOS Sharpe across 3 annual splits"
  },
  "real_costs": {
    "result": "PASS",
    "observed": "BRAZIL_REALISTIC",
    "threshold": "any_cost_model",
    "note": "5bps proportional + 10bps slippage"
  },
  "dsr_threshold": {
    "result": "PASS",
    "observed": 1.0,
    "threshold": 0.5,
    "note": "best split DSR (Split 2 = 1.000)"
  },
  "sensitivity_stable": {
    "result": "FAIL",
    "observed": "sharpe_range_0.04_to_2.77",
    "threshold": "dispersion_lt_100pct",
    "note": "high OOS Sharpe dispersion across splits"
  },
  "manifest_valid": {
    "result": "PASS",
    "observed": true,
    "threshold": true,
    "note": "experiment artifacts reproducible"
  }
}
```

---

## 4. Seed Data

### ctrl_original_20m

```python
{
    "strategy_key": "ctrl_original_20m",
    "strategy_fingerprint": compute_fingerprint({...}),
    "strategy_type": "magic_formula_original",
    "role": StrategyRole.CONTROL,
    "promotion_status": PromotionStatus.REJECTED,
    "config_json": {"strategy_type": "magic_formula_original", "top_n": 20, "rebalance_freq": "monthly", ...},
    "evidence_summary": "Walk-forward v2: worst OOS performer across 3 annual splits. Avg OOS Sharpe 0.09.",
    "experiment_ids": ["2ac6848485f05b20"],
    "is_sharpe_avg": 0.49,
    "oos_sharpe_avg": 0.09,
    "promotion_checks": {"oos_real": {"result": "FAIL", "observed": 0.09, "threshold": 0.3}},
    "decided_by": DecisionSource.TECH_LEAD_REVIEW,
}
```

### ctrl_brazil_20m

```python
{
    "strategy_key": "ctrl_brazil_20m",
    "role": StrategyRole.CONTROL,
    "promotion_status": PromotionStatus.REJECTED,
    "evidence_summary": "Walk-forward v2: gates worsened OOS vs Original. Avg OOS Sharpe 0.01.",
    "oos_sharpe_avg": 0.01,
    "promotion_checks": {"oos_real": {"result": "FAIL", "observed": 0.01, "threshold": 0.3}},
}
```

### hybrid_20q

```python
{
    "strategy_key": "hybrid_20q",
    "role": StrategyRole.FRONTRUNNER,
    "promotion_status": PromotionStatus.BLOCKED,
    "evidence_summary": "Walk-forward v2: 3/3 wins vs controls, 3/3 OOS positive. Avg Sharpe 1.20. Blocked by sensitivity (high dispersion).",
    "oos_sharpe_avg": 1.20,
    "promotion_checks": {full 6-check structure as above},
}
```

---

## 5. Appetite

**Level: XS** — 1 build scope

### Must-fit:
- Migration (table + 3 enums + partial unique index)
- SQLAlchemy model
- Drizzle schema
- Seed script with 3 entries + fingerprints
- Promotion checks in structured format

### First cuts:
- API exposure → follow-up
- UI badges → follow-up
- Automated promotion pipeline → follow-up
- Language enforcement → follow-up

---

## 6. Boundaries / No-Gos

- Do NOT change ranking behavior
- Do NOT expose in API yet
- Do NOT auto-promote
- Do NOT modify empirical results
- `strategy_type` must reuse existing pgEnum

---

## 7. Validation Plan

| Check | Pass criteria |
|-------|---------------|
| V1 — Table + 3 enums | Migration clean |
| V2 — 3 entries seeded | All with correct role + promotion_status |
| V3 — Fingerprints | Deterministic, match experiment configs |
| V4 — Promotion checks | Structured with observed/threshold/result |
| V5 — Partial unique | Cannot insert 2 active rows for same fingerprint |
| V6 — Dual ORM | SQLAlchemy + Drizzle aligned |
| V7 — State expression | ctrl_original = CONTROL+REJECTED, ctrl_brazil = CONTROL+REJECTED, hybrid_20q = FRONTRUNNER+BLOCKED |

---

## 8. Close Summary

### Delivered

1. **Migration** `20260321_0022`: 3 pgEnums (strategy_role, promotion_status, decision_source) + strategy_status_registry table + partial unique index on fingerprint
2. **SQLAlchemy model**: `StrategyStatusRegistry` in shared-models-py
3. **Drizzle schema**: `strategyStatusRegistry` + 3 enum exports
4. **Seed**: 3 entries with correct role + promotion_status + fingerprints + structured promotion_checks

### Registry state

| strategy_key | role | promotion_status | OOS Sharpe | fingerprint |
|-------------|------|:----------------:|:----------:|-------------|
| ctrl_original_20m | CONTROL | REJECTED | 0.09 | 7c39f500e909d0eb |
| ctrl_brazil_20m | CONTROL | REJECTED | 0.01 | 61559eec643f413d |
| hybrid_20q | FRONTRUNNER | BLOCKED | 1.20 | 8a3ede51c1f12f77 |

### Validation

| Check | Result |
|-------|--------|
| V1 — Table + enums | PASS |
| V2 — 3 entries seeded | PASS |
| V3 — Fingerprints deterministic | PASS |
| V4 — Partial unique (duplicate blocked) | PASS |
| V5 — Dual ORM (Drizzle typecheck) | PASS |
| V6 — Typecheck | PASS |
| V7 — State expression (CONTROL+REJECTED, FRONTRUNNER+BLOCKED) | PASS |

### Tests: 414 quant-engine, 0 regressions

---

## 9. Tech Lead Handoff

### What changed
- Migration `20260321_0022`: new table + 3 enums
- `entities.py`: `StrategyStatusRegistry` model
- `schema.ts`: Drizzle table + 3 enum exports
- `scripts/seed_strategy_registry.py`: seed with empirical verdicts

### What did NOT change
- Ranking pipeline
- Backtest engine
- API endpoints
- UI

### Registry is SSOT for decisional state
- Points to experiment artifacts via experiment_ids
- Does NOT replace artifact store
- Future status changes = supersede old row + insert new
