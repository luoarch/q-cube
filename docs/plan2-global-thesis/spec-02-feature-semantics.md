# Spec 02 — Feature Semantics

Responde perguntas: 5, 6, 7, 25, 26, 27, 28, 34, 35, 36, 37

---

## Decisao-mae: Como cada feature e definida e produzida?

### Fronteira clara entre Feature Engineering e Scoring

| Camada | Responsabilidade | Input | Output | Dono |
|--------|-----------------|-------|--------|------|
| **Feature Engineering (F1)** | Transforma dados brutos em scores parciais com provenance | computed_metrics, sector, rubrics | `Plan2FeatureDraft` (scores automaticos, SEM defaults/derivados) | MF-F1 |
| **Input Assembly (B2)** | Completa draft com defaults, derivados e fallbacks | `Plan2FeatureDraft` + regras de fallback | `Plan2FeatureInput` (completo, 7 scores 0-100 + provenance) | MF-B2 |
| **Scoring Engine (A)** | Computa composites, buckets, ranking, explanation | `Plan2FeatureInput` (scores 0-100) | `Plan2RankingSnapshot` + `Plan2Explanation` | MF-A |

**Regra:** O Scoring Engine NUNCA acessa DB, NUNCA transforma dados brutos, NUNCA decide como um score foi produzido. Ele recebe 0-100 e faz matematica.

**Regra:** Feature Engineering NUNCA faz bucketing, NUNCA computa thesis rank, NUNCA ordena. Ele produz dimensoes individuais.

**Regra:** B2 e o unico dono da completude do `Plan2FeatureInput`. F1 entrega draft parcial. B2 aplica defaults/derivados/fallbacks e garante que todos os 7 scores + provenance estao presentes antes de chamar A.

### Respostas diretas

**Q25: No MF A, os inputs ja chegam em 0-100 ou o modulo vai transformar valores brutos?**
R: Ja chegam em 0-100. O MF A (Scoring Engine) so faz matematica sobre scores pre-normalizados.

**Q26: Se os inputs ja chegam em 0-100, por que normalization.py existe no MF A?**
R: NAO existe mais. normalization.py foi removido do MF A. A normalizacao pertence ao Feature Engineering (MF-F).

**Q27: Se nao chegam em 0-100, qual e o raw schema oficial?**
R: N/A — os inputs DO chegam em 0-100 para o Scoring Engine.

**Q28: Onde termina feature engineering e comeca scoring?**
R: Feature Engineering (F1) termina quando produz `Plan2FeatureDraft` (scores parciais). B2 completa o draft em `Plan2FeatureInput` (7 scores + provenance). Scoring (A) comeca ao receber `Plan2FeatureInput` completo.

---

## Feature Semantics — Opportunity Vector (MVP: 3 dimensoes)

### 1. directCommodityExposureScore (0-100)

| Campo | Valor |
|-------|-------|
| **Definicao** | Grau em que o negocio principal da empresa envolve extracao, producao ou processamento direto de commodities |
| **Unidade** | Score 0-100 (0 = nenhuma exposicao, 100 = negocio 100% commodity) |
| **Tipo de score** | Score final derivado (composite de proxy + override) |
| **Fonte primaria MVP** | SECTOR_PROXY — mapeamento CVM sector/subsector |
| **Override** | RUBRIC_MANUAL — humano pode sobrescrever com evidencia |
| **Formula MVP** | `sectorProxyMap[issuer.sector + "/" + issuer.subsector]` com override manual |
| **Janela temporal** | Estatico ate proximo update de rubrica ou recadastro CVM |
| **Fallback** | Sempre disponivel (CVM cadastro tem sector para todos os issuers) |
| **Responsavel** | Feature Engineering automatico (proxy) + analista (override) |

**Mapeamento setorial MVP:**

| Setor CVM | Subsector CVM | Score proxy |
|-----------|---------------|-------------|
| Materiais Basicos | Mineracao | 90 |
| Petroleo, Gas e Biocombustiveis | Exploracao, Refino e Distribuicao | 85 |
| Materiais Basicos | Siderurgia e Metalurgia | 80 |
| Materiais Basicos | Papel e Celulose | 75 |
| Consumo nao Ciclico | Agropecuaria | 70 |
| Materiais Basicos | Quimicos | 65 |
| Consumo nao Ciclico | Acucar e Alcool | 65 |
| Materiais Basicos | Madeira | 60 |
| (outros) | (qualquer) | 10 |

