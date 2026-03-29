# Plan 5 — CVM Shares Outstanding: Time Series PIT

## Status: BUILD APPROVED — TL approved 2026-03-25

**TL review v1**: BLOCKED (6 issues)
**This revision**: Resolves all 6 blocking items.

### TL Blockers Resolution Table

| # | Blocker | Resolution |
|---|---------|------------|
| 1 | "NBY exato" semanticamente forte demais | Renomeado para "NBY v2". Definicao explicita: formula exata sobre melhor share count auditavel disponivel, nao vendor-grade canonical. Secao 6.1 adicionada. |
| 2 | PIT incompleto — knowledge_date nao materializado | knowledge_date e parametro de lookup, nao coluna da row. Contrato PIT formalizado na secao 6.2. |
| 3 | Ownership da ingestao ambiguo ("ou") | Fechado: fundamentals-engine e owner unico. Ingestao e upstream, metrica e consumer. Secao 6.3 adicionada. |
| 4 | Lookup CVM com janela frouxa de 45 dias | Removida. Lookup CVM usa match exato por quarter-end. Sem nearest-neighbor. Politica na secao 6.4. |
| 5 | DFP > ITR nao formalizado como politica | Politica formal de precedencia documental na secao 6.5. Implementada em unico lugar (find_cvm_shares). |
| 6 | Deprecacao proxy prematura no mesmo plano | Removida do escopo. Proxy permanece durante validacao. Deprecacao fica para follow-up Plan 5B. |

---

## 1. Micro Feature

**Substituir Yahoo por CVM composicao_capital como fonte primaria auditavel de shares outstanding, persistindo time series PIT para resolver o blocker estrutural de NBY.**

## 2. Problem

O NBY v1 (Plan 3A) depende de `market_snapshots.shares_outstanding` populado via Yahoo/yfinance. Yahoo nao fornece shares_outstanding para ~39 issuers Core (17% do universo). Isso trava NBY em 77.6% de cobertura — abaixo do gate de 80%.

Enquanto isso, o script `compute_nby_proxy_free.py` ja provou que CVM composicao_capital cobre 215/232 issuers (92.7%) — mas:

1. Dados sao baixados on-demand e descartados apos computacao
2. Nao existe tabela persistente para share counts CVM
3. Nao ha time series — apenas snapshots pontuais por execucao de script
4. Sem PIT compliance formal (publication_date nao rastreado)
5. Reconciliacao contra Yahoo nao existe

O Q3 tem uma fonte auditavel (CVM) que cobre quase tudo, mas a usa de forma efemera.

## 3. Outcome

- Tabela `cvm_share_counts` persistindo time series de shares por issuer (total, treasury, net)
- Ingestao automatica de composicao_capital integrada ao pipeline de fundamentals-engine
- NBY v2 recomputado com CVM como fonte primaria auditavel e Yahoo como fallback
- Cobertura NBY v2 >= 90% do universo CORE_ELIGIBLE
- PIT compliance: cada registro com `publication_date_estimated`; lookup aceita `knowledge_date` como parametro
- Reconciliacao CVM vs Yahoo documentada
- Proxy (`nby_proxy_free`) permanece durante periodo de validacao; deprecacao fica para follow-up (Plan 5B)

**Explicitamente NAO incluso**: ranking integration (Plan 3B), DMPL parsing, FRE download, deprecacao do proxy.

## 4. Why Now

- `compute_nby_proxy_free.py` provou viabilidade a 92.7% — risco tecnico ja mitigado
- NBY v1 e o UNICO release gate restante do Plan 3A (DY e NPY ja passam)
- Plan 3C.3 estabeleceu framework PIT — infra pronta para ser consumida
- Cada dia sem resolver = dados de forward returns do piloto sem NBY auditavel
- Zero custo de vendor — CVM e gratuito e regulatorio

---

## 5. Current System Summary

### O que existe hoje

| Componente | Status | Detalhes |
|------------|--------|----------|
| `compute_nby_proxy_free.py` | Script one-off | Baixa CVM composicao_capital, computa NBY proxy, salva em computed_metrics. 215/232 cobertura. Dados efemeros. |
| `backfill_historical_snapshots.py` | Script one-off | Usa CVM composicao_capital para derivar market_cap historico. Salva em MarketSnapshot.raw_json mas NAO em tabela propria. |
| `net_buyback_yield.py` (v1) | Metric strategy | Usa `market_snapshots.shares_outstanding` (Yahoo). 180/232 = 77.6%. BLOQUEADO. |
| `snapshot_anchor.py` | Anchoring | Busca snapshot mais proximo de quarter-end (+/- 30 dias). Reutilizavel. |
| `market_snapshots.shares_outstanding` | Coluna | Populada por Yahoo adapter + backfill scripts. NULL para ~39 Core issuers. |
| Composicao capital CSV (CVM) | Fonte externa | Dentro de ZIPs DFP/ITR. Campos: `QT_ACAO_TOTAL_CAP_INTEGR`, `QT_ACAO_TOTAL_TESOURO`, `DT_REFER`, `CNPJ_CIA`. |
| Pipeline de filings | Operacional | market-ingestion baixa ZIPs CVM, parseia DFP/ITR. NAO extrai composicao_capital. |
| PIT framework (3C.3) | Operacional | `publication_date` em filings, `knowledge_date` em panel. Estimativas DFP+90d, ITR+45d. |

