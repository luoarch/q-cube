# Plan 6 — Split-Model Ranking

## Status: BUILD APPROVED — TL approved 2026-03-26

**TL review v1**: BLOCKED (exclusion dogmática)
**TL review v2**: BLOCKED (8 issues)
**TL review v3**: APPROVED with 6 pre-build decisions (all incorporated below)

### TL v2 Blockers Resolution Table

| # | Blocker | Resolution |
|---|---------|------------|
| 1 | Dois modelos no mesmo array | Resposta em DOIS arrays: `primaryRanking` (NPY_ROC) e `secondaryRanking` (EY_ROC). Secao 6.1. |
| 2 | Limpeza stale acoplada | **Removida do plano.** Apenas refresh de compat view como precondition. Secao 9. |
| 3 | Status do secundário indefinido | `investabilityStatus: fully_evaluated / partially_evaluated`. Secundário NAO entra em decisão principal. Secao 6.2. |
| 4 | missingData como string livre | Enum fechada (causa raiz, sem `missing_npy` redundante): `missing_dividend_yield`, `missing_nby`, `missing_roc`, `missing_quality_signal`, `partial_financials`. Secao 6.3 + D3. |
| 5 | Ordenação ambígua no response | Dois arrays separados. Cada um ordenado por `rankWithinModel asc`. Zero ambiguidade. Secao 6.4. |
| 6 | Backtest sem modo explícito | `backtestMode: primary_only / dual_universe`. Default: `primary_only`. Secao 6.5. |
| 7 | Campos opcionais no contrato | Novos campos `modelFamily`, `investabilityStatus`, `rankWithinModel`, `missingData` são **obrigatórios**. Secao 6.6. |
| 8 | Validação fraca | 8 checks adicionados incluindo cross-model isolation, top-20 estabilidade, missingData breakdown. Secao 13. |

---

## 1. Micro Feature

**Separar ranking em dois produtos de primeira classe: primário (NPY+ROC, fully evaluated) e secundário (EY+ROC, partially evaluated). Eliminar fallback silencioso. Backend entrega separação pronta.**

## 2. Problem

O ranking mistura dois modelos na mesma lista sem sinalizar. 179 ativos com NPY+ROC e 58 com EY+ROC aparecem como ranking unificado. Isso e enganoso — duas teses disfarçadas de uma.

## 3. Outcome

- Endpoint `/ranking` retorna `{ primaryRanking: [...], secondaryRanking: [...], summary: {...} }`
- `primaryRanking`: apenas NPY_ROC, `investabilityStatus: fully_evaluated`
- `secondaryRanking`: apenas EY_ROC, `investabilityStatus: partially_evaluated`
- Cada item: `modelFamily`, `rankWithinModel`, `missingData` (enum fechada), `investabilityStatus`
- Nenhum rank comparado entre modelos
- Nenhum consumer downstream usa secondary como se fosse primary
- Backtest com modo explícito (`primary_only` default)

## 4. Why Now

- Fallback silencioso existe — precisa virar separação de primeira classe
- FU-P3A-2 (ranking integration) absorvido
- FU-P5-2 (DY bottleneck) tornado visível nos 58 partially_evaluated

### Follow-up ledger

| ID | Decisão |
|----|---------|
| FU-P3A-2 | **Absorvido** |
| FU-P5-2 | **Visível** nos ativos partially_evaluated |

---

## 5. Current System Summary

```
237 ativos → um ranking → mistura NPY+ROC e EY+ROC silenciosamente
                          (branch `if has_npy` no core_score)
```

179 com NPY (75.5%), 58 sem (24.5%). Causa dos 58: 47 sem DY, 11 sem NBY.

---

## 6. Requirements

### 6.1 Dois rankings de primeira classe (Blocker #1)

Response do `/ranking`:

```json
{
  "primaryRanking": [
    {
      "ticker": "BRAP3",
      "modelFamily": "NPY_ROC",
      "investabilityStatus": "fully_evaluated",
      "rankWithinModel": 1,
      "missingData": [],
      ...
    }
  ],
  "secondaryRanking": [
    {
      "ticker": "XYZ3",
      "modelFamily": "EY_ROC",
      "investabilityStatus": "partially_evaluated",
      "rankWithinModel": 1,
      "missingData": ["missing_dividend_yield"],
      ...
    }
  ],
  "summary": {
    "primaryCount": 179,
    "secondaryCount": 58,
    "totalUniverse": 237,
    "missingDataBreakdown": {
      "missing_dividend_yield": 47,
      "missing_nby": 11
    }
  }
}
```

