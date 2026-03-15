# Spec 04 — Versioning & Provenance

Responde perguntas: 20, 21, 22, 23, 24, 31, 32, 33

---

## Versionamento — 3 eixos

| Eixo | O que versiona | Exemplo | Onde persiste |
|------|---------------|---------|---------------|
| **thesis_config_version** | Pesos dos composites, thresholds de bucketing, formula do thesis_rank_score | `"1.0.0"` | **`plan2_runs.thesis_config_version`** |
| **feature_source_version** | Versao do mapeamento setorial, formula quantitativa, rubrica | `"sector-map-v1"`, `"quant-v1"`, `"rubric-v1"` | Dentro de `ScoreProvenance.sourceVersion` no `plan2_thesis_scores.feature_input_json` |
| **pipeline_version** | Versao do pipeline end-to-end (como F1→A→persist sao orquestrados) | `"1.0.0"` | **`plan2_runs.pipeline_version`** |

### thesis_config_version (semver)

Cobre:
- Pesos do opportunity vector (0.45, 0.25, 0.15, 0.15)
- Pesos do fragility vector (0.25, 0.20, 0.20, 0.15, 0.10, 0.10)
- Pesos do thesis_rank_score (0.60, 0.25, 0.15)
- Thresholds de bucketing (70, 60, 75, 65)
- Thresholds de eligibility (interest_coverage >= 1.5, debt_to_ebitda <= 6.0)

**Regra:** Qualquer mudanca de peso ou threshold incrementa thesis_config_version.

**Bump rules:**
- Patch (1.0.x): ajuste fino de threshold (ex: 70→72)
- Minor (1.x.0): mudanca de peso ou adicao de dimensao
- Major (x.0.0): mudanca estrutural (nova formula, novo bucket)

### feature_source_version

Cada dimensao carrega sua propria versao:

```
Plan2FeatureInput.provenance = {
  directCommodityExposure: {
    sourceType: "SECTOR_PROXY",
    sourceVersion: "sector-map-v1",    // versao do mapeamento
    ...
  },
  refinancingStress: {
    sourceType: "QUANTITATIVE",
    sourceVersion: "quant-v1",         // versao da formula
    ...
  },
  usdDebtExposure: {
    sourceType: "RUBRIC_MANUAL",
    sourceVersion: "rubric-v1",        // versao da rubrica
    assessedBy: "user-uuid",
    ...
  }
}
```

### Comparabilidade historica

Para comparar rankings entre periodos:
1. Filtrar por `thesis_config_version` (mesma versao de pesos)
2. Verificar `feature_source_version` por dimensao (mesma metodologia)
3. Se versoes diferem, marcar comparacao como "cross-version" na UI

---

## Respostas sobre bucketing e distribuicao

**Q20: Qual a distribuicao esperada de buckets no universo brasileiro?**

Estimativa com sector proxy no universo B3 (~80-150 empresas apos core screening):

| Bucket | Estimativa | Empresas tipicas |
|--------|-----------|------------------|
| A_DIRECT | 8-15 | Vale, Petrobras, CSN, Suzano, Klabin, PRIO, 3R, SLC Agricola |
| B_INDIRECT | 5-10 | Rumo, Santos Brasil, WEG (parcial), Randon |
| C_NEUTRAL | 50-100 | Maioria do universo (varejo, tech, saude, educacao, etc.) |
| D_FRAGILE | 5-15 | Empresas com divida USD alta + import dependence + refinancing stress |

**Nota:** Com sector proxy apenas (sem rubricas manuais), a distribuicao vai ser concentrada em C_NEUTRAL porque os proxies sao conservadores (default = 10).

**Q21: Quantas empresas em A_DIRECT?**
R: Estimativa 8-15 no MVP com proxy setorial. Pode crescer com rubricas manuais refinando scores de empresas com exposure nao-obvio pelo setor CVM.