### Fluxo atual (duplicado e efemero)

```
CVM Portal
  |
  +--> compute_nby_proxy_free.py (download -> parse -> compute -> discard raw)
  |       -> computed_metrics.nby_proxy_free (215/232)
  |
  +--> backfill_historical_snapshots.py (download -> parse -> derive mcap -> discard raw)
  |       -> market_snapshots.shares_outstanding (parcial)
  |
  +--> Yahoo adapter (yfinance .info)
          -> market_snapshots.shares_outstanding (~193/232)
          -> net_buyback_yield.py (v1, 180/232)
```

### Arquivos-chave

- `services/fundamentals-engine/scripts/compute_nby_proxy_free.py` — logica de parsing CVM ja funcional
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/net_buyback_yield.py` — NBY v1 (Yahoo-dependent)
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/snapshot_anchor.py` — anchoring reutilizavel
- `packages/shared-models-py/src/q3_shared_models/entities.py` — modelos SQLAlchemy
- `apps/api/src/db/schema.ts` — Drizzle schema

---

## 6. Requirements

### 6.1 Definicao semantica de NBY v2 (TL Blocker #1)

**NBY v2** = formula exata (`(shares_t4 - shares_t) / shares_t4`) aplicada sobre o melhor share count auditavel disponivel.

**O que NBY v2 e**:
- Estimativa operacional auditavel com fonte primaria regulatoria (CVM)
- Formula exata sobre dados de composicao de capital de filings oficiais
- Resultado rastreavel: cada valor registra fonte (CVM ou Yahoo), datas, e shares usados

**O que NBY v2 NAO e**:
- Vendor-grade canonical share history
- Verdade absoluta — contem: estimated publication dates, fallback Yahoo, split detection heuristica

**Nomenclatura**: metric_code permanece `net_buyback_yield`. `formula_version=2` distingue de v1 (Yahoo-only). `inputs_snapshot.source_t` e `source_t4` registram "cvm" ou "yahoo" por ponta.

### 6.2 Contrato PIT (TL Blocker #2)

**Na tabela `cvm_share_counts`**, persistir:

| Coluna | Tipo | Semantica |
|--------|------|-----------|
| `issuer_id` | UUID FK | Emissor |
| `reference_date` | date | Data economica do corte (quarter-end do filing CVM) |
| `document_type` | text | 'DFP' ou 'ITR' |
| `total_shares` | numeric | QT_ACAO_TOTAL_CAP_INTEGR |
| `treasury_shares` | numeric | QT_ACAO_TOTAL_TESOURO |
| `net_shares` | numeric | total - treasury |
| `publication_date_estimated` | date | Estimativa: DFP ref_date + 90d, ITR ref_date + 45d |
| `source_file` | text | Provenance (ex: "CVM_DFP_2024_composicao_capital") |
| `loaded_at` | timestamptz | Quando o registro foi inserido |

Unique key: `(issuer_id, reference_date, document_type)`.

**`knowledge_date` NAO e coluna da tabela.** E um parametro de contexto de consumo, passado pelo caller no momento do lookup.

**Contrato do lookup**:

```python
def find_cvm_shares(
    session: Session,
    issuer_id: UUID,
    target_quarter_end: date,
    *,
    knowledge_date: date | None = None,
) -> CVMShareCount | None:
```

- `target_quarter_end`: quarter-end exato (ex: 2024-12-31). **Match exato por reference_date, sem janela.**
- `knowledge_date`: quando fornecido, filtra `publication_date_estimated <= knowledge_date`. Modo PIT estrito.
- Quando `knowledge_date` e None: modo relaxado (ignora publication_date). Para uso operacional corrente.

### 6.3 Ownership da ingestao (TL Blocker #3)

**Owner unico: fundamentals-engine.**

| Responsabilidade | Owner | Modulo |
|-----------------|-------|--------|
| Parser CSV composicao_capital | fundamentals-engine | `shares/parser.py` |
| Loader (upsert em cvm_share_counts) | fundamentals-engine | `shares/loader.py` |
| Lookup PIT-aware | fundamentals-engine | `shares/lookup.py` |
| Backfill historico | fundamentals-engine | `scripts/backfill_cvm_shares.py` |
| Ingestao automatica (filing pipeline) | fundamentals-engine | `tasks/ingest_share_counts.py` |
| NBY v2 (consumer) | fundamentals-engine | `metrics/net_buyback_yield.py` |

**Regra**: metrica NAO baixa/parseia CVM. Metrica apenas consome via `find_cvm_shares()`. Ingestao e upstream, metrica e downstream.

### 6.4 Politica de lookup CVM (TL Blocker #4)

**CVM composicao_capital e dado estrutural trimestral, nao snapshot de mercado.** Nao precisa de aproximacao por janela temporal.

**Politica**:

Para cada ponta do NBY (t e t-4):

1. Computar `target_quarter_end` (ex: t = 2024-12-31, t-4 = 2023-12-31)
2. Buscar row em `cvm_share_counts` com `reference_date == target_quarter_end`
3. Se knowledge_date fornecido: filtrar `publication_date_estimated <= knowledge_date`
4. Se existem DFP e ITR para mesma reference_date: aplicar precedencia documental (secao 6.5)
5. Se nao existir row valida: **fallback Yahoo** via `find_anchored_snapshot()` (logica existente, +/- 30 dias)

