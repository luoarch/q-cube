# Shape Up — Global Thesis Layer (Plan 2)

## 1. Micro Feature

**Request original:** Criar um modo tematico "Global Thesis Rank" que reorganiza empresas aprovadas no core ranking, priorizando aderencia ao ciclo de commodities e penalizando fragilidade ao dolar/funding global.

**Avaliacao:** A request e grande demais para um unico micro feature. Decomposta em micro features com grafo de dependencia corrigido.

**Decomposicao corrigida (v2 — pos-review Tech Lead):**

| # | Micro Feature | Escopo | Depende de |
|---|---------------|--------|------------|
| 0 | **Specs** | Universe, Feature Semantics, Dependency Graph, Versioning | — |
| A | **Contracts + Scoring Engine** | Zod schemas (incl. Plan2FeatureDraft + Plan2FeatureInput) + pure functions Python + testes | 0 |
| F1 | **Feature Engineering — Automatico** | Sector proxy maps + refinancingStress quantitativo → Plan2FeatureDraft | 0 |
| B1 | **Persistence Schema** | Tabelas plan2_runs + plan2_thesis_scores (Alembic + SQLAlchemy + Drizzle) | 0 |
| B2 | **Pipeline Execution** | Celery task: F1 draft → completa input → chama A → persiste | A, F1, B1 |
| C | **API Endpoints** | GET /thesis-rank, GET /thesis-rank/:ticker | B2 |
| D | **Web UI — Toggle + Ranking** | Toggle Core/Thesis, bucket badges, score column | C |
| E | **Web UI — Breakdown** | Detalhe por ticker, vectors, positives/negatives | C |
| F2 | **Feature Engineering — Rubric System** | UI para input manual de rubricas com evidencia | B1 |
| G | **Validation Framework** | Sanity, sensitivity, stability, face validity | B2 |

**Grafo de execucao:**

```
Wave 1 (paralelo): MF-A + MF-F1 + MF-B1
Wave 2:            MF-B2
Wave 3 (paralelo): MF-C + MF-F2
Wave 4 (paralelo): MF-D + MF-E + MF-G
```

**Specs detalhados:** Ver `spec-01-*.md` a `spec-04-*.md` neste diretorio.

---

## 2. Problem

O Q3 so tem um ranking universal (Magic Formula + Refiner). Nao ha como expressar uma tese tematica que reorganize os ativos ja aprovados. O usuario quer ver: "entre as empresas boas, quais capturam melhor o ciclo de commodities e tem menor fragilidade ao dolar?"

## 3. Outcome

O sistema passa a ter dois rankings:
- **Q3 Core Rank** — ranking universal (value + qualidade + seguranca + refiner) — inalterado
- **Q3 Global Thesis Rank** — ranking tematico, so empresas aprovadas no core, reordenadas pela tese

## 4. Current System Summary

### Ranking pipeline atual
```
Universe (v_financial_statements_compat)
  -> Magic Formula (EY + ROC ranking)
  -> Refiner (top 30 HARDCODED: earnings quality, safety, operating consistency, capital discipline)
  -> Adjusted Rank (0.85 * base + 0.15 * refiner)
  -> Persist (strategy_runs.result_json + refinement_results table)
```

### Constraint critico descoberto no review
O **refiner roda apenas no top 30** (`top_n=30` hardcoded em `strategy.py:55`).
Isso significa que a elegibilidade do Plan 2 **NAO pode depender de refiner scores** sem limitar artificialmente o universo.

### Decisao: Universo do Plan 2
**Universo = todos os ativos que passam no core screening (~80-150 empresas).**
Elegibilidade usa computed_metrics (disponiveis para todos), nao refiner scores.
Detalhes em `spec-01-universe-eligibility.md`.

### Decisao: Feature Engineering vs Scoring Engine
**Fronteira clara:**
- Feature Engineering (MF-F1/F2): transforma dados brutos em scores 0-100 com provenance
- Scoring Engine (MF-A): recebe scores 0-100, computa composites, buckets, ranking
- O Scoring Engine NUNCA acessa DB ou transforma dados brutos
Detalhes em `spec-02-feature-semantics.md`.