**Nota:** O score proxy e grosseiro por design. Empresa de mineracao diversificada pode ter score diferente de mineradora pura. O override manual existe para corrigir isso.

---

### 2. indirectCommodityExposureScore (0-100)

| Campo | Valor |
|-------|-------|
| **Definicao** | Grau em que a empresa captura valor do ciclo de commodities sem producao direta (logistica, infra, servicos, equipamentos) |
| **Unidade** | Score 0-100 |
| **Tipo de score** | Score final derivado |
| **Fonte primaria MVP** | SECTOR_PROXY + RUBRIC_MANUAL |
| **Formula MVP** | `sectorProxyMap[sector/subsector]` com override manual |
| **Janela temporal** | Estatico ate proximo update |
| **Fallback** | Sector proxy |
| **Responsavel** | Feature Engineering automatico (proxy) + analista (override) |

**Mapeamento setorial MVP:**

| Setor CVM | Subsector CVM | Score proxy |
|-----------|---------------|-------------|
| Bens Industriais | Transporte | 55 |
| Bens Industriais | Maquinas e Equipamentos | 50 |
| Bens Industriais | Material de Transporte | 45 |
| Construcao e Engenharia | Construcao Pesada | 40 |
| Bens Industriais | Comercio (maq/equip) | 35 |
| (outros) | (qualquer) | 10 |

---

### 3. exportFxLeverageScore (0-100)

| Campo | Valor |
|-------|-------|
| **Definicao** | Grau em que a empresa se beneficia de exportacoes e/ou receita em moeda forte |
| **Unidade** | Score 0-100 |
| **Tipo de score** | Score final derivado |
| **Fonte primaria MVP** | RUBRIC_MANUAL (CVM nao fornece revenue por geografia) |
| **Fonte secundaria** | SECTOR_PROXY como fallback grosseiro |
| **Formula MVP** | Se rubrica existe: valor da rubrica. Se nao: `directCommodityExposureScore * 0.6` (proxy: exportadores de commodities tendem a ter receita FX) |
| **Janela temporal** | Estatico ate proximo update |
| **Fallback** | Derivado de directCommodityExposureScore (correlacao grosseira) |
| **Responsavel** | Analista (rubrica) ou derivacao automatica |

**Nota:** Esse e o score com maior incerteza no MVP. O fallback (derivar de commodity exposure) e explicitamente uma aproximacao. Empresas como Embraer (exportadora, nao-commodity) precisam de rubrica manual para ter score correto.

---

## Feature Semantics — Fragility Vector (MVP: 4 dimensoes)

### 4. refinancingStressScore (0-100)

| Campo | Valor |
|-------|-------|
| **Definicao** | Vulnerabilidade a pressao de refinanciamento de divida |
| **Unidade** | Score 0-100 (0 = sem estresse, 100 = estresse extremo) |
| **Tipo de score** | Score final derivado (quantitativo puro) |
| **Fonte primaria MVP** | QUANTITATIVE — computed_metrics + statement_lines |
| **Responsavel** | Feature Engineering automatico |

**Formula MVP:**

```
shortTermDebtRatio = short_term_debt / (short_term_debt + long_term_debt)
  // 0-1, higher = worse (mais divida de curto prazo)
  // Normalizado: clamp(shortTermDebtRatio * 100, 0, 100)

leverageComponent = clamp(debt_to_ebitda / 6.0 * 100, 0, 100)
  // 0-100, 6x = 100 (teto), 0x = 0

coverageComponent = clamp((1 - (interest_coverage / 10.0)) * 100, 0, 100)
  // 0-100, 10x+ = 0 (excelente), 0x = 100 (critico)
  // Invertido: menor cobertura = maior estresse

refinancingStressScore =
  0.35 * shortTermDebtRatioNorm +
  0.35 * leverageComponent +
  0.30 * coverageComponent
```

**Inputs e disponibilidade:**