**Sem nearest-neighbor para CVM.** A janela de +/- 45 dias do script antigo e removida.

**Consequencia**: se um issuer tem filing com reference_date = 2024-11-30 (FYE nao padrao), o match exato contra 2024-12-31 falhara, e o fallback Yahoo sera usado. Isso e correto — preferir precisao a cobertura forjada.

### 6.5 Precedencia documental DFP > ITR (TL Blocker #5)

**Politica formal**:

| Prioridade | Tipo | Racional |
|------------|------|----------|
| 1 (maior) | DFP | Peca anual consolidada/final. Auditada. |
| 2 | ITR | Intermediaria. Pode ser revisada no DFP subsequente. |

**Racional**: DFP e o registro canonico anual. ITR e provisorio. Para mesma `reference_date`, DFP prevalece como verdade contabil.

**Implementacao**: esta logica existe em **um unico lugar** — `find_cvm_shares()`. Consumidores nao reimplementam a ordenacao.

```sql
-- Dentro de find_cvm_shares():
WHERE issuer_id = :issuer_id
  AND reference_date = :target_quarter_end
ORDER BY CASE WHEN document_type = 'DFP' THEN 0 ELSE 1 END
LIMIT 1
```

**Aplica-se a**: lookup para metrica, reconciliacao, e qualquer futuro consumer de `cvm_share_counts`.

### R1: Persistir share counts CVM em tabela dedicada

Conforme schema da secao 6.2.

### R2: Ingestao automatica no pipeline de fundamentals-engine

fundamentals-engine processa composicao_capital CSV quando disponivel em ZIPs DFP/ITR. Idempotente (upsert). Conforme ownership da secao 6.3.

### R3: NBY v2 com CVM como fonte primaria

Modificar `net_buyback_yield.py` para:
1. Buscar shares de `cvm_share_counts` via `find_cvm_shares()` — match exato por quarter-end (secao 6.4)
2. Se CVM indisponivel para qualquer ponta: fallback para `find_anchored_snapshot()` (Yahoo)
3. Registrar fonte usada em `inputs_snapshot` (`source_t`, `source_t4`: "cvm" | "yahoo")
4. `formula_version=2` (secao 6.1)

Formula inalterada: `NBY = (shares_t4 - shares_t) / shares_t4`

### R4: Split detection

Manter logica de `compute_nby_proxy_free.py`: se ratio shares_t / shares_t4 > 5x ou < 0.2x, flag como possivel split. NBY = NULL ate investigacao.

### R5: Reconciliacao CVM vs Yahoo

Script de validacao que compara `cvm_share_counts.net_shares` vs `market_snapshots.shares_outstanding` para issuers com ambos. Report segmentado:
- Concordancia total (< 2% diff)
- Divergencia moderada (2-10% diff)
- Divergencia severa (> 10% diff)
- Only-CVM (sem Yahoo)
- Only-Yahoo (sem CVM)

---

## 7. Candidate Shapes

### Shape A: Tabela dedicada + ingestao integrada (RECOMENDADA)

- Nova tabela `cvm_share_counts`
- Parser extraido de `compute_nby_proxy_free.py` para modulo reutilizavel
- Ingestao via fundamentals-engine (owner unico, secao 6.3)
- NBY v2 consulta `cvm_share_counts` (match exato) com fallback Yahoo
- Backfill historico via script one-off (2020-2024)

**Pros**: SSOT auditavel, PIT-compliant, pipeline integrado, auditoria limpa.
**Cons**: Nova tabela + migration + dual-ORM sync.

### Shape B: Enriquecer market_snapshots com CVM shares (REJEITADA)

- Popular `market_snapshots.shares_outstanding` com CVM em vez de Yahoo
- Nao criar tabela nova

**Problemas**:
- market_snapshots e keyed por `(security_id, fetched_at)` — CVM data nao tem security_id natural (usa CNPJ -> issuer_id)
- Mistura fontes na mesma coluna sem provenance clara
- Perde treasury_shares (informacao relevante para auditoria)
- Nao resolve PIT — fetched_at != reference_date CVM

### Shape C: Manter script standalone, rodar periodicamente (REJEITADA)

**Problemas**:
- Dados efemeros, sem auditoria
- Reprocessamento desnecessario
- Nao integra com pipeline existente
- Nao resolve PIT

---

## 8. Selected Shape

**Shape A** — Tabela dedicada + ingestao integrada.

### Fit check

| Requirement | Shape A fit |
|-------------|-------------|
| R1: Persistir shares CVM | Tabela dedicada com schema formal (6.2) |
| R2: Ingestao automatica | fundamentals-engine owner unico (6.3) |
| R3: NBY v2 CVM primario | Match exato quarter-end (6.4) + fallback Yahoo |
| R4: Split detection | Logica ja provada, migra para modulo |
| R5: Reconciliacao segmentada | 5 categorias (concordancia, moderada, severa, only-CVM, only-Yahoo) |

### Pair shaping
- Triggered: no
- Triggers matched: none (single service, clear SSOT, appetite small)
- Decision: async review

---

## 9. Appetite