### Dados disponiveis
| Camada | Status | Tabela |
|--------|--------|--------|
| Fundamentals (12 metricas) | Disponivel para TODOS os issuers | computed_metrics, statement_lines |
| short_term_debt, long_term_debt | Disponivel (canonical keys) | statement_lines |
| debt_to_ebitda, interest_coverage | Disponivel (computed) | computed_metrics |
| Setor/subsetor/segmento | Disponivel | issuers (CVM cadastro) |
| Quality scoring (4 blocos) | Apenas top 30 | refinement_results |
| Exposicao geografica | Nao existe | — |
| Divida por moeda | Nao existe | — |
| Revenue por moeda | Nao existe | — |

### Resumo de source types no MVP
| Dimensao | Source | Automatizado? |
|----------|--------|---------------|
| directCommodityExposure | SECTOR_PROXY + rubrica override | Sim (proxy) |
| indirectCommodityExposure | SECTOR_PROXY + rubrica override | Sim (proxy) |
| exportFxLeverage | RUBRIC_MANUAL (fallback: derivado) | Nao |
| refinancingStress | QUANTITATIVE (computed_metrics) | Sim, 100% |
| usdDebtExposure | RUBRIC_MANUAL (fallback: proxy) | Nao |
| usdImportDependence | RUBRIC_MANUAL (fallback: default) | Nao |
| usdRevenueOffset | RUBRIC_MANUAL (fallback: derivado) | Nao |

### Arquivos-chave
| Componente | Path |
|------------|------|
| Strategy contracts | `packages/shared-contracts/src/domains/strategy.ts` |
| Ranking contracts | `packages/shared-contracts/src/domains/ranking.ts` |
| Refiner contracts | `packages/shared-contracts/src/domains/refiner.ts` |
| Ranking engine | `services/quant-engine/src/q3_quant_engine/strategies/ranking.py` |
| Strategy task | `services/quant-engine/src/q3_quant_engine/tasks/strategy.py` |
| Refiner engine | `services/quant-engine/src/q3_quant_engine/refiner/engine.py` |
| SQLAlchemy models | `packages/shared-models-py/src/q3_shared_models/entities.py` |
| Drizzle schema | `apps/api/src/db/schema.ts` |
| API strategy controller | `apps/api/src/strategy/strategy.controller.ts` |
| Web ranking page | `apps/web/app/(dashboard)/ranking/page.tsx` |

---

## MICRO FEATURE A: Contracts + Scoring Engine (v2 — pos-review)

### 5. Requirements (corrigidos)

| # | Requirement | Type | Mudou? |
|---|-------------|------|--------|
| R1 | Zod schemas: BaseEligibility (com failed_reasons), ScoreProvenance, OpportunityVector, FragilityVector, ThesisBucket, Plan2FeatureDraft, Plan2FeatureInput, Plan2RankingSnapshot, Plan2Explanation, Plan2RankResponseItem | Contract | Sim — adicionado FeatureDraft, failed_reasons, ScoreProvenance |
| R2 | `check_base_eligibility(passed_core_screening, has_valid_financials, interest_coverage, debt_to_ebitda) -> BaseEligibility` — assinatura canonica com 4 params, retorna failed_reasons | Engine | Sim — assinatura unica, sem refiner |
| R3 | `compute_final_commodity_affinity_score()` com 3 dimensoes MVP (pesos redistribuidos) | Engine | Sim — 3 dimensoes, nao 4 |
| R4 | `compute_final_dollar_fragility_score()` com 4 dimensoes MVP | Engine | Sim — 4 dimensoes, nao 6 |
| R5 | `assign_thesis_bucket()` com thresholds como constantes | Engine | Igual |
| R6 | `compute_thesis_rank_score()` | Engine | Igual |
| R7 | `sort_plan2_rank()` com bucket precedence absoluta | Engine | Igual |
| R8 | `generate_explanation()` deterministica (template-based) | Engine | Novo — geracao basica inclusa |
| R9 | Testes unitarios com edge cases e boundary values | Test | Igual |
| R10 | Thesis config version como constante nomeada | Engine | Novo |