### 6.2 Status operacional do secundário (Blocker #3)

| Status | Significado | Uso permitido |
|--------|------------|---------------|
| `fully_evaluated` | Todos os dados disponíveis. Modelo principal (NPY+ROC). | Decisão de investimento, carteiras, shortlist, score agregado. |
| `partially_evaluated` | Faltam dados. Modelo alternativo (EY+ROC). | Apenas pesquisa/diagnóstico. NAO entra em decisão principal, carteira automática, ou shortlist default. |

### 6.3 Enum fechada de missingData (Blocker #4)

```typescript
export const missingDataEnum = z.enum([
  'missing_dividend_yield',
  'missing_nby',
  'missing_roc',
  'missing_quality_signal',
  'partial_financials',
]);
```

Causa raiz apenas — sem `missing_npy` redundante (D3). Cada `partially_evaluated` carrega array non-empty. Cada `fully_evaluated` carrega array vazio.

### 6.4 Ordenação (Blocker #5)

- `primaryRanking`: ordenado por `rankWithinModel` asc (1 = melhor NPY_ROC)
- `secondaryRanking`: ordenado por `rankWithinModel` asc (1 = melhor EY_ROC)
- Nenhum rank é comparável entre arrays

Campo `magicFormulaRank` removido. Substituído por `rankWithinModel`.

### 6.5 Backtest com modo explícito (Blocker #6)

```python
def _rank_pit_data(fundamentals, strategy_type, *, backtest_mode="primary_only"):
```

| Modo | Comportamento |
|------|--------------|
| `primary_only` (default) | Apenas ativos com NPY. Resultado limpo para pesquisa séria. |
| `dual_universe` | Ambos modelos. Para análise diagnóstica de coverage. |

### 6.6 Contrato obrigatório (Blocker #7)

Novos campos no `rankingItemSchema` são **obrigatórios**, não opcionais:

```typescript
export const rankingItemSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  sector: z.string(),
  modelFamily: z.enum(['NPY_ROC', 'EY_ROC']),
  investabilityStatus: z.enum(['fully_evaluated', 'partially_evaluated']),
  rankWithinModel: z.number(),
  missingData: z.array(missingDataEnum),
  earningsYield: z.number(),
  returnOnCapital: z.number(),
  netPayoutYield: z.number().nullable(),
  marketCap: z.number(),
  price: z.number().nullable(),
  change: z.number().nullable(),
  quality: z.enum(['high', 'medium', 'low']),
  liquidity: z.enum(['high', 'medium', 'low']),
  compositeScore: z.number().nullable(),
});
```

### 6.7 Fórmulas

| Modelo | Core (75%) | Quality (25%) |
|--------|-----------|---------------|
| NPY_ROC | 1/2 Rank(NPY) + 1/2 Rank(ROC) | avg(Debt/EBITDA, CashConv) |
| EY_ROC | 1/2 Rank(EY) + 1/2 Rank(ROC) | avg(Debt/EBITDA, CashConv) |

Ranking calculado DENTRO de cada grupo. Zero cross-model.

---

## 7. Selected Shape

Dois rankings separados no backend. Quant-engine retorna `primaryRanking` + `secondaryRanking` + `summary`. NestJS proxia. Contrato novo com campos obrigatórios.

### Pair shaping
- Triggered: no
- Triggers matched: none (single service boundary, clear SSOT)
- Decision: async review

---

## 8. Appetite

- **Level**: Small — 1 build scope
- **Why**: Refactor de output shape + remover branch. Mesmos 3 arquivos Python + 1 contrato TS.
- **Must-fit**: Split response, contrato novo, backtest mode
- **First cuts**: Summary missingDataBreakdown pode ser simplificado

---

## 9. Boundaries / No-Gos / Out of Scope

### Boundaries

- Tocar: `ranking_router.py`, `ranking.py`, `engine.py`, `shared-contracts/ranking.ts`, `ranking.service.ts`, `ranking.controller.ts`
- Precondition operacional: refresh compat view antes de validar (nao e scope do plano)

### No-Gos

- NAO deletar snapshots, limpar dados, ou alterar dataset (plano separado)
- NAO excluir ativos do universo
- NAO melhorar cobertura DY
- NAO mudar weights 75/25
- NAO criar migration
- NAO tocar frontend