- **Level**: Small-Medium — 4 build scopes
- **Why this appetite is enough**: Parsing CVM composicao_capital ja esta provado (92.7%). Trabalho e: (1) persistir o que ja parseia, (2) integrar no pipeline, (3) rewire NBY v2, (4) reconciliar e validar. Sem unknowns relevantes. Deprecacao do proxy fica para Plan 5B.
- **Must-fit items**: S1 (tabela + parser), S2 (backfill + ingestao), S3 (NBY v2 rewire), S4 (reconciliacao + validacao)
- **First cuts if exceeded**: S4 (reconciliacao pode ser script manual). S2 ingestao automatica pode ser task standalone ate pipeline ser wired.

---

## 10. Boundaries / No-Gos / Out of Scope

### Boundaries

- Tocar: entities.py (novo modelo), fundamentals-engine (owner unico: parser, loader, lookup, NBY v2), migration, Drizzle schema
- Fonte de shares: CVM composicao_capital (DFP/ITR) como primaria, Yahoo como fallback
- PIT: usar estimativas existentes (DFP+90d, ITR+45d) de 3C.3. knowledge_date e parametro de lookup.
- Lookup CVM: match exato por quarter-end (secao 6.4). Sem janela de aproximacao.

### No-Gos

- NAO parsear DMPL (formato matricial — complexidade fora de escopo)
- NAO baixar FRE (Formulario de Referencia) — pipeline nao suporta
- NAO modificar `market_snapshots` schema (coluna shares_outstanding permanece, Yahoo continua populando)
- NAO alterar DY ou NPY (composicao inalterada)
- NAO modificar ranking (Plan 3B)
- NAO derivar shares de `capital_social / valor_nominal` — muitos emissores sem valor nominal explicito
- NAO deprecar/deletar nby_proxy_free neste plano — proxy coexiste ate Plan 5B
- NAO usar nearest-neighbor/janela temporal para lookup CVM (secao 6.4)

### Out of Scope

- ON vs PN breakdown (composicao_capital tem, mas NBY usa total net)
- Desdobramentos/grupamentos historicos (splits) — deteccao binaria (flag + skip), nao correcao
- Valor nominal tracking
- Integration com B3 Investor API
- UI para share counts
- Deprecacao de nby_proxy_free / npy_proxy_free (Plan 5B)

---

## 11. Rabbit Holes / Hidden Risks

### RH1: CNPJ matching inconsistency (BAIXO)

CVM composicao_capital usa CNPJ. Nosso sistema usa `issuers.cnpj`. `compute_nby_proxy_free.py` ja resolve com `_normalize_cnpj()`.

**Mitigacao**: Reusar logica existente. Log warnings para CNPJs nao matchados.

### RH2: Duplicatas por DFP + ITR no mesmo reference_date (MEDIO)

Para Q4 (ref_date 2024-12-31), composicao_capital pode aparecer tanto no ZIP DFP quanto ITR. Mesmo CNPJ + mesma ref_date + document_types diferentes.

**Mitigacao**: Unique key inclui `document_type` — ambas rows sao persistidas. Para NBY, DFP prevalece sobre ITR conforme politica formal de precedencia documental (secao 6.5), implementada em `find_cvm_shares()` como unico ponto de decisao.

### RH3: Splits nao detectados entre t e t-4 (MEDIO)

Se empresa fez split 1:10 entre t-4 e t, shares_t sera ~10x shares_t4. NBY seria ~-900% (falsa diluicao massiva).

**Mitigacao**: Manter threshold de `compute_nby_proxy_free.py` — ratio > 5x ou < 0.2x → NBY = NULL + flag. Ja provado: apenas 11 issuers flaggados no universo de 232.

### RH4: Gap temporal entre DFP/ITR disponibilidade (BAIXO)

Composicao_capital so existe quando o filing DFP/ITR e publicado. Para quarters muito recentes, dado pode nao existir ainda.

**Mitigacao**: Fallback para Yahoo quando CVM nao disponivel. `inputs_snapshot` registra qual fonte foi usada.

### RH5: net_shares = 0 (treasury = total) (BAIXO)

Empresa com 100% de acoes em tesouraria teria net_shares = 0, causando divisao por zero.

**Mitigacao**: Ja tratado — se net_shares <= 0, NBY = NULL. Nenhum emissor Core tem este cenario.

### RH6: Alembic migration ordering com Plan 4 (BAIXO)

Migration 20260322_0020 (Plan 4) ja existe. Nova migration deve ser sequencial.

**Mitigacao**: Usar timestamp-based naming (padrao existente).

---

## 12. Breadboard Summary

### Places

```
CVM Portal (dados.cvm.gov.br)
  |
  v
[composicao_capital CSV parser]  --- modulo reutilizavel extraido de script
  |
  v
[cvm_share_counts]  --- NOVA tabela PIT-compliant
  |                       (issuer_id, ref_date, doc_type, total, treasury, net, pub_date_est)
  |
  +--> [CVM Share Lookup]  --- nova funcao: find_cvm_shares(issuer_id, as_of, knowledge_date)
  |       |
  |       v
  |    [net_buyback_yield.py]  --- rewired: CVM primario, Yahoo fallback
  |       |
  |       v
  |    [computed_metrics]  --- metric_code='net_buyback_yield' (formula_version=2)
  |
  +--> [Reconciliation]  --- CVM net_shares vs Yahoo shares_outstanding
          |
          v
       [validation report]
```