| Input | Fonte | Disponivel? |
|-------|-------|-------------|
| short_term_debt | statement_lines (canonical_key) | Sim, todos os issuers com filing |
| long_term_debt | statement_lines (canonical_key) | Sim |
| debt_to_ebitda | computed_metrics (metric_code) | Sim, todos os issuers |
| interest_coverage | computed_metrics (metric_code) | Sim, todos os issuers |

**Janela temporal:** Ultimo reference_date anual disponivel.

**Fallback:** Se algum input faltando, score = 50 (neutro). Provenance marcada como INCOMPLETE.

---

### 5. usdDebtExposureScore (0-100)

| Campo | Valor |
|-------|-------|
| **Definicao** | Exposicao da divida a USD/moeda forte como proporcao da divida total |
| **Unidade** | Score 0-100 (0 = nenhuma divida em USD, 100 = toda divida em USD) |
| **Tipo de score** | Input bruto rubricado |
| **Fonte primaria MVP** | RUBRIC_MANUAL |
| **Formula MVP** | Valor atribuido pela rubrica |
| **Janela temporal** | Estatico ate proximo update |
| **Fallback** | SECTOR_PROXY grosseiro (exportadores de commodities frequentemente tem divida em USD). Se nenhum: 30 (moderado-default) |
| **Responsavel** | Analista |

**Rubrica ordinal MVP:**

| Nivel | Score | Criterio |
|-------|-------|----------|
| 0 - Nenhum | 0 | Sem divida em moeda forte conhecida |
| 1 - Minimo | 20 | < 10% da divida em USD |
| 2 - Moderado | 40 | 10-30% da divida em USD |
| 3 - Relevante | 60 | 30-50% da divida em USD |
| 4 - Alto | 80 | 50-80% da divida em USD |
| 5 - Dominante | 100 | > 80% da divida em USD |

**Evidencia requerida:** Notas explicativas do ultimo DFP, secao de endividamento.

---

### 6. usdImportDependenceScore (0-100)

| Campo | Valor |
|-------|-------|
| **Definicao** | Dependencia de importacoes dolarizadas como proporcao do custo operacional |
| **Unidade** | Score 0-100 (0 = sem dependencia, 100 = totalmente dependente) |
| **Tipo de score** | Input bruto rubricado |
| **Fonte primaria MVP** | RUBRIC_MANUAL |
| **Fallback** | 20 (default conservador — maioria das empresas brasileiras tem alguma dependencia) |
| **Responsavel** | Analista |

**Rubrica ordinal MVP:**

| Nivel | Score | Criterio |
|-------|-------|----------|
| 0 - Nenhum | 0 | Operacao 100% domestica, sem insumos importados |
| 1 - Minimo | 20 | < 10% dos custos em insumos importados |
| 2 - Moderado | 40 | 10-30% dos custos importados |
| 3 - Relevante | 60 | 30-50% dos custos importados |
| 4 - Alto | 80 | 50-80% dos custos importados |
| 5 - Dominante | 100 | > 80% dos custos importados |

**Evidencia requerida:** Release de resultados ou formulario de referencia, secao de custos.

---

### 7. usdRevenueOffsetScore (0-100)

| Campo | Valor |
|-------|-------|
| **Definicao** | Protecao natural via receita em USD (hedge natural — quanto maior, menos fragil) |
| **Unidade** | Score 0-100 (0 = sem receita em USD, 100 = receita toda em USD) |
| **Tipo de score** | Input bruto rubricado |
| **Fonte primaria MVP** | RUBRIC_MANUAL |
| **Fallback** | Se directCommodityExposureScore >= 70: derivar como `directCommodityExposureScore * 0.7` (proxy: exportadores de commodities tem receita em USD). Se nao: 10 (default baixo) |
| **Responsavel** | Analista |

**Nota:** Este score e INVERTIDO na formula de fragility (100 - usdRevenueOffsetScore). Maior score = mais protecao = menos fragilidade.

**Rubrica ordinal MVP:**

| Nivel | Score | Criterio |
|-------|-------|----------|
| 0 - Nenhum | 0 | Receita 100% em BRL, sem exportacao |
| 1 - Minimo | 20 | < 10% da receita em USD/exportacao |
| 2 - Moderado | 40 | 10-30% |
| 3 - Relevante | 60 | 30-50% |
| 4 - Alto | 80 | 50-80% |
| 5 - Dominante | 100 | > 80% |

---

## Dimensoes NAO incluidas no MVP