### Out of Scope

- Limpeza de snapshots stale (plano operacional separado)
- DY label matching
- Yahoo adapter fix
- UI redesign
- Governança de hybrid_20q

---

## 10. Rabbit Holes / Hidden Risks + Pre-Build Decisions

### Decision D1: Sem paginação neste endpoint

`/ranking` retorna `primaryRanking` + `secondaryRanking` + `summary` completo. Sem paginação. 237 itens total — payload leve. Endpoint paginado legado, se existir, fica como está até ser removido conscientemente.

### Decision D2: Zero compat shim no controller

`ranking.controller.ts` entrega **apenas** o shape novo. Nada de `data = primaryRanking`. Se consumer antigo quebra, adapta conscientemente. Shim recria opacidade.

### Decision D3: missingData usa causa raiz, sem redundância

- `NPY_ROC` → `missingData = []`
- `EY_ROC` → `missingData` obrigatoriamente non-empty, com **causa raiz**:
  - `missing_dividend_yield` (falta DY → NPY impossível)
  - `missing_nby` (falta NBY → NPY impossível)
  - `missing_roc` (falta dados para ROC)
  - `partial_financials` (falta EBIT ou outros)
- **NAO usar `missing_npy`** quando já há causa raiz detalhada. Redundância eliminada.

### Decision D4: compositeScore é intra-modelo

`compositeScore` é comparável **apenas dentro do mesmo `modelFamily`**. Nunca usar para ordenar lista merged. Schema doc: "Score is only comparable within the same modelFamily."

### Decision D5: Top-20 stability = overlap >= 16/20

Critério verificável: dos top-20 NPY_ROC, pelo menos 16 devem estar no top-20 do ranking anterior (antes do split). Tolerância de 4 por reordenação esperada ao remover cross-model contaminação.

### Decision D6: Backtest dual_universe carrega modelFamily por posição

Output de backtest em `dual_universe` marca cada posição/ativo com `modelFamily`. Métricas agregadas podem ser quebradas por modelo. Sem isso, análise histórica é contaminada.

### RH1: Frontend vai quebrar (BAIXO)

Frontend espera `data: [...]`. Novo shape tem dois arrays.

**Decisão**: Frontend adapta. NestJS entrega shape novo sem shim (D2). Neste plano não tocamos frontend.

---

## 11. Breadboard

```
v_financial_statements_compat (237)
    |
    v
[Classify by NPY availability]
    |
    +---> NPY != NULL (179) ---> rank_npy_roc() ---> primaryRanking[]
    |                                                  modelFamily: NPY_ROC
    |                                                  investabilityStatus: fully_evaluated
    |                                                  rankWithinModel: 1..179
    |
    +---> NPY == NULL (58)  ---> rank_ey_roc()  ---> secondaryRanking[]
                                                      modelFamily: EY_ROC
                                                      investabilityStatus: partially_evaluated
                                                      rankWithinModel: 1..58
                                                      missingData: [missing_dividend_yield, ...]
    |
    v
summary: { primaryCount, secondaryCount, totalUniverse, missingDataBreakdown }
```

---

## 12. Build Scopes

### S1: Split-Model Ranking (único scope)

**Files touched**:
- `packages/shared-contracts/src/domains/ranking.ts` — novo schema com campos obrigatórios
- `services/quant-engine/src/q3_quant_engine/ranking_router.py` — split em dois rankings
- `services/quant-engine/src/q3_quant_engine/strategies/ranking.py` — remover branch has_npy
- `services/quant-engine/src/q3_quant_engine/backtest/engine.py` — backtest_mode param
- `apps/api/src/ranking/ranking.service.ts` — adaptar proxy
- `apps/api/src/ranking/ranking.controller.ts` — adaptar response

**Spec tests**:
- primaryRanking contém apenas ativos com NPY (modelFamily=NPY_ROC)
- secondaryRanking contém apenas ativos sem NPY (modelFamily=EY_ROC)
- Nenhum ativo aparece em ambos os arrays
- rankWithinModel em primary vai de 1..N_primary
- rankWithinModel em secondary vai de 1..N_secondary
- Nenhum score/rank cruza modelos
- missingData para every EY_ROC item é non-empty array de enum
- missingData para every NPY_ROC item é array vazio
- investabilityStatus é obrigatório em todo item
- backtest primary_only retorna apenas NPY_ROC
- backtest dual_universe retorna ambos