### 6. Candidate Shapes

#### Shape 1: Novo dominio `thesis.ts` em shared-contracts + novo modulo `thesis/` em quant-engine

**Contracts:**
- `packages/shared-contracts/src/domains/thesis.ts` — todos os schemas Plan 2
- Export via barrel em `domains/index.ts`

**Engine:**
- `services/quant-engine/src/q3_quant_engine/thesis/` — novo modulo
  - `scoring.py` — pure functions (opportunity, fragility, bucketing, ranking, explanation)
  - `eligibility.py` — base eligibility check (computed_metrics based)
  - `types.py` — Python dataclasses espelhando os Zod schemas
  - `config.py` — constantes: pesos, thresholds, version strings

**Fit check:**
- Segue padrao existente (refiner tem seu proprio submodulo)
- Nao toca codigo existente
- Pure functions = facilmente testavel
- Nenhuma dependencia de DB ou infra
- Elegibilidade NAO depende do refiner (usa computed_metrics)
- normalization.py REMOVIDO (normalizacao pertence a Feature Engineering, MF-F1)

#### Shape 2: Estender refiner existente com thesis overlay

**Rejeitado.** O refiner tem responsabilidade clara (quality scoring). Misturar thesis scoring viola SRP.

### 7. Selected Shape

**Shape 1** — novo dominio `thesis.ts` + novo modulo `thesis/` em quant-engine.

### 8. Appetite

- **Level:** Small batch — 1 sessao de build
- **Why this appetite is enough:** ~6 pure functions + config + types + 1 arquivo Zod + testes. Zero infra.
- **Must-fit items:**
  - Zod schemas completos com ScoreProvenance
  - Pure functions de scoring em Python
  - Elegibilidade baseada em computed_metrics
  - Testes unitarios
  - Explanation generation basica (template)
- **First cuts if exceeded:**
  - Simplificar ScoreProvenance (so sourceType, sem evidenceRef)
  - Simplificar explanation templates (menos variantes de texto)

### 9. Boundaries / No-Gos / Out of Scope

**Boundaries:**
- Tocar apenas: `packages/shared-contracts/src/domains/`, `services/quant-engine/src/q3_quant_engine/thesis/`
- Build de shared-contracts deve continuar passando
- Testes do quant-engine devem continuar passando

**No-gos:**
- NAO alterar ranking.py, refiner, strategy task
- NAO criar tabelas / migrations
- NAO criar endpoints de API
- NAO alterar UI
- NAO acessar DB nas pure functions
- NAO fazer normalizacao de dados brutos (pertence a F1)
- NAO hardcodar sector proxy maps (pertence a F1)

**Out of scope:**
- Feature ingestion (MF-F1/F2)
- Persistencia (MF-B1)
- Pipeline execution (MF-B2)
- API / UI (MF-C/D/E)
- Validacao end-to-end (MF-G)
- Subteses por commodity (v2)
- AI-assisted scoring (v2)

### 10. Rabbit Holes / Hidden Risks (corrigidos)

| Risk | Impact | Mitigation |
|------|--------|------------|
| Zod 4 API | Build quebra | Seguir padrao dos domains existentes |
| MVP tem 3 dimensoes opportunity, formula original tem 4 pesos | Pesos nao somam 1.0 com 4 pesos | MVP redistribui: 0.50*direct + 0.30*indirect + 0.20*exportFx |
| Dual-schema drift (Zod vs Python) | Inconsistencia | Nomes identicos, comment linking |
| Thresholds de bucketing arbitrarios | Distribuicao ruim | Constantes nomeadas em config.py. Alert se >40% em D_FRAGILE ou 0 em A_DIRECT. Validacao em MF-G |
| Elegibilidade muito permissiva (sem refiner) | Empresa de baixa qualidade entra | interest_coverage >= 1.5 + debt_to_ebitda <= 6.0 ja filtram empresas frageis. Core screening filtra micro caps e EBIT negativo |
| ScoreProvenance aumenta complexidade do contrato | Over-engineering | Provenance e NECESSARIO (exigencia do Tech Lead review). Mas MVP usa subset: so sourceType + sourceVersion + confidence |

