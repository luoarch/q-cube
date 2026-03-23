# D1 — Soft Enforcement of Strategy Governance

## Status: BUILD COMPLETE — Awaiting Tech Lead review

---

## 1. Micro Feature

**Add soft enforcement gates to strategy execution surfaces.** When a user attempts to run a strategy that has been empirically rejected or is not yet promoted, a warning modal requires explicit acknowledgment before proceeding.

---

## 2. Problem

The strategy status registry exists and is visible, but execution is still frictionless for rejected strategies. A user can select `magic_formula_brazil` (REJECTED) and click "Calcular Ranking" without any friction. The status panel exists but is informational only — a user can ignore it entirely.

---

## 3. Design

### StrategyWarningGate component

A shared component that wraps execution buttons. On click:

1. **Check registry**: Does the selected `strategy_type` have any registered configs?
2. **If PROMOTED exists**: proceed immediately (no warning)
3. **If all REJECTED**: show warning modal (red border, strong language)
4. **If BLOCKED but not REJECTED**: show warning modal (yellow border, moderate language)
5. **If no registry entries**: proceed immediately (unvalidated, no claim either way)

### Warning modal content

- Shows all registered configs for the selected strategy_type
- Each config shows: strategy_key, role, promotion_status, evidence_summary, OOS Sharpe
- **REJECTED**: "Esta estratégia foi testada empiricamente e rejeitada na validação."
- **BLOCKED**: "Esta estratégia ainda não foi promovida. Prossiga com consciência das limitações."
- Two buttons: "Cancelar" (return) / "Entendo, prosseguir" (acknowledge and execute)

### Acknowledgment behavior

- First click on a non-promoted strategy → warning shown
- After acknowledging → subsequent clicks proceed without re-warning (session-level)
- Page refresh resets acknowledgment

### Surfaces covered

| Surface | Button | Strategy type | Gate |
|---------|--------|---------------|:----:|
| `/strategy` | "Calcular Ranking" | Selected from dropdown | YES |
| `/backtest` | "+ Novo Backtest" | Hardcoded `magic_formula_brazil` | YES |

### What this is NOT

- **NOT hard blocking** — user can always proceed after acknowledging
- **NOT strategy_type-level verdict** — the modal shows config-level entries from the registry
- **NOT auto-switching** — never changes the user's selection

---

## 4. Appetite

**Level: XS** — 1 build scope

---

## 5. Boundaries / No-Gos

- Do NOT prevent execution (soft, not hard)
- Do NOT change ranking behavior
- Do NOT change backtest engine
- Do NOT auto-select strategies
- Do NOT show warning for PROMOTED strategies
- Do NOT show warning for unregistered strategies (no evidence = no claim)

---

## 6. Validation Plan

| Check | Pass criteria |
|-------|---------------|
| V1 — Strategy page gate | Clicking "Calcular Ranking" with `magic_formula_brazil` selected shows warning |
| V2 — Backtest page gate | Clicking "+ Novo Backtest" shows warning (uses brazil default) |
| V3 — REJECTED content | Warning shows red styling + "rejeitada na validação" for rejected configs |
| V4 — BLOCKED content | Warning shows yellow styling + "não promovida" for blocked configs |
| V5 — Acknowledge | After clicking "Entendo, prosseguir", execution proceeds |
| V6 — Cancel | Clicking "Cancelar" returns without executing |
| V7 — No warning for promoted | If a PROMOTED entry exists, button proceeds without modal |
| V8 — Typecheck | Clean |

---

## 7. Close Summary

### Delivered

1. **StrategyWarningGate** component (`src/components/StrategyWarningGate.tsx`)
   - Shared gate wrapping execution buttons
   - Matches strategy_type against registry
   - Modal with config-level entries, evidence summary, OOS Sharpe
   - "Entendo, prosseguir" / "Cancelar" buttons
   - Session-level acknowledgment (no re-warning after first accept)

2. **Strategy page** (`/strategy`): "Calcular Ranking" button wrapped with gate
3. **Backtest page** (`/backtest`): "+ Novo Backtest" button wrapped with gate

### What the user sees

**When selecting `magic_formula_brazil` and clicking "Calcular Ranking":**

Modal appears with:
- ctrl_brazil_20m: CONTROL + REJECTED (red dot)
- Evidence summary + OOS Sharpe 0.01
- "Esta estratégia foi testada empiricamente e rejeitada na validação."
- [Cancelar] [Entendo, prosseguir]

**When selecting `magic_formula_hybrid` and clicking "Calcular Ranking":**

Modal appears with:
- hybrid_20q: FRONTRUNNER + BLOCKED (yellow dot)
- Evidence summary + OOS Sharpe 1.20
- "Esta estratégia ainda não foi promovida."
- [Cancelar] [Entendo, prosseguir]

### Typecheck: clean

---

## 8. Tech Lead Handoff

### What changed
- New: `src/components/StrategyWarningGate.tsx`
- Modified: `strategy/page.tsx` — button → StrategyWarningGate
- Modified: `backtest/page.tsx` — button → StrategyWarningGate

### What did NOT change
- Ranking pipeline
- Backtest engine
- Strategy registry
- API endpoints
- No hard blocking

### Key design decision
The gate matches by `strategy_type` to find relevant registry entries, then shows all config-level entries for that type. This means:
- `magic_formula_hybrid` shows hybrid_20q (BLOCKED) but also would show hybrid_20m (REJECTED) if registered
- The user sees the full picture per strategy family
- No config-level false precision on the type-level selector
