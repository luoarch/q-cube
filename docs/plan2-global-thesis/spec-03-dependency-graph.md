# Spec 03 — Dependency Graph Corrigido

Responde perguntas: 8, 9, 10, 11, 12, 13, 14, 29, 30

---

## Problemas no grafo original

| Problema | Correcao |
|----------|----------|
| B dependia so de A, mas precisa de F para ter dados | B partido em B1 (schema) e B2 (pipeline). B2 depende de A + F1 |
| F dependia de A, mas e independente | F1 (automatico) e paralelo a A |
| F era monolitico | F partido em F1 (automatico) e F2 (rubricas manuais) |
| Primeiro bet era A sem specs fechados | MF-0 (specs) adicionado antes de A |
| Explanation ownership ambiguo | MF-A e dono unico da geracao (pure function). B2 persiste. D/E exibem. |
| Plan2FeatureInput parcial vs completo | F1 entrega Plan2FeatureDraft (parcial). B2 completa defaults/derivados e monta Plan2FeatureInput final. A recebe input completo. |

---

## Grafo corrigido

```
MF-0: Specs (ESTE DOCUMENTO)
  |
  +---> MF-A: Contracts + Scoring Engine
  |       (Zod schemas + pure functions Python + testes)
  |       Input: Plan2FeatureInput (completo, 7 scores 0-100 + provenance)
  |       Output: buckets, thesis rank, snapshots, explanation
  |       Dono de: schema + scoring + explanation generation
  |
  +---> MF-F1: Feature Engineering — Automatico
  |       (sector proxy maps + refinancingStress quantitativo)
  |       Input: computed_metrics, issuer.sector/subsector
  |       Output: Plan2FeatureDraft (scores automaticos, SEM defaults/derivados)
  |
  +---> MF-B1: Persistence Schema
          (tabelas plan2_runs + plan2_thesis_scores, Alembic + SQLAlchemy + Drizzle)
          |
          +---> (A, F1 e B1 precisam estar prontos)
          |
          v
        MF-B2: Pipeline Execution
          (Celery task que orquestra: F1 draft -> completa defaults/derivados
           -> monta Plan2FeatureInput final -> chama A -> persiste em B1)
          Dono de: completude do input (defaults, derivados, fallbacks)
          |
          v
        MF-C: API Endpoints
          (GET /thesis-rank, GET /thesis-rank/:ticker)
          |
          +---> MF-D: Web UI — Toggle + Ranking
          |       (toggle Core/Thesis, bucket badges, score column)
          |
          +---> MF-E: Web UI — Breakdown
                  (detalhe por ticker, vectors, positives/negatives)

        MF-F2: Feature Engineering — Rubric System (paralelo a C/D/E)
          (UI para input manual de rubricas com evidencia)
          (pode ser feito a qualquer momento apos B1)

        MF-G: Validation Framework (apos B2 ter dados reais)
          (sanity checks, sensitivity, stability, face validity)
```

### Ownership de responsabilidades (sem ambiguidade)

| Responsabilidade | Dono unico | Justificativa |
|------------------|-----------|---------------|
| Plan2FeatureDraft (scores automaticos parciais) | **MF-F1** | Feature engineering puro |
| Plan2FeatureInput (input completo com defaults/derivados) | **MF-B2** | B2 e o orchestrator — recebe draft de F1, aplica defaults, monta payload final |
| Scoring (composites, buckets, ranking) | **MF-A** | Pure functions, sem DB |
| Explanation generation | **MF-A** | Pure function, depende so de scores/bucket |
| Persistencia | **MF-B2** | Persiste output de A em tabelas de B1 |
| Exibicao | **MF-D/E** | Consume API de C |

---

## Dependencias explicitas

| Micro Feature | Depende de | Entrega |
|---------------|------------|---------|
| MF-0 | — | 4 specs (este documento) |
| MF-A | MF-0 | Zod schemas (incl. Plan2FeatureDraft + Plan2FeatureInput) + Python pure functions + testes |
| MF-F1 | MF-0 | Sector proxy maps + refinancingStress calculator → produz Plan2FeatureDraft |
| MF-B1 | MF-0 | Tabelas plan2_runs + plan2_thesis_scores + migration + models |
| MF-B2 | MF-A + MF-F1 + MF-B1 | Celery task: F1 draft → completa input → chama A → persiste |
| MF-C | MF-B2 | API endpoints |
| MF-D | MF-C | UI ranking + toggle |
| MF-E | MF-C | UI breakdown |
| MF-F2 | MF-B1 | UI de rubrica manual |
| MF-G | MF-B2 | Validacao com dados reais |