**Decisao sobre pesos MVP (3 dimensoes opportunity):**
```
MVP: finalCommodityAffinity = 0.50*direct + 0.30*indirect + 0.20*exportFx
V2:  finalCommodityAffinity = 0.45*direct + 0.25*indirect + 0.15*exportFx + 0.15*realAsset
```
A formula e uma constante em `config.py`. Mudar pesos = bump thesis_config_version.

### 11. Breadboard Summary (corrigido)

```
CURRENT (nao muda):
  [Strategy Run] -> [Ranking Engine] -> [Refiner Engine] -> [result_json + refinement_results]

NEW (Micro Feature A — scoring puro, sem DB):
  Input: Plan2FeatureInput (completo — montado por B2 a partir de F1 draft + defaults)
    - 7 scores 0-100 (ja normalizados)
    - ScoreProvenance por dimensao
    - coreRankPercentile (posicao no ranking core)
    - passed_core_screening, has_valid_financials, interest_coverage, debt_to_ebitda
    |
    v
  [check_base_eligibility] -> BaseEligibility (eligible_for_plan2 + failed_reasons[])
    - Assinatura canonica: 4 params (passed_core_screening, has_valid_financials, interest_coverage, debt_to_ebitda)
    - NAO usa refiner scores
    |
    v (se eligible)
  [compute_final_commodity_affinity_score] -> 0-100
  [compute_final_dollar_fragility_score] -> 0-100
    |
    v
  [assign_thesis_bucket] -> A_DIRECT | B_INDIRECT | C_NEUTRAL | D_FRAGILE
    |
    v
  [compute_thesis_rank_score] -> 0-100
    |
    v
  [generate_explanation] -> Plan2Explanation (template-based)
    |
    v
  [sort_plan2_rank] -> lista ordenada por bucket + score
    |
    v
  Output: list[Plan2RankingSnapshot]
```

### 12. Build Scopes (corrigidos)

#### Scope 1: Zod Schemas em shared-contracts (V1 required)

**Objective:** Definir todos os tipos Plan 2 como SSOT em Zod 4, incluindo ScoreProvenance.

**Files touched:**
- `packages/shared-contracts/src/domains/thesis.ts` (novo)
- `packages/shared-contracts/src/domains/index.ts` (export)

**Dependencies:** Nenhuma
**Risk focus:** Zod 4 API
**Review focus:** Nomes dos campos, ScoreProvenance structure, ranges documentados

**Done criteria:**
- thesis.ts com: thesisBucketSchema, scoreProvenanceSchema, baseEligibilitySchema (com failedReasons array), opportunityVectorSchema, fragilityVectorSchema, plan2FeatureDraftSchema, plan2FeatureInputSchema, plan2RankingSnapshotSchema, plan2ExplanationSchema, plan2RankResponseItemSchema
- Exportado via barrel
- `pnpm --filter @q3/shared-contracts build` passa

**Validation hook:** `pnpm --filter @q3/shared-contracts build`

---

#### Scope 2: Python types + config + eligibility (V1 required)

**Objective:** Dataclasses Python espelhando Zod + constantes + funcao de elegibilidade baseada em computed_metrics.

**Files touched:**
- `services/quant-engine/src/q3_quant_engine/thesis/__init__.py` (novo)
- `services/quant-engine/src/q3_quant_engine/thesis/types.py` (novo)
- `services/quant-engine/src/q3_quant_engine/thesis/config.py` (novo)
- `services/quant-engine/src/q3_quant_engine/thesis/eligibility.py` (novo)

**Dependencies:** Scope 1 (nomes dos campos)
**Risk focus:** Alinhamento com Zod, thresholds corretos
**Review focus:** Dataclass fields = Zod fields, config constantes nomeadas