**Q22: Se 0 empresas em A_DIRECT, qual o comportamento correto?**
R: Comportamento normal. O bucket aparece vazio na UI. O ranking continua com B_INDIRECT como primeiro bucket. Isso e informacao ("nenhuma empresa atende criterio de exposicao direta forte com fragilidade controlada"), nao erro.

Log de alerta: `logger.warning("thesis_rank: bucket A_DIRECT is empty for run=%s", run_id)`.

**Q23: Se 60% em D_FRAGILE, aceitavel ou threshold errado?**
R: Sinal de threshold errado. Se mais de 40% do universo cair em D_FRAGILE, o sistema deve logar alerta:

```
logger.warning(
    "thesis_rank: %d%% of eligible assets in D_FRAGILE (threshold: 40%%), "
    "review fragility thresholds. run=%s",
    pct_fragile, run_id
)
```

Nao bloqueia o ranking, mas sinaliza para revisao em MF-G (validation).

**Q24: Bucket precedence e absoluta? A_DIRECT sempre acima de B_INDIRECT?**
R: **Sim, absoluta.** Essa e a decisao central do modo tese.

Justificativa:
- O usuario explicitamente pediu um modo onde "a tese domina a ordenacao".
- "Uma empresa muito boa no core, mas sem aderencia a tese, nao deve ficar acima de uma empresa boa com aderencia forte."
- Se o usuario nao quer precedencia absoluta, usa o Core Rank.
- O Thesis Rank existe para expressar convicao tematica, nao para ser um blend suave.

Mitigacao: A UI mostra claramente que o ranking e "Thesis Mode" e explica a regra de buckets. O usuario sempre pode alternar para Core Rank.

---

## Respostas sobre versionamento

**Q31: Como saber se um score foi calculado com pesos v1 ou v2, rubrica v1 ou v2, thresholds v1 ou v2?**
R: `plan2_runs.thesis_config_version` identifica pesos/thresholds da execucao. `plan2_thesis_scores.feature_input_json[dimensao].provenance.sourceVersion` identifica a versao da rubrica/formula por dimensao. Cada execucao tem seu `plan2_run_id` — nunca sobrescreve.

**Q32: Onde sera persistido?**
R: Duas tabelas:
- `plan2_runs`: thesis_config_version, pipeline_version, as_of_date, status, bucket_distribution_json, timestamps
- `plan2_thesis_scores`: feature_input_json (JSONB com provenance por dimensao), eligibility_json (com failed_reasons), explanation_json
Cada plan2_run_id e uma execucao imutavel. Recalcular cria nova run.

**Q33: O ranking exibido vai informar a versao da tese?**
R: Sim. A API retorna `thesisConfigVersion` e `plan2RunId` no metadata do response. A UI exibe como footer discreto: "Thesis v1.0.0 — calculado em DD/MM/YYYY".

---

## Schema de persistencia proposto (preview para MF-B1)

### Decisao: plan2_runs com identidade propria

O Thesis Rank tem identidade de execucao separada do strategy_run.
Motivo: o mesmo strategy_run pode gerar multiplas execucoes do Thesis Rank
(ex: apos mudar rubrica, threshold, ou pesos). Sem identidade propria,
UNIQUE(strategy_run_id, issuer_id) forca sobrescrita e mata auditabilidade.

`plan2_runs` e a entidade de execucao. `plan2_thesis_scores` referencia `plan2_run_id`.