---

## Ordem de execucao recomendada

### Wave 1 (paralelo)
- **MF-A**: Contracts + Scoring Engine
- **MF-F1**: Feature Engineering automatico
- **MF-B1**: Persistence schema

Podem ser construidos simultaneamente porque:
- A so precisa dos specs (MF-0)
- F1 so precisa dos specs + computed_metrics existentes
- B1 so precisa dos specs

### Wave 2
- **MF-B2**: Pipeline Execution (wira F1 → A → B1)

### Wave 3 (paralelo)
- **MF-C**: API
- **MF-F2**: Rubric system (pode comecar em paralelo com C)

### Wave 4 (paralelo)
- **MF-D**: UI toggle + ranking
- **MF-E**: UI breakdown
- **MF-G**: Validation

---

## Respostas diretas

**Q8: As tabelas do Plan 2 vao persistir scores finais, features brutas, evidencias, versao da rubrica, versao da tese, fonte por campo?**
R: Sim, tudo. Distribuido em duas tabelas (schema SSOT em `spec-04`):
- **`plan2_runs`**: `thesis_config_version`, `pipeline_version`, `as_of_date`, `status`, `bucket_distribution_json`
- **`plan2_thesis_scores`**: `feature_input_json` (Plan2FeatureInput completo com provenance por dimensao), `eligibility_json` (com failed_reasons), scores individuais como colunas (direct_commodity_exposure_score, etc.), composites (final_commodity_affinity_score, final_dollar_fragility_score), `bucket`, `thesis_rank_score`, `thesis_rank`, `explanation_json`
A evidencia por score vive dentro da provenance no `feature_input_json`. Versioning vive em `plan2_runs`.

**Q9: O pipeline de B calcula score de que, se F ainda nao existe?**
R: Corrigido. B foi partido em B1 (schema) e B2 (pipeline). B2 depende de F1. B2 so roda quando F1 produz `Plan2FeatureInput`.

**Q10: B deveria ser quebrado em B1 persistence schema e B2 pipeline execution?**
R: Sim, exatamente. B1 cria tabela/models. B2 cria Celery task que orquestra F1→A→persist.

**Q11: A dependencia correta nao e B depende de F?**
R: Sim. B2 depende de A + F1 + B1. Corrigido no grafo.

**Q12: Por que o primeiro bet nao e um MF anterior de Feature Definition Spec?**
R: Correto. MF-0 (este documento) e agora o primeiro bet. MF-A so comeca apos specs aprovados.

**Q13: Qual evidencia de que os campos do thesis.ts estao estaveis?**
R: As dimensoes sao conceitualmente estaveis (commodity exposure, dollar fragility sao conceitos de macro/finance bem definidos). O que muda e COMO sao populadas (proxy vs rubrica vs quantitativo), nao O QUE sao. O contrato do Scoring Engine (0-100 input → ranking output) e estavel independente da fonte.

**Q14: Quais campos espera que mudem quando F for detalhado?**
R: Nenhum campo do Scoring Engine muda. O que muda:
- Sector proxy maps podem ganhar granularidade (F1)
- Novas source types podem aparecer (F2: RUBRIC_MANUAL)
- Fallback defaults podem ser ajustados
Mas o contrato `Plan2FeatureInput` (7 scores 0-100 + provenance) e estavel.

**Q29: O MF A vai so definir o schema de explanation ou tambem gerar?**
R: MF-A define o schema E implementa geracao. `generate_explanation()` e pure function em A (recebe scores/bucket, produz positives/negatives/summary). Deterministica, template-based, sem AI. B2 apenas persiste o output. D/E exibem.

**Q30: Se nao gera, quem e dono da geracao?**
R: MF-A e o dono unico. Nenhum outro MF gera explanation. Ownership table acima e definitiva.

**Q9 (atualizado): O pipeline de B2 faz o que exatamente?**
R: B2 orquestra o fluxo completo:
1. Chama F1 para cada issuer elegivel → recebe Plan2FeatureDraft (scores parciais, sem defaults)
2. Completa o draft: aplica defaults, derivados e fallbacks → monta Plan2FeatureInput final
3. Chama A (scoring engine) com o input completo → recebe Plan2RankingSnapshot + Plan2Explanation
4. Persiste tudo em plan2_thesis_scores (tabela de B1)

F1 entrega Plan2FeatureDraft. B2 monta Plan2FeatureInput. A consome Plan2FeatureInput.