**Done criteria:**
- Dataclasses para todos os tipos incluindo ScoreProvenance, Plan2FeatureDraft, BaseEligibility (com failed_reasons)
- config.py com: OPPORTUNITY_WEIGHTS, FRAGILITY_WEIGHTS, THESIS_RANK_WEIGHTS, BUCKET_THRESHOLDS, ELIGIBILITY_MIN_INTEREST_COVERAGE, ELIGIBILITY_MAX_DEBT_TO_EBITDA, THESIS_CONFIG_VERSION
- `check_base_eligibility(passed_core_screening: bool, has_valid_financials: bool, interest_coverage: float | None, debt_to_ebitda: float | None) -> BaseEligibility` — assinatura canonica com 4 params
- BaseEligibility retorna `eligible_for_plan2: bool` + `failed_reasons: list[str]`
- NAO depende de refiner scores

**Validation hook:** `python -m mypy src` no quant-engine

---

#### Scope 3: Scoring + explanation functions (V1 required)

**Objective:** Pure functions para opportunity, fragility, bucketing, ranking, sorting, explanation.

**Files touched:**
- `services/quant-engine/src/q3_quant_engine/thesis/scoring.py` (novo)

**Dependencies:** Scope 2 (types, config)
**Risk focus:** Formulas corretas, edge cases, clamp 0-100
**Review focus:** Pesos usam config (nao hardcoded), bucket precedence absoluta, explanation templates

**Done criteria:**
- `compute_final_commodity_affinity_score(opp_vector) -> float` — usa OPPORTUNITY_WEIGHTS
- `compute_final_dollar_fragility_score(frag_vector) -> float` — usa FRAGILITY_WEIGHTS
- `assign_thesis_bucket(scores) -> ThesisBucket` — usa BUCKET_THRESHOLDS
- `compute_thesis_rank_score(affinity, fragility, base_core) -> float` — usa THESIS_RANK_WEIGHTS
- `sort_plan2_rank(list[Plan2RankingSnapshot]) -> list[Plan2RankingSnapshot]`
- `generate_explanation(snapshot) -> Plan2Explanation` — template-based, deterministica
- Todos os scores clampados [0, 100]

**Validation hook:** `python -m mypy src` no quant-engine

---

#### Scope 4: Testes unitarios (V1 required)

**Objective:** Cobertura completa para todas as pure functions.

**Files touched:**
- `services/quant-engine/tests/thesis/__init__.py` (novo)
- `services/quant-engine/tests/thesis/test_eligibility.py` (novo)
- `services/quant-engine/tests/thesis/test_scoring.py` (novo)

**Dependencies:** Scopes 2, 3
**Risk focus:** Edge cases, boundary values
**Review focus:** Todos os buckets testados, boundary values exatos, sorting estavel

**Done criteria:**
- test_eligibility: eligible com passed_core_screening=True, has_valid_financials=True, interest_coverage=5.0, debt_to_ebitda=2.0
- test_eligibility: ineligible com passed_core_screening=False → failed_reasons contem "failed_core_screening"
- test_eligibility: ineligible com has_valid_financials=False → failed_reasons contem "missing_valid_financials"
- test_eligibility: ineligible com interest_coverage=1.0 → failed_reasons contem "interest_coverage_below_1.5"
- test_eligibility: ineligible com debt_to_ebitda=7.0 → failed_reasons contem "debt_to_ebitda_above_6.0"
- test_eligibility: ineligible com interest_coverage=None → failed_reasons contem "interest_coverage_below_1.5"
- test_eligibility: boundary values exatos (1.5 eligible, 1.49 ineligible, 6.0 eligible, 6.01 ineligible)
- test_eligibility: multiplas falhas acumulam em failed_reasons
- test_scoring: opportunity formula com valores conhecidos (3 dimensoes MVP)
- test_scoring: fragility formula com valores conhecidos (4 dimensoes MVP)
- test_scoring: bucketing para cada bucket (A, B, C, D)
- test_scoring: bucketing boundary (directCommodity=70, fragility=60 → A_DIRECT)
- test_scoring: bucketing boundary (directCommodity=69 → NAO A_DIRECT)
- test_scoring: thesis rank score formula
- test_scoring: sorting por bucket primeiro, score depois
- test_scoring: sorting estavel para scores iguais
- test_scoring: explanation gera positives/negatives coerentes
- test_scoring: scores all-zero, all-100
- `python -m pytest tests/thesis/ -v` passa