```sql
-- Identidade de execucao do Thesis Rank
CREATE TABLE plan2_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_run_id UUID NOT NULL REFERENCES strategy_runs(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

  -- versioning
  thesis_config_version TEXT NOT NULL,    -- ex: "1.0.0"
  pipeline_version TEXT NOT NULL,         -- ex: "1.0.0"

  -- metadata
  as_of_date DATE NOT NULL,
  total_eligible INT NOT NULL,
  total_ineligible INT NOT NULL,
  bucket_distribution_json JSONB NOT NULL, -- {"A_DIRECT": 12, "B_INDIRECT": 8, ...}

  -- lifecycle
  status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
  error_message TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_plan2_runs_strategy ON plan2_runs(strategy_run_id);
CREATE INDEX idx_plan2_runs_tenant ON plan2_runs(tenant_id);

-- Scores por issuer por execucao
CREATE TABLE plan2_thesis_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plan2_run_id UUID NOT NULL REFERENCES plan2_runs(id) ON DELETE CASCADE,
  issuer_id UUID NOT NULL REFERENCES issuers(id),

  -- eligibility
  eligible BOOLEAN NOT NULL,
  eligibility_json JSONB NOT NULL,        -- BaseEligibility completo com failed_reasons

  -- opportunity vector (0-100, NULL se ineligible)
  direct_commodity_exposure_score FLOAT,
  indirect_commodity_exposure_score FLOAT,
  export_fx_leverage_score FLOAT,
  final_commodity_affinity_score FLOAT,

  -- fragility vector (0-100, NULL se ineligible)
  refinancing_stress_score FLOAT,
  usd_debt_exposure_score FLOAT,
  usd_import_dependence_score FLOAT,
  usd_revenue_offset_score FLOAT,
  final_dollar_fragility_score FLOAT,

  -- ranking (NULL se ineligible)
  bucket TEXT,                            -- A_DIRECT, B_INDIRECT, C_NEUTRAL, D_FRAGILE
  thesis_rank_score FLOAT,
  thesis_rank INT,

  -- provenance
  feature_input_json JSONB NOT NULL,     -- Plan2FeatureInput completo com provenance por dimensao
  explanation_json JSONB,                 -- Plan2Explanation (NULL se ineligible)

  -- audit
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (plan2_run_id, issuer_id)
);

CREATE INDEX idx_plan2_thesis_scores_run ON plan2_thesis_scores(plan2_run_id);
CREATE INDEX idx_plan2_thesis_scores_bucket ON plan2_thesis_scores(plan2_run_id, bucket, thesis_rank_score DESC);
CREATE INDEX idx_plan2_thesis_scores_eligible ON plan2_thesis_scores(plan2_run_id, eligible) WHERE eligible = true;
```

### O que isso resolve

| Cenario | Comportamento antigo (UNIQUE strategy_run_id, issuer_id) | Comportamento novo (plan2_run_id) |
|---------|--------------------------------------------------------|----------------------------------|
| Recalcular apos mudar rubrica | Sobrescreve, perde historico | Nova plan2_run, historico preservado |
| Recalcular apos mudar pesos | Sobrescreve | Nova plan2_run com thesis_config_version diferente |
| Comparar versoes | Impossivel | Filtrar por plan2_run_id, comparar lado a lado |
| Auditoria | Capenga | Cada execucao tem identidade, versao, timestamp, status |

---

## Provenance completa — exemplo concreto

Para VALE3, um registro completo ficaria:

```json
{
  "directCommodityExposure": {
    "score": 90,
    "sourceType": "SECTOR_PROXY",
    "sourceVersion": "sector-map-v1",
    "assessedAt": "2026-03-15",
    "assessedBy": null,
    "confidence": "low",
    "evidenceRef": null,
    "rawInput": { "sector": "Materiais Basicos", "subsector": "Mineracao" }
  },
  "refinancingStress": {
    "score": 35,
    "sourceType": "QUANTITATIVE",
    "sourceVersion": "quant-v1",
    "assessedAt": "2026-03-15",
    "assessedBy": null,
    "confidence": "high",
    "evidenceRef": "filing:uuid-xxx",
    "rawInput": {
      "short_term_debt": 15000000,
      "long_term_debt": 85000000,
      "debt_to_ebitda": 1.8,
      "interest_coverage": 8.5
    }
  },
  "usdDebtExposure": {
    "score": 30,
    "sourceType": "DEFAULT",
    "sourceVersion": "default-v1",
    "assessedAt": "2026-03-15",
    "assessedBy": null,
    "confidence": "low",
    "evidenceRef": null,
    "rawInput": null
  }
}
```
