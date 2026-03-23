# 3C.1 — Entity Hardening

## Status: SHAPING COMPLETE — Ready for build

---

## 1. Micro Feature

**Limpar o estado quebrado de `securities`: resolver duplicatas de reimport, estabelecer regra deterministica de primary security, e garantir 1:1 issuer→primary para issuers com securities.**

## 2. Problem

O estado atual de `securities` tem 3 problemas concretos:

1. **Reimport duplicado**: 439 securities criadas em 2026-03-09 sao copias identicas das 439 de 2020-01-01. As copias tem 0 snapshots e inflam a compat view.
2. **Blanket is_primary**: `is_primary=true` em TODAS as 879 securities. Nao existe regra de selecao.
3. **Multi-ticker sem desempate**: 72 issuers tem ON+PN (ex: PETR3+PETR4), 6 tem ON+PN+UNIT. Sem primary definido, compat view produz linhas duplicadas por issuer.

## 3. Outcome

- 0 issuers com >1 current primary
- 0 securities duplicadas ativas (reimport superseded)
- `security_class` populado como derived metadata
- `primary_rule_version` + `primary_rule_reason` registrados
- Compat view com ~440 rows (1 per issuer, nao 710)
- Zero regressao em computed_metrics ou market_snapshots

## 4. Current System

- 879 securities, todas current (`valid_to IS NULL`)
- 711 com `is_primary=true` (todas exceto outlier INDEX)
- `security_class` NULL em 878/879
- Compat view: 710 rows (inflado por duplicatas)
- Market snapshots: 175,574 (todos em securities de 2020-01-01)
- 0 snapshots nas securities de 2026-03-09

## 5. Appetite

- **Level**: Small — 2 build scopes
- **Must-fit**: Scope A (dedup/supersede) + Scope B (primary selection)
- **First cut**: Scope C (diagnostics) pode ser inline, nao precisa de entregavel separado

## 6. Boundaries / No-Gos

### Boundaries
- Tocar: `securities` table (valid_to, is_primary, security_class)
- Gerar: relatorio before/after

### No-Gos
- NAO fazer hard delete (preservar audit trail via valid_to)
- NAO linkar orphan issuers (3C.1b)
- NAO criar issuer_security_map
- NAO criar market_panel_pti
- NAO modificar computed_metrics ou market_snapshots
- NAO chamar security_class inferida de "canonico"
- NAO chamar snapshot_count de "liquidez"

### Out of Scope
- Subsidiary-to-parent linkage
- Orphan ticker resolution
- Point-in-time enforcement
- Dataset versioning

## 7. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Suffix inference edge cases (tickers sem suffix padrao) | LOW | Fallback: security_class = NULL, nao inventar |
| UNIT (11) + underlying classes: qual e primary? | MEDIUM | UNIT nao e primary. Preferir underlying (3 ou 4) |
| Security sem snapshots que deveria ser primary | LOW | Snapshot count rule resolve — se nao tem dados, nao e util como primary |
| FK dependencies no security duplicado | LOW | Verificado: 0 snapshots nas duplicatas. Nenhum FK aponta para elas |
| Compat view cache stale apos mudanca | LOW | REFRESH apos build |

## 8. Build Scopes

### Scope A: Supersede duplicate securities

**Objective**: Marcar as 439 securities de 2026-03-09 como superseded.

**Implementation**:
```sql
UPDATE securities
SET valid_to = now(), is_primary = false
WHERE valid_from = '2026-03-09'::date;
```

**Done criteria**:
- 439 securities com valid_to NOT NULL
- 0 securities duplicadas com is_primary=true
- 0 snapshots afetados
- Compat view query funciona com WHERE valid_to IS NULL

**Validation**:
- Count securities where valid_to IS NULL = 440 (439 original + 1 INDEX)
- Count market_snapshots = 175,574 (unchanged)

**Risk focus**: Verificar que nenhuma query downstream assume valid_to IS NULL implicitamente.

---

### Scope B: Deterministic primary selection

**Objective**: Para issuers com multiplos tickers correntes, selecionar 1 primary.

**Rule: Data continuity proxy v1**

1. Se issuer tem 1 ticker corrente → primary
2. Se issuer tem multiplos tickers correntes:
   a. Contar snapshots por security (`SELECT security_id, count(*) FROM market_snapshots GROUP BY security_id`)
   b. Maior snapshot_count → primary
   c. Tiebreak: suffix 3 (ON) > 4 (PN) > 5 (PNA) > 6 (PNB) > 11 (UNIT)
   d. Ultimo tiebreak: menor security_id (deterministic)

**Metadata a registrar** (em securities ou log):
- `primary_rule_version = 'v1-data-continuity'`
- `primary_rule_reason = 'highest_snapshot_count'` ou `'tiebreak_suffix_3'` ou `'single_ticker'`

**security_class inference** (derived metadata):
- Ticker ending `3` → `ON`
- Ticker ending `4` → `PN`
- Ticker ending `5` → `PNA`
- Ticker ending `6` → `PNB`
- Ticker ending `11` → `UNIT`
- Other → NULL (nao inventar)