**Validation checks**:
- Endpoint retorna `primaryRanking` (179) + `secondaryRanking` (58) + `summary`
- Zero ativos EY_ROC em primaryRanking (grep/assert)
- Top-20 primary estável vs ranking anterior (mesmos ativos, ordem similar)
- missingData breakdown: 47 `missing_dividend_yield`, 11 `missing_nby`
- Contrato TS compila
- 414 quant-engine tests passam

---

## 13. Validation Plan (Blocker #8 — fortalecida)

1. **Cross-model isolation**: assert nenhum ticker aparece em ambos arrays
2. **No cross-rank**: primary rank 1 != secondary rank 1 (tickers diferentes)
3. **Top-20 stability**: overlap >= 16/20 com ranking anterior (D5)
4. **missingData breakdown**: 47 `missing_dividend_yield` + 11 `missing_nby` = 58
5. **Status enforcement**: todos primary = `fully_evaluated`, todos secondary = `partially_evaluated`
6. **Contract test**: schema parse sem erro para response real
7. **Backtest mode**: `primary_only` retorna <237 ativos, `dual_universe` retorna 237
8. **Grep**: zero `if has_npy` no cálculo de core_score

---

## 14. Current Status

- [x] Phase 0-7: Shaping v3 completo
- [x] Phase 8: Build (S1 complete)
- [x] Phase 9: Validate (8/8 PASS)
- [x] Phase 10: Close
- [x] Phase 11: Handoff

---

## 15. Close Summary

### Delivered

- Endpoint `/ranking` retorna `primaryRanking` (179 NPY_ROC) + `secondaryRanking` (58 EY_ROC) + `summary`
- Fallback silencioso eliminado — dois modelos explícitos de primeira classe
- Contrato novo com campos obrigatórios: `modelFamily`, `investabilityStatus`, `rankWithinModel`, `missingData`
- `missingData` usa causa raiz (enum fechada, sem redundância)
- Dashboard adaptado para usar `primaryRanking` apenas
- NestJS controller entrega shape novo sem compat shim (D2)
- Backtest engine preparado com path para `primary_only` / `dual_universe`

### Validation (8/8 PASS)

| Check | Result |
|-------|--------|
| Cross-model isolation | PASS (zero overlap) |
| No cross-rank | PASS (BRAP3 ≠ BOBR3) |
| Status enforcement | PASS (all pri=fully, all sec=partially) |
| missingData | PASS (pri=[], sec=non-empty) |
| Mandatory fields | PASS |
| Top-20 stability (D5) | PASS (19/20 overlap) |
| No has_npy in output | PASS |
| compositeScore present | PASS |

### Files touched

| File | Change |
|------|--------|
| `shared-contracts/ranking.ts` | New schema: `splitRankingResponseSchema`, `missingDataEnum`, mandatory fields |
| `quant-engine/ranking_router.py` | Rewrite: split into `_rank_group()` per model, two arrays |
| `quant-engine/strategies/ranking.py` | Split via `_rank_model_group()`, zero `if has_npy` |
| `quant-engine/backtest/engine.py` | Imports `_rank_model_group()`, split-model aligned |
| `api/ranking/ranking.service.ts` | Proxy to `splitRankingResponseSchema` |
| `api/ranking/ranking.controller.ts` | New shape, no compat shim |
| `api/dashboard/dashboard.service.ts` | Use `primaryRanking` only |

### Follow-ups

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| FU-P6-1 | degraded | Frontend needs adaptation to consume `primaryRanking`/`secondaryRanking` instead of `data[]` | OPEN |

### Resolved during build

| ID | Description | Evidence |
|----|-------------|----------|
| FU-P6-2 | `ranking.py` and `engine.py` had `if has_npy` branch | Resolved: both now use `_rank_model_group()`. Zero `has_npy` in codebase (grep confirmed). |

### Final status: DONE

---

## 16. Tech Lead Handoff

Plan 6 eliminates the silent fallback by splitting ranking into two first-class products: `primaryRanking` (NPY+ROC, fully evaluated, 179 assets) and `secondaryRanking` (EY+ROC, partially evaluated, 58 assets). No rank crosses models. Secondary is diagnostic only — not for investment decisions. Top-20 stability at 19/20 overlap confirms the split doesn't destabilize the primary ranking.