**Validation hook:** `python -m pytest tests/thesis/ -v`

---

### 13. Validation Plan

**Per-scope:**
- Scope 1: `pnpm --filter @q3/shared-contracts build` passa
- Scope 2: `python -m mypy src` passa
- Scope 3: `python -m mypy src` passa
- Scope 4: `python -m pytest tests/thesis/ -v` — todos os testes passam

**Final feature validation:**
- Cenario com 6 empresas ficticias cobrindo: elegivel em cada bucket + inelegivel
- Verificar ordenacao: A_DIRECT > B_INDIRECT > C_NEUTRAL > D_FRAGILE
- Verificar: dentro do mesmo bucket, maior thesisRankScore vem primeiro
- Verificar: empresa com interest_coverage < 1.5 NAO e elegivel (independente dos scores)
- Verificar: explanation positives/negatives coerentes com bucket e scores
- `pnpm build` completo passa
- `python -m ruff check src` + `python -m mypy src` no quant-engine

### 14. Current Status

**Phase:** Wave 1 BUILD COMPLETE — MF-A + MF-B1 concluidos. MF-F1 pendente.
**Tech Lead approval:** 2026-03-15. SSOT definitivo: este shaping.md + spec-01 a spec-04 neste diretorio.

**Artefatos entregues:**
- `spec-01-universe-eligibility.md` — responde Q1-4, 15-19 + assinatura canonica de eligibility (Redline 1)
- `spec-02-feature-semantics.md` — responde Q5-7, 25-28, 34-37
- `spec-03-dependency-graph.md` — responde Q8-14, 29-30 + ownership table (Redlines 2, 3)
- `spec-04-versioning-provenance.md` — responde Q20-24, 31-33 + plan2_runs (Redline 4)
- `shaping.md` (este arquivo) — v3 com todos os redlines aplicados

**Decisoes-mae resolvidas:**
1. Universo = todos os ativos que passam no core screening (NAO top 30)
2. "Aprovada no core" = passou core filters + interest_coverage >= 1.5 + debt_to_ebitda <= 6.0
3. Cada feature tem definicao, fonte, formula, fallback e provenance documentados
4. Feature Engineering (0-100 com provenance) → Scoring Engine (matematica pura) → Output

**Redlines corrigidos (v3):**
1. Assinatura canonica de eligibility: `check_base_eligibility(passed_core_screening, has_valid_financials, interest_coverage, debt_to_ebitda) -> BaseEligibility` com `failed_reasons[]`. Replicada em spec-01 + shaping scopes.
2. Dono da completude do input: **Opcao B aceita.** F1 entrega `Plan2FeatureDraft` (parcial). B2 completa defaults/derivados e monta `Plan2FeatureInput` final. A recebe input completo.
3. Dono unico da explanation: **MF-A** (pure function `generate_explanation()`). B2 persiste. D/E exibem. "geracao em B2" removido de todos os docs.
4. Identidade de persistencia: **`plan2_runs`** criada como entidade de execucao separada. `plan2_thesis_scores` referencia `plan2_run_id` (nao strategy_run_id direto). UNIQUE(plan2_run_id, issuer_id). Recalcular = nova run, historico preservado.

**Completed:**
- MF-A Scope 1: thesis.ts — 13 Zod schemas, build passa ✓
- MF-A Scope 2: types.py + config.py + eligibility.py — mypy clean ✓
- MF-A Scope 3: scoring.py — 6 pure functions, mypy clean, ruff clean ✓
- MF-A Scope 4: 43 testes passando (13 eligibility + 30 scoring) ✓
- MF-B1: SQLAlchemy models (Plan2Run, Plan2ThesisScore, ThesisBucket enum), Drizzle schema, Alembic migration ✓
- Regressao: 217 testes existentes do quant-engine continuam passando ✓

**Pending:**
- MF-F1: Feature Engineering automatico (sector proxy maps + refinancingStress quantitativo)

**Next action:** Build MF-F1, depois MF-B2 (pipeline execution).

### 15. Close Summary

_Pendente — sera preenchido apos build._

### 16. Tech Lead Handoff

_Pendente — sera preenchido apos close._