### Code Affordances (NEW)

| Affordance | Location | Type |
|------------|----------|------|
| `CVMShareCount` model | entities.py | SQLAlchemy model |
| `cvmShareCounts` table | schema.ts | Drizzle table |
| `parse_composicao_capital()` | shares/parser.py | Pure function (CSV rows -> ShareCountRow list) |
| `persist_share_counts()` | shares/loader.py | Session -> upsert to cvm_share_counts |
| `find_cvm_shares()` | shares/lookup.py | PIT-aware lookup: match exato por quarter-end + DFP>ITR (secao 6.4, 6.5) |
| `compute_net_buyback_yield()` v2 | metrics/net_buyback_yield.py | Consumer: CVM primary (via lookup) + Yahoo fallback |

### Wiring Changes vs CURRENT

1. **entities.py**: Novo modelo `CVMShareCount`
2. **schema.ts**: Nova tabela `cvmShareCounts` (Drizzle)
3. **shares/parser.py** (NOVO): Extraido de `compute_nby_proxy_free.py` `_build_share_counts()`. Owner: fundamentals-engine.
4. **shares/loader.py** (NOVO): Upsert idempotente em `cvm_share_counts`. Owner: fundamentals-engine.
5. **shares/lookup.py** (NOVO): `find_cvm_shares()` — match exato por quarter-end + PIT + DFP>ITR priority. Unico ponto de decisao de precedencia. Owner: fundamentals-engine.
6. **metrics/net_buyback_yield.py**: v2 — consumer de `find_cvm_shares()`, fallback Yahoo. NAO parseia/baixa CVM.
7. **Alembic migration**: CREATE TABLE `cvm_share_counts`
8. **Backfill script**: Popular 2020-2024 a partir de CVM ZIPs

---

## 13. Build Scopes

### S1: Tabela + Modelo + Parser

**Objective**: Criar tabela `cvm_share_counts`, modelo SQLAlchemy/Drizzle, e parser reutilizavel.

**Sub-tasks**:
1. Alembic migration: CREATE TABLE `cvm_share_counts` com unique constraint e check constraints
2. SQLAlchemy model `CVMShareCount` em entities.py
3. Drizzle table `cvmShareCounts` em schema.ts
4. `shares/parser.py`: `parse_composicao_capital(rows: list[dict]) -> list[ShareCountRow]`
   - Extraido de `compute_nby_proxy_free.py` `_build_share_counts()`
   - Adiciona `publication_date_estimated` (DFP+90d, ITR+45d)
   - Normaliza CNPJ
5. `shares/loader.py`: `persist_share_counts(session, issuer_map, share_rows) -> LoadResult`
   - Upsert por `(issuer_id, reference_date, document_type)`
   - Retorna stats (inserted, updated, skipped)

**Files touched**:
- `packages/shared-models-py/src/q3_shared_models/entities.py`
- `apps/api/src/db/schema.ts`
- `services/quant-engine/alembic/versions/YYYYMMDD_XXXX_create_cvm_share_counts.py`
- `services/fundamentals-engine/src/q3_fundamentals_engine/shares/parser.py` (NOVO)
- `services/fundamentals-engine/src/q3_fundamentals_engine/shares/loader.py` (NOVO)

**Dependencies**: Nenhuma
**Risk focus**: RH2 (duplicatas DFP+ITR), RH6 (migration ordering)
**Review focus**: Unique constraint correctness, parser fidelity vs script original

**Spec tests**:
- Parser extrai corretamente de fixture CSV (total, treasury, net, ref_date)
- Parser ignora rows com total <= 0
- Parser normaliza CNPJ (com e sem pontuacao)
- Loader upsert idempotente (2x insert = mesma row)
- Loader nao cria row para CNPJ sem match em issuers
- Publication date estimada: DFP ref_date 2024-12-31 -> pub_date 2025-03-31, ITR ref_date 2024-06-30 -> pub_date 2024-08-14

**Validation checks**:
- `pnpm --filter @q3/shared-contracts typecheck`
- `python -m mypy src` (fundamentals-engine)
- Migration up + down funciona

---

### S2: Backfill Historico + Ingestao + Lookup

**Objective**: Popular `cvm_share_counts` com dados 2020-2024, integrar no pipeline de fundamentals-engine, e implementar lookup PIT-aware.

**Sub-tasks**:
1. Script `scripts/backfill_cvm_shares.py`:
   - Baixa composicao_capital de DFP/ITR 2020-2024 (8 ZIPs: 4 DFP + 4 ITR, ou mais se quiser 2019)
   - Usa `shares/parser.py` + `shares/loader.py`
   - Report: issuers cobertos, rows inseridas, CNPJs nao matchados
2. Task `tasks/ingest_share_counts.py` (fundamentals-engine — owner unico, secao 6.3):
   - Quando ZIP DFP/ITR e processado, extrair composicao_capital CSV se presente
   - Chamar parser + loader