| Dimensao | Razao da exclusao |
|----------|-------------------|
| realAssetCharacterScore | Fortemente correlacionado com directCommodityExposure. Incluir geraria redundancia sem dado novo. V2. |
| hedgingProtectionScore | Requer dados de notas explicativas que nao temos automatizados. V2. |
| usDemandConcentrationScore | Requer breakdown de receita por pais. V2. |

---

## Resumo de source types no MVP

| Dimensao | Source type | Automatizado? |
|----------|------------|---------------|
| directCommodityExposureScore | SECTOR_PROXY + RUBRIC_MANUAL | Sim (proxy), manual (override) |
| indirectCommodityExposureScore | SECTOR_PROXY + RUBRIC_MANUAL | Sim (proxy), manual (override) |
| exportFxLeverageScore | RUBRIC_MANUAL (fallback: derivado) | Nao |
| refinancingStressScore | QUANTITATIVE | Sim, 100% automatizado |
| usdDebtExposureScore | RUBRIC_MANUAL (fallback: proxy) | Nao |
| usdImportDependenceScore | RUBRIC_MANUAL (fallback: default) | Nao |
| usdRevenueOffsetScore | RUBRIC_MANUAL (fallback: derivado) | Nao |

**Implicacao:** No MVP, apenas refinancingStressScore sera calculado automaticamente para todos. Os demais terao sector proxy ou defaults ate que rubricas sejam preenchidas.

---

## Provenance por score

Cada score individual carrega metadata:

```
type ScoreProvenance = {
  sourceType: 'QUANTITATIVE' | 'SECTOR_PROXY' | 'RUBRIC_MANUAL' | 'DERIVED' | 'DEFAULT'
  sourceVersion: string           // ex: "sector-map-v1", "rubric-v1", "quant-v1"
  assessedAt: string              // ISO date
  assessedBy: string | null       // null para automatico, user_id para manual
  confidence: 'high' | 'medium' | 'low'
  evidenceRef: string | null      // referencia a evidencia (filing_id, nota, release)
}
```

**Regra de confidence:**

| Source type | Confidence |
|-------------|------------|
| QUANTITATIVE | high (dado direto de filing) |
| RUBRIC_MANUAL | medium (julgamento humano com evidencia) |
| SECTOR_PROXY | low (aproximacao grosseira) |
| DERIVED | low (derivado de outro score) |
| DEFAULT | low (sem informacao) |

---

## Respostas diretas

**Q5: Para cada dimensao, definicao/fonte/formula/unidade/janela/fallback/responsavel?**
R: Detalhado acima para cada uma das 7 dimensoes MVP.

**Q6: Quais sao quantitativas, rubricadas, AI-assisted, proxies setoriais?**
R: 1 quantitativa (refinancingStress), 2 sector proxy + manual override (directCommodity, indirectCommodity), 4 rubrica manual com fallback (exportFx, usdDebt, usdImport, usdRevenue). Nenhuma AI-assisted no MVP.

**Q7: Qual e "score final derivado" e qual e "input bruto"?**
R: directCommodity, indirectCommodity, refinancingStress = scores finais derivados (composites). exportFx, usdDebt, usdImport, usdRevenue = inputs brutos rubricados (valor direto da rubrica ou proxy).

**Q34: Quais scores podem usar proxy setorial?**
R: directCommodityExposure, indirectCommodityExposure. Sao os unicos com mapeamento CVM sector/subsector significativo.

**Q35: Quais exigem evidencia especifica da empresa?**
R: usdDebtExposure, usdImportDependence, usdRevenueOffset (requerem dados de notas explicativas ou releases). exportFxLeverage tambem, mas tem derivacao como fallback.

**Q36: Como o sistema diferencia score inferido, observado, rubricado, assistido por IA?**
R: Via `ScoreProvenance.sourceType`: QUANTITATIVE (observado), SECTOR_PROXY (inferido), RUBRIC_MANUAL (rubricado), DERIVED (derivado). AI_ASSISTED reservado para v2.

**Q37: Isso entra no contrato ou so na persistencia?**
R: Entra no contrato. `Plan2FeatureInput` inclui provenance por dimensao. O Scoring Engine recebe e propaga. A persistencia armazena. A UI pode exibir confidence badges.