**Done criteria**:
- 0 issuers com >1 current primary (WHERE valid_to IS NULL AND is_primary = true)
- security_class populado para todas as securities com suffix reconhecivel
- primary_rule_version e primary_rule_reason registrados

**Validation**:
```sql
-- Zero multi-primaries
SELECT issuer_id, count(*) FROM securities
WHERE valid_to IS NULL AND is_primary = true
GROUP BY issuer_id HAVING count(*) > 1;
-- Must return 0 rows

-- Compat view row count
SELECT count(*) FROM v_financial_statements_compat;
-- Should be ~356 (1 per issuer with securities)
```

---

## 9. Validation Plan

### Per-scope
- Scope A: 439 superseded, 0 snapshots affected
- Scope B: 0 multi-primaries, compat rows ~356

### Post-build
- Refresh compat view
- NPY coverage (should be unchanged — 176, same issuers)
- Compat view row count (should drop from 710 to ~356)
- Existing queries still work (ranking.py, universe.service, asset.service)
- 184 tests still passing

### Evidence required
- Before/after security counts
- Before/after compat view counts
- Before/after multi-primary counts
- primary_rule_reason distribution

---

## 10. Current Status

**Status: BUILD COMPLETE — Awaiting Tech Lead review**

---

## 11. Validation Evidence

### Before/After Comparison

| Metric | Before | After | Target | Status |
|--------|-------:|------:|--------|--------|
| Total securities | 879 | 879 | unchanged | PASS |
| Current (valid_to IS NULL) | 879 | 440 | ~440 | PASS |
| Superseded (valid_to IS NOT NULL) | 0 | 439 | 439 | PASS |
| is_primary=true (current only) | 711 | 356 | 356 | PASS |
| Multi-primary issuers | 355 | **0** | 0 | PASS |
| Compat view rows | 710 | 355 | ~356 | PASS |
| Market snapshots | 175,574 | 175,574 | unchanged | PASS |
| security_class populated (current) | 1 | 439 | ~439 | PASS |
| security_class NULL (current) | 878 | 1 (^BVSP) | expected | PASS |
| NPY coverage in compat view | 176 | 176 | unchanged | PASS |

### Primary Rule Reason Distribution

| Reason | Count |
|--------|------:|
| single_ticker | 278 |
| highest_snapshot_count | 70 |
| tiebreak_suffix_3 | 8 |
| superseded_reimport | 439 |

### Security Class Distribution (current)

| Class | Count |
|-------|------:|
| ON | 342 |
| PN | 84 |
| UNIT | 13 |
| NULL (^BVSP index) | 1 |

### Regression Tests

- quant-engine: 415 passed, 0 failed
- fundamentals-engine: 184 passed, 0 failed

### Zero-orphan Primary Check

0 issuers with current securities but missing a primary.

---

## 12. Close Summary

### Delivered Scope
- **Scope A**: 439 duplicate securities from 2026-03-09 superseded (valid_to set, is_primary=false)
- **Scope B**: Deterministic primary selection for all 356 issuers with securities
  - 278 single-ticker (trivial)
  - 70 resolved by highest snapshot count
  - 8 resolved by suffix tiebreak (ON preferred)
- **Metadata**: primary_rule_version='v1-data-continuity' + primary_rule_reason recorded on all primaries and superseded records
- **security_class**: Populated from ticker suffix for 439/440 current securities (1 index = correct NULL)
- **Schema**: Added primary_rule_version and primary_rule_reason columns to securities
- **Dual ORM**: Both SQLAlchemy (entities.py) and Drizzle (schema.ts) updated
- **Migration**: 20260321_0017 — single migration covering schema + data

### Cuts / Deferrals
- Orphan linkage (3C.1b) — out of scope as agreed
- issuer_security_map — not needed, is_primary on securities is sufficient
- market_panel_pti — belongs to 3C.2

### Known Limitations
- 84 non-primary securities remain current (valid_to IS NULL) — these are PN/UNIT classes for multi-ticker issuers. They are correctly marked is_primary=false.
- ^BVSP index has no security_class (no ticker suffix pattern). Correct behavior.

### Follow-ups
- 3C.1b: Orphan linkage (~50-80 independently listed issuers) — optional
- 3C.2: Source tier tagging + research panel MVP
- 3C.3: Point-in-time enforcement + dataset versioning

---

## 13. Tech Lead Handoff

### Changes Made
1. **Migration** `20260321_0017`: Adds 2 columns, supersedes duplicates, implements primary selection, refreshes compat view
2. **SQLAlchemy model** `entities.py`: Added primary_rule_version, primary_rule_reason to Security
3. **Drizzle schema** `schema.ts`: Added primaryRuleVersion, primaryRuleReason to securities

### Review Focus
- Migration SQL correctness (window function for primary selection)
- Downgrade path preserves original state
- No hard deletes — audit trail via valid_to
- Compat view refreshed and row count correct

### Residual Risk
- LOW: Downstream queries that assumed all securities are current (valid_to IS NULL) without explicit filter. Verified: all Python code and compat view already filter correctly.