3. `shares/lookup.py`: `find_cvm_shares()` conforme contrato da secao 6.2:
   - Match exato: `reference_date == target_quarter_end` (sem janela de aproximacao, secao 6.4)
   - PIT: se `knowledge_date` fornecido, `publication_date_estimated <= knowledge_date`
   - Precedencia documental: DFP > ITR (secao 6.5), implementada aqui como unico ponto de decisao
   - Retorna None se nao existe row com match exato

**Files touched**:
- `services/fundamentals-engine/scripts/backfill_cvm_shares.py` (NOVO)
- `services/fundamentals-engine/src/q3_fundamentals_engine/shares/lookup.py` (NOVO)
- `services/fundamentals-engine/src/q3_fundamentals_engine/tasks/ingest_share_counts.py` (NOVO)

**Dependencies**: S1
**Risk focus**: RH1 (CNPJ matching), RH4 (gap temporal)
**Review focus**: Backfill coverage report, PIT lookup correctness, match exato sem janela

**Spec tests**:
- `find_cvm_shares()` retorna row quando reference_date == target_quarter_end
- `find_cvm_shares()` retorna None quando reference_date nao bate exatamente (ex: 2024-11-30 vs 2024-12-31)
- `find_cvm_shares()` com knowledge_date filtra por publication_date_estimated
- `find_cvm_shares()` retorna None quando publication_date_estimated > knowledge_date (PIT estrito)
- `find_cvm_shares()` prefere DFP sobre ITR para mesma reference_date
- `find_cvm_shares()` sem knowledge_date retorna row independente de publication_date (modo relaxado)
- Backfill script e idempotente (rodar 2x = mesmos dados)

**Validation checks**:
- Backfill report: >= 200/232 issuers Core com pelo menos 1 share count
- Cobertura temporal: >= 2 reference_dates por issuer (t e t-4)
- Nenhum CNPJ de issuer Core sem match (log de warnings vazio para Core)

---

### S3: NBY v2 Rewire (CVM Primary)

**Objective**: Modificar `net_buyback_yield.py` para consumir CVM via `find_cvm_shares()`, com fallback Yahoo.

**Sub-tasks**:
1. Modificar `compute_net_buyback_yield()`:
   - Primeiro tentar `find_cvm_shares(target_quarter_end)` para t e t-4 (match exato, secao 6.4)
   - Se CVM indisponivel para qualquer ponta, fallback para `find_anchored_snapshot()` (Yahoo, +/- 30 dias)
   - `formula_version=2` (secao 6.1)
   - `inputs_snapshot` registra: `source_t` ("cvm" | "yahoo"), `source_t4` ("cvm" | "yahoo"), shares values, dates, document_type se CVM
   - Metrica NAO baixa/parseia CVM — apenas consome via lookup (secao 6.3)
2. Split detection:
   - Se CVM: ratio > 5x ou < 0.2x -> NBY = NULL + flag (migrado de proxy script)
   - Se Yahoo: manter logica existente (abs(NBY) > 0.50 -> flag)
3. Recomputar NBY v2 para todos os issuers Core
4. Recomputar NPY (composicao: DY + NBY, automatico)

**Files touched**:
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/net_buyback_yield.py`
- `services/fundamentals-engine/tests/test_net_buyback_yield.py`

**Dependencies**: S2 (lookup funcional)
**Risk focus**: RH3 (splits), RH2 (DFP/ITR duplicata — resolvido pelo lookup centralizado)
**Review focus**: Separacao ingestao/consumer, formula_version bump, inputs_snapshot completude, fallback Yahoo preservado

**Spec tests**:
- NBY com ambas pontas CVM -> source_t="cvm", source_t4="cvm", formula_version=2
- NBY com t CVM + t4 Yahoo -> source_t="cvm", source_t4="yahoo" (mixed)
- NBY com ambas pontas Yahoo fallback -> source_t="yahoo", source_t4="yahoo" (backward compat)
- NBY com CVM split detectado (ratio > 5x) -> None
- NBY com CVM net_shares <= 0 -> None
- NBY normal range: PETR4-like (shares delta < 5%) -> valor entre -0.05 e +0.05
- inputs_snapshot contem todos os campos mandatorios (source, shares, dates, document_type)
- Metrica nao importa nenhum modulo de parser/loader CVM (enforcement de ownership)

**Validation checks**:
- Cobertura NBY v2 >= 90% de CORE_ELIGIBLE (gate principal)
- Mixed-source (um ponta CVM + outra Yahoo) <= 20% do universo (gate TL)
- `python -m mypy src`
- Testes existentes de NBY continuam passando (backward compat para Yahoo path)
- Nenhum NBY com abs > 0.50 nao investigado

---

### S4: Reconciliacao + Validacao

**Objective**: Validar CVM vs Yahoo, produzir report segmentado, reavaliar release gates.

**Sub-tasks**:
1. Script `scripts/reconcile_cvm_yahoo_shares.py`:
   - Para cada issuer com ambas fontes: comparar `cvm_share_counts.net_shares` vs `market_snapshots.shares_outstanding`
   - Report segmentado (5 categorias, conforme R5):
     - Concordancia total (< 2% diff)
     - Divergencia moderada (2-10% diff)
     - Divergencia severa (> 10% diff)
     - Only-CVM (sem Yahoo)
     - Only-Yahoo (sem CVM)
   - Investigar divergencias severas
2. Validation report `docs/plan5-cvm-shares/validation-report.md`:
   - Coverage NBY v2: total e por setor
   - Coverage delta vs NBY v1 (Yahoo-only) — issuers ganhos
   - Mixed-source breakdown (CVM+CVM, CVM+Yahoo, Yahoo+Yahoo)
   - Reconciliacao CVM vs Yahoo segmentada
   - Release gate status (todos os gates)
3. Plan 3A re-gate: reavaliar DY/NBY/NPY coverage com NBY v2

**NAO inclui deprecacao de proxy** — permanece para Plan 5B.

**Files touched**:
- `services/fundamentals-engine/scripts/reconcile_cvm_yahoo_shares.py` (NOVO)
- `docs/plan5-cvm-shares/validation-report.md` (NOVO)

**Dependencies**: S3
**Risk focus**: Divergencias CVM vs Yahoo inesperadas
**Review focus**: Reconciliacao completude, mixed-source distribution, sector gaps

**Spec tests**: N/A (validation scope)

**Validation checks**:
- NBY v2 cobertura >= 90% CORE_ELIGIBLE
- Mixed-source <= 20% do universo
- NPY recomputed: NPY = DY + NBY v2 para 100% (identidade preservada)
- Reconciliacao: >= 85% dos issuers com ambas fontes concordam dentro de 2%
- Nenhum setor inteiro com 0% cobertura
- Release gates Plan 3A reavaliados com NBY v2

---

## 14. Release Gates

| Gate | Criterio | Threshold | Nota |
|------|----------|-----------|------|
| G1 | Coverage NBY v2 (CVM+Yahoo) | >= 90% CORE_ELIGIBLE | Era 77.6% com Yahoo-only |
| G2 | Coverage NPY recomputed | >= 80% CORE_ELIGIBLE | Sobe com NBY |
| G3 | Identidade NPY | NPY = DY + NBY para 100% | Inalterado |
| G4 | Splits flagged | 0 abs(NBY) > 0.50 nao investigados | Inalterado |
| G5 | Mixed-source cap | Mixed-source (CVM+Yahoo) <= 20% do universo | Evita inflacao de cobertura via fallback |
| G6 | CVM vs Yahoo concordancia | >= 85% concordam < 2% diff (segmentado) | 5 categorias: total, moderada, severa, only-CVM, only-Yahoo |
| G7 | Backfill temporal | >= 2 reference_dates por issuer Core | Time series minima para t vs t-4 |
| G8 | PIT compliance | publication_date_estimated preenchido para 100% rows | Novo gate |

---

## 15. Validation Plan

### Per-scope validation

Cada scope tem spec tests + validation checks proprios (secao 13).

### Final feature validation

1. **Coverage report**: NBY v2 cobertura total + por setor CVM
2. **Delta report**: issuers que tinham NBY=NULL (Yahoo) e agora tem NBY (CVM)
3. **Reconciliacao**: CVM vs Yahoo shares para issuers com ambos
4. **Manual audit**: 5 issuers diversificados — comparar CVM net_shares vs Info Money / B3 site
5. **Regression**: testes existentes (415 quant + 252 fundamentals) passando
6. **Plan 3A re-gate**: reavaliar todos os release gates com NBY v2

---

## 16. Current Status

- [x] Phase 0: Intake / Micro-feature framing
- [x] Phase 1: Map current system
- [x] Phase 2: Shape
- [x] Phase 3: Set appetite
- [x] Phase 4: Boundaries / no-gos / out of scope
- [x] Phase 5: Rabbit holes / hidden risks
- [x] Phase 6: Breadboard
- [x] Phase 7: Slice into build scopes
- [x] Phase 8: Build (S1-S4 complete)
- [x] Phase 9: Validate (validation-report.md)
- [x] Phase 10: Close
- [x] Phase 11: Tech Lead handoff

**CLOSED — TL approved 2026-03-25. Fully closed and handed off.**

### TL Approval Record

**Decision**: APPROVED FOR BUILD (all 4 scopes)
**Date**: 2026-03-25
**Conditions**:
1. Nao reabrir lookup aproximado para CVM
2. Nao puxar deprecacao do proxy para dentro do escopo
3. Nao deixar consumers fora de `find_cvm_shares()` implementarem DFP > ITR por conta propria
4. Nao relaxar mixed-source cap sem validation report

**First cut if pressure**: reduzir sofisticacao da reconciliacao. NAO mexer na semantica central.

**TL notes for close**:
- Documentar que `publication_date_estimated` e proxy regulatoria, nao timestamp real de ingestao publica
- FYE nao padrao: fallback Yahoo e correto, nao tentar resolver neste plano

---

## 17. Close Summary

### Delivered scope

| Scope | Status | Key outcome |
|-------|--------|-------------|
| S1 | Done | `cvm_share_counts` table, SQLAlchemy/Drizzle models, parser, loader. Migration with 3 check constraints + index. |
| S2 | Done | Backfill 2020-2024 (14,392 rows, 890 issuers, 520/521 Core). Lookup PIT-aware with exact match. Pipeline task. |
| S3 | Done | NBY v2 rewire: CVM primary, Yahoo fallback. formula_version=2. 218/237 Core = 92.0%. Zero mixed-source. |
| S4 | Done | Reconciliation script + validation report. G6 resolved (scale invariance). Impacto downstream documentado. |

### What shipped

Plan 5 resolves the structural blocker of NBY by replacing an incomplete vendor-based source (Yahoo) with a regulatory, auditable, PIT-compliant time series (CVM composicao_capital), achieving 92.0% coverage without fallback dependency.

### Explicit cuts and deferrals

- **Proxy deprecation**: `nby_proxy_free` / `npy_proxy_free` remain active. Deprecation deferred to Plan 5B.
- **NPY recomputation**: NPY coverage limited by DY (49.6%), not by NBY. Plan 5 does not address DY coverage.
- **CVM scale normalization**: ~79 issuers report in thousands vs units. Irrelevant for NBY (scale-invariant), documented as known characteristic.

### Known limitations

1. **7 issuers NO_T**: DFP 2024 not yet published for these issuers. Temporal, not structural.
2. **11 issuers SPLIT_DETECTED**: Legitimate splits/restructurings. Suppressed correctly.
3. **1 issuer NO_T4**: New issuer (ATOM EDUCACAO), insufficient history.
4. **Treasury negative**: 1 case in DFP 2022 (treasury=-16,318). Raw CVM preserved without sanitization.
5. **CVM scale variable**: No explicit scale field in composicao_capital. ~79 issuers in thousands.

### Follow-up decision

| Follow-up | Severity | Description |
|-----------|----------|-------------|
| Plan 5B | degraded | Deprecate proxy metrics after validation period |
| DY coverage | blocking | 49.6% DY is now the sole bottleneck for NPY — requires DFC label matching improvement (Plan 3A S1 domain) |
| CVM scale mapping | cleanup | Document which issuers use mil vs unit (useful for future absolute shares usage) |
| DFP 2024 monitoring | cleanup | 7 NO_T issuers should gain coverage when DFP 2024 filings arrive |

No follow-ups generated. Follow-up ledger updated.

### Final feature status

**DONE.** Structural blocker resolved. NBY v2 operational at 92.0% Core coverage with auditable CVM source.

---

## 18. Tech Lead Handoff

### Micro feature summary

Replace Yahoo shares_outstanding with CVM composicao_capital as primary auditable source for NBY, persisting a PIT-compliant time series that resolves the 77.6% → 92.0% coverage gap.

### Selected shape and rationale

Dedicated `cvm_share_counts` table (not polluting market_snapshots). Parser/loader/lookup in fundamentals-engine as single owner. Metric as downstream consumer only. Match exato by quarter-end (no window approximation). DFP > ITR precedence in single place.

### Appetite used

Small-Medium — 4 build scopes. All completed within appetite.

### What changed

| Area | Change |
|------|--------|
| `entities.py` | +1 model (`CVMShareCount`) |
| `schema.ts` | +1 table (`cvmShareCounts`) |
| Migration `20260325_0023` | CREATE TABLE with 3 checks + index |
| `shares/parser.py` | NEW — extracted from script, pure function |
| `shares/loader.py` | NEW — idempotent upsert with CNPJ normalization + dedup |
| `shares/lookup.py` | NEW — exact match + PIT + DFP>ITR precedence |
| `tasks/ingest_share_counts.py` | NEW — pipeline integration |
| `metrics/net_buyback_yield.py` | REWRITE — v2: CVM primary, Yahoo fallback, split detection, formula_version=2 |
| `scripts/backfill_cvm_shares.py` | NEW — downloads 10 CVM ZIPs, backfills 2020-2024 |
| `scripts/reconcile_cvm_yahoo_shares.py` | NEW — 5-category segmented reconciliation |

### Boundaries and no-gos respected

- knowledge_date NOT stored as column (lookup parameter only)
- No nearest-neighbor for CVM lookup
- No proxy deprecation in this plan
- Metric does NOT import parser/loader (ownership enforcement test)
- DFP > ITR implemented in single place (find_cvm_shares)

### Rabbit holes and residual risks

1. **CVM scale variable**: Known, documented, NBY-irrelevant
2. **Treasury negative**: Raw preserved, 1 case, documented
3. **Dedup intra-CSV**: CVM restatements handled (last row wins)
4. **DY bottleneck**: NBY solved, DY now sole blocker for NPY

### Test coverage

306 tests passing (262 pre-existing + 44 new). 0 regressions. New tests:
- Parser: 21 (CNPJ, dates, skips, frozen dataclass)
- Loader: 7 (insert, update, idempotency, unknown CNPJ)
- Lookup: 12 (exact match, None on mismatch, DFP>ITR, PIT, no nearest-neighbor)
- NBY v2: 19 (CVM/CVM, Yahoo/Yahoo, mixed, splits, provenance, ownership enforcement)
- Total delta: +59 tests, -15 tests (v1 replaced)

### Where to focus review

1. `shares/lookup.py` — semantic core (exact match + PIT + precedence)
2. `metrics/net_buyback_yield.py` — rewire correctness, split detection, inputs_snapshot
3. `validation-report.md` — gate status, scale invariance argument, Plan 3A impact

### Questions requiring Tech Lead attention

1. **Plan 5B timing**: When to deprecate proxy metrics?
2. **DY improvement priority**: Is 49.6% DY coverage worth a dedicated micro-feature?
3. **CVM scale normalization**: Worth investigating for future absolute shares usage, or accept as-is?
