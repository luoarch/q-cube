# Plan 3A — Net Payout Yield: Foundation

## Status: SHAPING v2 — Tech Lead gates addressed

**Tech Lead review v1**: BLOCKED (7 issues, 4 gates required)
**This revision**: Resolves all 7 blocking items. S6 (ranking) removed from must-fit.

---

## 1. Micro Feature

**Computar Net Payout Yield (NPY) como metrica auditavel no Q3, com cobertura e qualidade suficientes para uso futuro em ranking.**

Esta fase NAO integra NPY no ranking. Entrega metricas computadas validadas.

## 2. Problem

O Q3 nao possui NENHUMA metrica de retorno ao acionista. Dos 12 computed_metrics atuais, zero capturam dividendos, JCP, ou recompras. Isso significa que:

- Estrategias de selecao ignoram completamente a politica de payout das empresas
- Empresas que distribuem capital via recompras sao invisiveis
- A Magic Formula (EY + ROC) avalia apenas earning power e eficiencia de capital, sem considerar distribuicao

## 3. Outcome

- `dividend_yield` (TTM) disponivel como computed_metric
- `net_buyback_yield` disponivel como computed_metric
- `net_payout_yield` disponivel como computed_metric
- Cobertura validada por setor com quality gates
- Compat view atualizada para consumo futuro
- Metricas auditaveis com inputs_snapshot + formula_version

**Explicitamente NAO incluso**: ranking integration (greenblatt_npy fica bloqueado ate NPY provar cobertura e estabilidade).

## 4. Why Now

- Plan 2 (Thesis Layer) estavel — fundacao para metricas avancadas
- Metodologia academica formalizada (Boudoukh et al. 2007)
- Dados CVM (DFC) ja parseados — ~129k sub-account lines com canonical_key=NULL, prontos para mapeamento
- `sharesOutstanding` ja disponivel em `raw_json` dos market_snapshots (yfinance)

---

## 5. Current System Summary

### O que existe hoje

| Componente | Status | Detalhes |
|------------|--------|----------|
| Canonical keys | 28 mapeadas | Nenhuma para dividendos, JCP, ou shares |
| MetricCode enum | 12 metricas | Nenhuma de payout/dividend |
| DFC parsing | Funcional | DFC_MD/DFC_MI parseados. Level 1 mapeado (6.01, 6.02, 6.03). ~129k linhas de sub-contas armazenadas com canonical_key=NULL |
| DMPL parsing | Armazenado cru | Formato matricial (CD_CONTA x COLUNA_DF). Nao normalizado. |
| Shares outstanding | NAO extraido, MAS disponivel | yfinance retorna `sharesOutstanding` no `.info` dict. Salvo em `market_snapshots.raw_json` mas nao extraido para coluna propria |
| TTM computation | Nao existe | Engine computa apenas por reference_date unico |
| ITR period semantics | YTD acumulado | ITR DRE/DFC contem valores Jan-1 ate quarter-end, NAO standalone trimestral |
| Market snapshots | Funcional | price + market_cap via Yahoo. `raw_json` preserva payload completo incluindo sharesOutstanding |
| Ranking strategies | 3 variantes | magic_formula_original, _brazil, _hybrid. Todas usam EY + ROC |
| Compat view | Funcional | v_financial_statements_compat com 15 colunas |

### Fluxo atual de metricas

```
CVM ZIP -> Parser (DFP/ITR) -> statement_lines (canonical_key mapped para nivel 1)
                                       |
                              MetricsEngine.compute_for_issuer()
                                       |
                              computed_metrics (12 metricas)
                                       |
                              v_financial_statements_compat (mat view)
                                       |
                              ranking.py -> RankedAsset
```

### Arquivos-chave afetados

- `packages/shared-models-py/src/q3_shared_models/entities.py` — CanonicalKey enum, MetricCode enum, MarketSnapshot model
- `services/fundamentals-engine/src/q3_fundamentals_engine/normalization/canonical_mapper.py` — CVM code -> canonical key
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/engine.py` — MetricsEngine
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/` — strategy classes
- `services/fundamentals-engine/src/q3_fundamentals_engine/providers/yahoo/adapter.py` — Yahoo adapter (shares extraction)
- `services/fundamentals-engine/src/q3_fundamentals_engine/providers/base.py` — YahooInfoPayload TypedDict
- `services/quant-engine/alembic/versions/` — migration para compat view
- `apps/api/src/db/schema.ts` — Drizzle schema (MetricCode sync)

---

## 6. Operational Metric Spec (Gate 1)

### 6.1 Net Payout Yield — Formula oficial

```
NPY(i,t) = DividendYield_TTM(i,t) + NetBuybackYield(i,t)
```

### 6.2 Dividend Yield TTM

```
DividendYield_TTM(i,t) = TotalPayoutTTM(i,t) / MCAP(i,t)
```

Onde:

```
TotalPayoutTTM(i,t) = abs(sum of dividends_paid + jcp_paid across 4 standalone quarters ending at t)
```

**Convencao de sinal**: No DFC/CVM, dividendos pagos sao NEGATIVOS (saida de caixa). A strategy aplica `abs()` para que DividendYield seja positivo. O `inputs_snapshot` preserva o valor original negativo para auditabilidade.

**MCAP**: `market_cap` do snapshot mais recente dentro da janela de tolerancia (ver 6.5).

### 6.3 Net Buyback Yield

```
NetBuybackYield(i,t) = (Shares(i, t-4) - Shares(i, t)) / Shares(i, t-4)
```

Onde:

- `Shares(i, t)` = `shares_outstanding` da coluna `market_snapshots.shares_outstanding`, populada via yfinance
- `Shares(i, t-4)` = `shares_outstanding` do snapshot ancorado em `t - 4 trimestres`
- Positivo = recompra liquida (bom para acionista)
- Negativo = emissao liquida (diluicao)

**NAO usar** `market_cap / price` como proxy de shares. Ver ADR (secao 7).

**Fonte de shares (atualizado pos-spike S1)**: `raw_json` estava vazio (`{}`) para todos os 175k snapshots existentes — adapter filtrava antes de salvar. Backfill via raw_json impossivel. Nova abordagem: usar `yf.Ticker.quarterly_balance_sheet["Ordinary Shares Number"]` para backfill historico + `sharesOutstanding` de `.info` para snapshots futuros. Ver ADR revisado.

### 6.4 TTM Computation — Regras de quarter extraction

CVM ITR armazena valores YTD acumulados, NAO standalone trimestral. Para extrair standalone:

```
Q_standalone(q) = YTD(q) - YTD(q-1)
```

Regras explicitas:

| Quarter | Calculo standalone | Fonte YTD(q) | Fonte YTD(q-1) |
|---------|-------------------|--------------|-----------------|
| Q1 | YTD_Q1 (ja e standalone) | ITR ref_date = YYYY-03-31 | N/A (zero) |
| Q2 | YTD_Q2 - YTD_Q1 | ITR ref_date = YYYY-06-30 | ITR ref_date = YYYY-03-31 |
| Q3 | YTD_Q3 - YTD_Q2 | ITR ref_date = YYYY-09-30 | ITR ref_date = YYYY-06-30 |
| Q4 | YTD_annual - YTD_Q3 | DFP ref_date = YYYY-12-31 | ITR ref_date = YYYY-09-30 |

**Regra de prioridade DFP vs ITR para Q4**:
- Se DFP existe para o ano fiscal, usar DFP como YTD_annual (source of truth)
- Se DFP nao existe mas ITR Q4 existe, usar ITR Q4 como YTD_annual
- Se ambos existem para mesmo ref_date (2024-12-31): DFP prevalece (filing_type='DFP' > filing_type='ITR')

**Regra de completeness**:
- TTM requer EXATAMENTE 4 quarters standalone consecutivos
- Se qualquer quarter esta faltando (filing nao existe): TTM = NULL
- Nao interpolar, nao preencher com zeros
- Quarters incompletos sao melhor que dados inventados

**Regra de escopo**:
- Preferir scope='con' (consolidado). Se nao disponivel, scope='ind' (individual)
- TODOS os 4 quarters devem usar o MESMO escopo. Nao misturar con+ind

**Regra de versao (restatements)**:
- Usar `MAX(version_number)` por filing/ref_date (mesmo comportamento do engine atual)

### 6.5 Snapshot Temporal Anchoring

Para alinhar shares e market_cap com quarters contabeis:

**Convencao: quarter-end anchored com janela de tolerancia**

```
snapshot_for_quarter(ref_date) = snapshot mais recente WHERE:
  - fetched_at >= ref_date - 30 dias
  - fetched_at <= ref_date + 30 dias
  - ORDER BY abs(fetched_at - ref_date) ASC
  - LIMIT 1
```

| Parametro | Valor | Justificativa |
|-----------|-------|---------------|
| Janela | +/- 30 dias do quarter-end | Publicacao de ITR ocorre ate 45 dias apos quarter-end. 30 dias captura snapshots proximos sem ser permissivo demais |
| Precedencia | Snapshot mais proximo do ref_date | Minimiza drift temporal |
| Fallback | NULL | Se nenhum snapshot na janela, NBY = NULL para esse issuer/periodo |
| Provider lock | Todos os snapshots do MESMO issuer devem vir do mesmo provider (source) | Evita inconsistencia cross-provider |

**Para `t` (quarter mais recente)**: snapshot ancorado no ref_date do quarter mais recente
**Para `t-4` (4 quarters atras)**: snapshot ancorado no ref_date de 4 quarters atras

### 6.6 Politica de NULL

| Situacao | Resultado |
|----------|-----------|
| Faltam <4 quarters de payout data | dividend_yield = NULL |
| Nenhum snapshot na janela para t ou t-4 | net_buyback_yield = NULL |
| sharesOutstanding ausente no raw_json | net_buyback_yield = NULL |
| Shares(t-4) = 0 | net_buyback_yield = NULL (divisao por zero) |
| dividend_yield = NULL | net_payout_yield = NULL |
| net_buyback_yield = NULL | net_payout_yield = NULL |
| Ambos componentes disponiveis | net_payout_yield = dividend_yield + net_buyback_yield |

**Consequencia para ranking (futuro S6)**: ativo com NPY NULL sera EXCLUIDO do universo elegivel de greenblatt_npy. Nao recebe penalidade nem score neutro. Isso e uma decisao arquitetural: NPY NULL significa "dados insuficientes para avaliar", nao "payout zero". Elegibilidade exige dados, nao assume.

### 6.7 Politica de sinais — resumo

| Metrica | Sinal esperado | Origem |
|---------|---------------|--------|
| dividends_paid (statement_line) | Negativo (saida de caixa) | CVM DFC |
| jcp_paid (statement_line) | Negativo (saida de caixa) | CVM DFC |
| TotalPayoutTTM | Positivo (abs aplicado) | Computed |
| DividendYield | Positivo (payout/mcap) | Computed |
| NetBuybackYield | Positivo = recompra, Negativo = diluicao | Computed |
| NetPayoutYield | Pode ser negativo (diluicao > payout) | Computed |

---

## 7. ADR — Shares Outstanding Source (Gate 2)

### Decision: Usar `sharesOutstanding` de yfinance raw_json

### Context

Para computar Net Buyback Yield, precisamos de shares outstanding em dois pontos temporais (t e t-4). Tres opcoes foram avaliadas.

### Options Considered

#### Option A: Derivar de market_cap / price (REJEITADA)

```
shares = market_cap / price
```

**Problemas**:
- `price` no market_snapshots e `regularMarketPrice` (unadjusted, intraday). Nao e adjusted close.
- `market_cap` no yfinance usa uma formula propria que pode ou nao usar diluted shares
- A divisao produz resultado inconsistente com o `sharesOutstanding` real do provider
- Stock splits fazem market_cap e price moverem juntos, mas a divisao pode produzir artefatos intraday
- Dois desenvolvedores poderiam obter resultados diferentes dependendo do momento do snapshot

**Veredito**: Inferencia fragil. Nao e uma serie canonica.

#### Option B: Extrair sharesOutstanding do yfinance (APROVADA — revisada pos-spike)

**Achado do spike S1**: `raw_json` estava `{}` para todos os 175k snapshots. O adapter filtra o dict yfinance a um whitelist (`YahooInfoPayload`) e depois salva `dict(info)` como raw_json — ou seja, raw_json contem apenas campos do whitelist, NAO o payload completo. Backfill via raw_json e IMPOSSIVEL.

**Abordagem revisada — duas fontes yfinance**:

1. **Para snapshots futuros**: adicionar `sharesOutstanding` ao `YahooInfoPayload` + coluna `shares_outstanding` no market_snapshots. Cada novo snapshot ja vem com shares.

2. **Para backfill historico**: usar `yf.Ticker(ticker).quarterly_balance_sheet["Ordinary Shares Number"]` que retorna shares totais por trimestre (historico). Script one-time: para cada primary security, buscar quarterly_balance_sheet e popular shares_outstanding no snapshot mais proximo de cada quarter-end.

3. **Corrigir raw_json**: adapter passa a salvar o dict COMPLETO do yfinance (nao apenas o whitelist) para evitar perda de dados futura.

**Validacao do spike**:
- PETR4: `Ordinary Shares Number` = 12,888,732,761 (total ON+PN), consistente com `impliedSharesOutstanding` de `.info`
- ITSA4: serie trimestral mostra variacao (11.08B → 10.94B → 11.29B) — reflete buybacks e emissoes reais
- O dado e quarterly-anchored, limpo, e reflete share counts contabeis (nao estimativas de mercado)

**Vantagens**:
- Dado canonico do provider (share counts de balance sheet filings)
- Historico disponivel via quarterly_balance_sheet (4-8 quarters tipicamente)
- Consistente com market_cap reportado pelo mesmo provider
- Quarter-aligned naturalmente (sem necessidade de anchoring temporal complexo)

#### Option C: CVM (DMPL / FRE) (REJEITADA para v1)

- DMPL e matricial, parsing complexo
- FRE nao e baixado no pipeline atual
- Escopo incompativel com appetite

### Provider Details

| Aspecto | Valor |
|---------|-------|
| Provider | yfinance (Yahoo Finance) |
| Campo | `sharesOutstanding` do dict `Ticker.info` |
| Tipo | Basic shares outstanding (nao fully diluted) |
| Ajuste de split | Sim — yfinance retorna valor pos-split atual |
| Atualizacao | Reflete ultimo filing da empresa no Yahoo (geralmente quarterly) |
| Historico | NAO disponivel via .info (so current). Snapshots historicos em raw_json dao a serie temporal |
| Persistencia | `market_snapshots.raw_json` (ja salvo). Nova coluna `shares_outstanding` (a criar) |

### Failure Modes

| Falha | Probabilidade | Consequencia | Mitigacao |
|-------|--------------|--------------|-----------|
| sharesOutstanding ausente no raw_json | Baixa (~5% dos tickers) | NBY = NULL para esse issuer | NULL propagation. Cobertura medida em release gate |
| Split entre t-4 e t nao refletido | Muito baixa | NBY distorcido (falso buyback gigante) | Sanity check: se abs(NBY) > 0.50, flag como outlier para revisao manual |
| yfinance muda schema de .info | Baixa | Campo some | Adapter ja e resiliente a campos ausentes (retorna None) |
| Dado desatualizado (quarterly lag) | Media | Shares reflete Q anterior, nao current | Aceitavel — NBY e trailing metric, defasagem de 1Q e toleravel |

### Limitations

- Basic shares, nao fully diluted. Opcoes/warrants nao contabilizados.
- Ponto unico por snapshot — se split ocorre entre snapshots, precisamos de ao menos 1 snapshot pos-split para corrigir.
- Serie temporal depende de frequencia de snapshot refresh. Se snapshots sao infrequentes, janela de 30 dias pode nao ter match para t-4.

### Decision Record

**Decisao**: Option B — extrair `sharesOutstanding` de yfinance raw_json/info.
**Data**: 2026-03-15.
**Racional**: Dado canonico do provider, disponivel retroativamente, sem inferencia fragil.
**Revisao planejada**: Quando CVM DMPL for parseado (futuro), comparar serie yfinance vs serie contabil.

---

## 8. Requirements (atualizado)

### R1: Extrair dividendos e JCP de DFC (CVM)

Mapear sub-contas DFC nivel 2+ para canonical key `shareholder_distributions`.

**Decisao de design**: Usar UMA canonical key (`shareholder_distributions`) em vez de separar `dividends_paid` e `jcp_paid`.

**Justificativa**: CVM nao padroniza separacao entre dividendos e JCP nos sub-accounts de DFC. Muitas empresas reportam "Dividendos e JCP pagos" como linha unica. Separar artificialmente criaria dados falsos. Para NPY, o relevante e o TOTAL distribuido, nao a composicao.

**Estrategia de mapeamento**: Label-based matching em `as_reported_label` para linhas com `as_reported_code LIKE '6.03.%'`.

Patterns a mapear (case-insensitive):
```
dividendo
jcp
juros sobre capital
proventos pagos
distribuicao de lucros
remuneracao aos acionistas
```

Sub-contas que NAO sao distribuicoes (exclusao):
```
emprestimos
financiamentos
debentures
aquisicao
captacao
pagamento de principal
```

### R2: Extrair e persistir shares outstanding

- Adicionar `shares_outstanding` ao `YahooInfoPayload` e a tabela `market_snapshots`
- Backfill de raw_json existente
- Alembic migration para nova coluna

### R3: Computar Dividend Yield TTM

Conforme Operational Metric Spec (secao 6.2 e 6.4).

### R4: Computar Net Buyback Yield

Conforme Operational Metric Spec (secao 6.3 e 6.5).

### R5: Computar Net Payout Yield

Conforme Operational Metric Spec (secao 6.1).

### R6: Atualizar compat view

Adicionar `dividend_yield`, `net_buyback_yield`, `net_payout_yield` ao v_financial_statements_compat.

---

## 9. Candidate Shapes (revisado)

### Shape A': CVM DFC + yfinance sharesOutstanding (SELECIONADA)

Evolucao do Shape A original. Muda a fonte de shares de "derivado de market_cap/price" para "extraido diretamente do yfinance".

- Dividendos/JCP: extrair de DFC sub-contas via label matching -> canonical key `shareholder_distributions`
- Shares: extrair `sharesOutstanding` de yfinance (raw_json existente + adapter update)
- TTM: funcao isolada com quarter extraction (YTD subtraction)
- NPY: nova IndicatorStrategy que combina intermediarios

**Pros**: Fonte primaria (CVM) para payout + dado canonico (yfinance) para shares. Sem inferencia fragil.
**Cons**: DFC sub-contas variam por empresa. sharesOutstanding e basic (nao diluted).

### Shapes B e C (REJEITADAS)

Motivos no ADR (secao 7).

---

## 10. Appetite

- **Level**: Medium — 5 build scopes (S6 ranking removido do must-fit)
- **Why this appetite is enough**: Dados CVM e yfinance ja disponiveis. MetricsEngine tem pattern estabelecido. Trabalho novo: label mapping DFC + shares extraction + TTM engine + 3 metricas.
- **Must-fit items**: S1 (DFC mapping + shares column), S2 (TTM engine + DY), S3 (NBY), S4 (NPY), S5 (compat view + validation)
- **First cuts if exceeded**: S5 (compat view) pode ser adiado. Metricas em computed_metrics ja sao consumiveis sem view.
- **Blocked items**: S6 (ranking integration). Requer coverage gate + strategy spec. Sera Plan 3B.

---

## 11. Boundaries / No-Gos / Out of Scope

### Boundaries

- Tocar: canonical_mapper, entities.py (enums), metrics/ (novas strategies), yahoo adapter (shares field), market_snapshots schema, compat view migration, Drizzle schema sync
- Payout data: exclusivamente de DFC (Cash Flow Statement) da CVM
- Shares data: exclusivamente de yfinance `sharesOutstanding` (raw_json + adapter)

### No-Gos

- NAO parsear DMPL (formato matricial — escopo proprio)
- NAO baixar FRE
- NAO modificar parser DFP/ITR existente — apenas estender canonical_mapper
- NAO alterar estrategias existentes (magic_formula_*)
- NAO criar UI/dashboard para NPY nesta fase
- NAO integrar NPY no ranking (Plan 3B)
- NAO derivar shares de market_cap/price
- NAO separar dividends_paid vs jcp_paid (ver R1)

### Out of Scope

- Ranking integration (greenblatt_npy) — Plan 3B
- Shareholder Yield Score (com debt paydown)
- Qualidade de buyback (accretive vs dilutive)
- Backtest com NPY
- Fully diluted shares
- API endpoints especificos para NPY

---

## 12. Rabbit Holes / Hidden Risks (revisado)

### RH1: DFC sub-contas nao padronizadas (ALTO)

CVM nao padroniza CD_CONTA nivel 2/3 entre empresas. "Dividendos pagos" pode ser 6.03.01, 6.03.02, 6.03.04, etc. Labels variam: "Dividendos pagos", "Dividendos e JCP pagos", etc. ~804 variantes de label so para 6.03.01.

**Mitigacao**:
- Label-based matching com patterns inclusivos + exclusao de nao-dividendos
- Spike query contra DB real para validar cobertura antes de commitar mapeamento
- Aceitar que cobertura sera parcial no spike; release gate e separado
- Log warnings para linhas 6.03.XX nao mapeadas (auditabilidade)

**Spike done criteria**: Patterns capturam distribuicoes para >30 issuers
**Release gate**: Cobertura >= 70% do universo elegivel do ranking Brazil

### RH2: TTM requer quarter extraction de YTD acumulado (ALTO — upgrade de MEDIO)

ITR armazena valores YTD acumulados, NAO standalone trimestral. Subtracao errada causa double-counting catastrofico. DFP anual e ITR Q4 podem coexistir para mesma ref_date.

**Mitigacao**:
- Funcao `extract_quarterly_standalone()` isolada com regras explicitas (secao 6.4)
- DFP prevalece sobre ITR Q4 para mesmo ref_date
- Q1 standalone = Q1 YTD (caso especial, sem subtracao)
- Teste obrigatorio com fixture de 4 quarters reais
- Sanity check: standalone negativo nao e impossivel (estorno), mas flag se abs(standalone) > 2x do YTD/4

**Spike done criteria**: TTM computado corretamente para 5 issuers verificados manualmente
**Release gate**: TTM nao produz valores absurdos (standalone > YTD) para nenhum issuer

### RH3: sharesOutstanding — disponibilidade e consistencia temporal (MEDIO — downgrade de ALTO)

Risco original era ALTO (derivar shares de market_cap/price). Com sharesOutstanding direto do yfinance, risco cai. Mas permanece:
- Campo pode estar ausente para alguns tickers (~5%)
- Valor reflete ultimo filing no Yahoo (lag de ate 1 quarter)
- Stock splits: yfinance reporta valor pos-split, mas snapshots historicos em raw_json podem ter valor pre-split se foram salvos antes do split

**Mitigacao**:
- NULL propagation se sharesOutstanding ausente
- Sanity check: se abs(NBY) > 0.50, marcar como outlier
- Backfill de raw_json preserva dado original do momento do snapshot (correto para comparacao temporal)
- Validacao cruzada: shares(t) * price(t) deve ser ~market_cap(t) (tolerancia 10%)

### RH4: Empresas sem DFC detalhado (BAIXO)

Algumas empresas menores reportam DFC apenas nivel 1.

**Mitigacao**: DY = NULL. Aceitavel.

### RH5: Sinal de dividendos no DFC (MEDIO)

Dividendos pagos no DFC sao NEGATIVOS. `abs()` aplicado na strategy.

**Mitigacao**: Sign handling explicito na strategy. inputs_snapshot preserva valor original. Test case com valor negativo obrigatorio.

### RH6: Escopo misturado entre quarters (NOVO — MEDIO)

Se issuer tem Q1-Q2 consolidado e Q3-Q4 individual (ou vice-versa), TTM mistura escopos.

**Mitigacao**: TODOS os 4 quarters devem ter MESMO escopo. Se escopo muda, TTM = NULL.

---

## 13. Breadboard Summary

### Places

```
[CVM DFC Sub-contas]  ->  [Label Matcher]  ->  [statement_lines.canonical_key = 'shareholder_distributions']
                                                         |
[Yahoo raw_json] -> [Adapter Update] -> [market_snapshots.shares_outstanding]
                                                         |
                                            [TTM Quarter Extractor]
                                                         |
                                            [DividendYieldStrategy]
                                            [NetBuybackYieldStrategy]
                                            [NetPayoutYieldStrategy]
                                                         |
                                               [computed_metrics]
                                                         |
                                          [v_financial_statements_compat]
```

### Code Affordances (NEW)

| Affordance | Location | Type |
|------------|----------|------|
| `CanonicalKey.shareholder_distributions` | entities.py | Enum value |
| `MetricCode.dividend_yield` | entities.py | Enum value |
| `MetricCode.net_buyback_yield` | entities.py | Enum value |
| `MetricCode.net_payout_yield` | entities.py | Enum value |
| `DFC_DISTRIBUTION_PATTERNS` | canonical_mapper.py | List of include/exclude label patterns |
| `shares_outstanding` column | market_snapshots table | NUMERIC, nullable |
| `YahooInfoPayload.sharesOutstanding` | providers/base.py | TypedDict field |
| `extract_quarterly_standalone()` | metrics/ttm.py | Pure function |
| `compute_ttm_sum()` | metrics/ttm.py | Pure function |
| `DividendYieldStrategy` | metrics/dividend_yield.py | IndicatorStrategy subclass |
| `NetBuybackYieldStrategy` | metrics/net_buyback_yield.py | IndicatorStrategy subclass |
| `NetPayoutYieldStrategy` | metrics/net_payout_yield.py | IndicatorStrategy subclass |

### Wiring Changes vs CURRENT

1. **canonical_mapper.py**: Adicionar label-based matching para DFC 6.03.XX -> `shareholder_distributions`
2. **entities.py**: Adicionar 1 CanonicalKey + 3 MetricCode
3. **providers/base.py + yahoo/adapter.py**: Adicionar sharesOutstanding ao whitelist
4. **market_snapshots**: Nova coluna shares_outstanding + backfill migration
5. **MetricsEngine**: Registrar 3 novas strategies. Diferem das atuais por exigirem TTM + market data
6. **compat view**: DROP + CREATE com 3 colunas adicionais
7. **Drizzle schema**: Sync enums + market_snapshots column

---

## 14. Build Scopes

### Done Criteria: Spike vs Release (Gate 3)

Cada scope tem dois niveis de acceptance:

| Nivel | Significado | Quando |
|-------|-------------|--------|
| **Spike done** | Prova tecnica de viabilidade. Cobertura parcial aceitavel. | Fim do scope |
| **Release done** | Cobertura e qualidade suficientes para uso em producao. | Fim do Plan 3A |

**Release gate final (Plan 3A)**: Todas as condicoes abaixo devem ser verdadeiras:
- `dividend_yield` nao-NULL para >= 70% do universo elegivel do ranking Brazil (~300 issuers)
- `net_buyback_yield` nao-NULL para >= 80% do universo com market_snapshots
- `net_payout_yield` nao-NULL para >= 60% do universo elegivel
- Zero issuers com standalone > YTD (double-counting)
- Zero issuers com abs(NBY) > 0.50 nao investigados
- Distribuicao por setor documentada (cobertura nao pode ter setor inteiro missing)
- 10 issuers auditados manualmente com reconciliacao contra dados publicos

---

### S1: DFC Mapping + Shares Column + Canonical Keys

**Objective**: Mapear distribuicoes em DFC, adicionar shares_outstanding ao market_snapshots, criar canonical keys.

**Sub-tasks**:
1. Spike query: `SELECT as_reported_code, as_reported_label, count(*) FROM statement_lines WHERE statement_type IN ('DFC_MD','DFC_MI') AND as_reported_code LIKE '6.03.%' GROUP BY 1,2 ORDER BY 3 DESC` — catalogar padroes
2. Definir `DFC_DISTRIBUTION_PATTERNS` (include + exclude)
3. Adicionar `CanonicalKey.shareholder_distributions` ao enum
4. Implementar label matcher no canonical_mapper (nova funcao, nao modifica mapeamento por CD_CONTA existente)
5. Re-normalizar statement_lines existentes para aplicar novo mapping (script one-off)
6. Alembic migration: `ALTER TABLE market_snapshots ADD COLUMN shares_outstanding NUMERIC`
7. Backfill script: extrair sharesOutstanding de raw_json para snapshots existentes
8. Atualizar `YahooInfoPayload` e adapter para persistir shares_outstanding em novos snapshots
9. Sync Drizzle schema

**Files touched**:
- `packages/shared-models-py/src/q3_shared_models/entities.py` (CanonicalKey enum)
- `services/fundamentals-engine/src/q3_fundamentals_engine/normalization/canonical_mapper.py`
- `services/fundamentals-engine/src/q3_fundamentals_engine/providers/base.py` (YahooInfoPayload)
- `services/fundamentals-engine/src/q3_fundamentals_engine/providers/yahoo/adapter.py`
- `services/quant-engine/alembic/versions/` (migration)
- `apps/api/src/db/schema.ts` (Drizzle sync)

**Dependencies**: Nenhuma
**Risk focus**: RH1 (label patterns), RH3 (shares availability)
**Review focus**: Cobertura do label matching, false positives/negatives, backfill correctness

**Spike done**: canonical_key='shareholder_distributions' presente para >30 issuers. shares_outstanding preenchido para >80% dos snapshots existentes.
**Release done**: Cobertura de shareholder_distributions por setor documentada. shares_outstanding backfill completo.

**Validation hook**:
```sql
-- Distribuicoes mapeadas
SELECT count(DISTINCT sl.filing_id)
FROM statement_lines sl
JOIN filings f ON f.id = sl.filing_id
WHERE sl.canonical_key = 'shareholder_distributions';

-- Shares backfill
SELECT count(*) FILTER (WHERE shares_outstanding IS NOT NULL) * 100.0 / count(*)
FROM market_snapshots;
```

---

### S2: TTM Engine + Dividend Yield Metric

**Objective**: Implementar quarter extraction (YTD -> standalone) e DividendYieldStrategy.

**Sub-tasks**:
1. Criar `metrics/ttm.py` com:
   - `extract_quarterly_standalone(issuer_id, canonical_key, quarters: list[date], session) -> dict[date, float | None]`
   - `compute_ttm_sum(standalones: dict[date, float | None]) -> float | None`
2. Implementar regras de secao 6.4 (DFP > ITR Q4, scope consistency, completeness)
3. Criar `metrics/dividend_yield.py` — DividendYieldStrategy
4. Registrar no MetricsEngine
5. Adicionar `MetricCode.dividend_yield` ao enum
6. Testes unitarios para TTM (fixtures com cenarios: normal, faltando Q, DFP+ITR overlap, scope mismatch)
7. Testes de integracao para DividendYieldStrategy

**Files touched**:
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/ttm.py` (NOVO)
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/dividend_yield.py` (NOVO)
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/engine.py`
- `packages/shared-models-py/src/q3_shared_models/entities.py` (MetricCode)
- `services/fundamentals-engine/tests/`

**Dependencies**: S1
**Risk focus**: RH2 (TTM double-counting), RH5 (sinal), RH6 (escopo mismatch)
**Review focus**: Quarter extraction logic, edge cases, sign handling

**Spike done**: DY computado para 5 issuers, verificado manualmente contra dados publicos (Status Invest, Fundamentus).
**Release done**: DY nao-NULL para >=70% do universo. Nenhum DY > 0.30 (30%) sem investigacao. Nenhum standalone > YTD.

**Validation hook**:
```sql
-- Sanity check
SELECT metric_code, count(*),
       avg(value::float), min(value::float), max(value::float),
       percentile_cont(0.95) WITHIN GROUP (ORDER BY value::float)
FROM computed_metrics
WHERE metric_code = 'dividend_yield'
GROUP BY 1;
```

---

### S3: Net Buyback Yield Metric

**Objective**: Implementar NetBuybackYieldStrategy usando shares_outstanding de market_snapshots.

**Sub-tasks**:
1. Criar `metrics/net_buyback_yield.py` — NetBuybackYieldStrategy
2. Implementar snapshot matching (secao 6.5 — quarter-end anchored, +/- 30 dias)
3. Implementar sanity check: abs(NBY) > 0.50 -> flag outlier
4. Registrar no MetricsEngine
5. Adicionar `MetricCode.net_buyback_yield`
6. Testes: normal buyback, normal dilution, split scenario, missing snapshot, NULL propagation

**Files touched**:
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/net_buyback_yield.py` (NOVO)
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/engine.py`
- `packages/shared-models-py/src/q3_shared_models/entities.py`
- `services/fundamentals-engine/tests/`

**Dependencies**: S1 (shares_outstanding column)
**Risk focus**: RH3 (shares consistency), snapshot temporal alignment
**Review focus**: Snapshot matching query, outlier detection, NULL handling

**Spike done**: NBY computado para >30 issuers. Valores entre -0.15 e +0.15 para 90%. Outliers investigados.
**Release done**: NBY nao-NULL para >=80% do universo com snapshots. Cross-check: shares(t) * price(t) ~= market_cap(t) (+/- 10%) para 95% dos issuers. Zero outliers abs(NBY) > 0.50 nao investigados.

**Validation hook**:
```sql
-- Cross-check shares vs market_cap
SELECT s.ticker,
       ms.shares_outstanding * ms.price AS implied_mcap,
       ms.market_cap,
       abs(ms.shares_outstanding * ms.price - ms.market_cap) / ms.market_cap AS pct_diff
FROM market_snapshots ms
JOIN securities s ON s.id = ms.security_id
WHERE ms.shares_outstanding IS NOT NULL AND ms.market_cap > 0
ORDER BY pct_diff DESC
LIMIT 20;
```

---

### S4: Net Payout Yield Metric

**Objective**: Combinar DY + NBY em NPY.

**Sub-tasks**:
1. Criar `metrics/net_payout_yield.py` — NetPayoutYieldStrategy
2. Buscar DY e NBY de computed_metrics (nao recomputar)
3. NPY = DY + NBY. NULL se qualquer componente NULL.
4. inputs_snapshot documenta: `{dividend_yield: X, net_buyback_yield: Y, source_dy_id: ..., source_nby_id: ...}`
5. Registrar no MetricsEngine (deve rodar APOS DY e NBY)
6. Testes: composicao normal, NULL propagation, NPY negativo (diluicao > payout)

**Files touched**:
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/net_payout_yield.py` (NOVO)
- `services/fundamentals-engine/src/q3_fundamentals_engine/metrics/engine.py`
- `packages/shared-models-py/src/q3_shared_models/entities.py`
- `services/fundamentals-engine/tests/`

**Dependencies**: S2, S3
**Risk focus**: Ordering de strategies no engine (NPY apos DY e NBY)
**Review focus**: Composicao, NULL propagation, inputs_snapshot completo

**Spike done**: NPY computado. NPY = DY + NBY para 100% dos issuers (tolerancia 1e-9).
**Release done**: NPY nao-NULL para >=60% do universo elegivel. Identidade NPY = DY + NBY verificada para 100%.

---

### S5: Compat View + Validation Report

**Objective**: Atualizar view, produzir validation report final.

**Sub-tasks**:
1. Alembic migration: DROP + CREATE v_financial_statements_compat com 3 colunas NPY
2. Drizzle schema sync
3. Gerar validation report com:
   - Cobertura total e por setor (dividend_yield, net_buyback_yield, net_payout_yield)
   - Taxa de NULL por setor
   - Distribuicao estatistica (mean, median, p5, p25, p75, p95) por metrica
   - Top/bottom 20 outliers por metrica
   - 10 issuers auditados manualmente (DY comparado com Status Invest / Fundamentus)
   - Cross-check NPY = DY + NBY (100%)
   - Reconciliacao shares * price ~= market_cap

**Files touched**:
- `services/quant-engine/alembic/versions/YYYYMMDD_XXXX_add_npy_to_compat.py` (NOVO)
- `apps/api/src/db/schema.ts`
- `docs/plan3-net-payout-yield/validation-report.md` (NOVO)

**Dependencies**: S4
**Risk focus**: DROP MATERIALIZED VIEW em producao
**Review focus**: Migration reversibility, validation completeness

**Spike done**: N/A (este scope e release-only)
**Release done**: Validation report completo. Todos os release gates (secao 14) passando. View funcional.

---

## 15. greenblatt_npy Strategy Spec (Gate 4) — BLOCKED

**Status**: Removido do must-fit de Plan 3A. Sera Plan 3B.

**Pre-requisitos para desbloquear**:
1. Plan 3A release gates cumpridos (cobertura, qualidade)
2. Analise de impacto: quantos issuers do ranking Brazil atual teriam NPY NULL (seriam excluidos)
3. Decisao de formula fechada

**Decisoes pendentes para Plan 3B** (registradas, nao resolvidas):

| Decisao | Opcoes | Impacto |
|---------|--------|---------|
| Metodo de combinacao | Rank-sum (como magic_formula) vs weighted percentile (como hybrid) | Determina se NPY e pilar simetrico ou overlay |
| Peso de NPY | 1/3 cada (EY, ROC, NPY) vs EY+ROC dominante com NPY como bonus | Muda dramaticamente o ranking |
| Tratamento de NPY negativo | Incluir no rank normalmente vs winsorizar em 0 vs excluir | Afeta empresas diluindo |
| Filtro hard de NPY | Exigir NPY >= 0 vs aceitar qualquer valor | Reduz universo |
| Winsorization | Aplicar em p5/p95 antes de rankear vs rankear raw | Controla influencia de outliers |
| Universo elegivel | Mesmo filtro do magic_formula_brazil + NPY nao-NULL | Define comparabilidade |

**Estas decisoes serao tomadas com base nos dados reais de Plan 3A.**

---

## 16. Validation Plan (revisado)

### Per-scope validation

Cada scope tem spike done + release done criteria proprios (ver secao 14).

### Release gates (Plan 3A)

| Gate | Criterio | Threshold |
|------|----------|-----------|
| G1 | Coverage DY | >= 70% do universo elegivel |
| G2 | Coverage NBY | >= 80% do universo com snapshots |
| G3 | Coverage NPY | >= 60% do universo elegivel |
| G4 | Identidade | NPY = DY + NBY para 100% (tol 1e-9) |
| G5 | No double-counting | Zero issuers com standalone > YTD |
| G6 | Outliers investigated | Zero abs(NBY) > 0.50 sem investigacao |
| G7 | Sector coverage | Nenhum setor inteiro sem cobertura |
| G8 | Manual audit | 10 issuers reconciliados contra dados publicos |
| G9 | Statistical distribution | Documented per metric (mean, p5-p95) |
| G10 | Shares cross-check | shares * price ~= market_cap (+/-10%) para 95% |

### Validacao estatistica (alem de consistencia interna)

1. **Distribuicao por setor**: tabela com coverage rate + stats por setor CVM
2. **Taxa de NULL por setor**: identificar setores problematicos
3. **Outlier inspection**: top/bottom 20 por metrica com explicacao
4. **Manual audit sample**: 10 issuers diversificados (2 bancos, 2 utilities, 2 commodities, 2 varejo, 2 tech/saude):
   - DY calculado vs DY em Status Invest / Fundamentus (tolerancia 20% relativo)
   - NBY: verificar se empresa de fato fez buyback/emissao no periodo
   - NPY: verificar coerencia com politica de payout conhecida
5. **Reconciliacao de DY contra referencia publica**: quando DY difere >20% de Status Invest, investigar e documentar causa (JCP inclusion, TTM window, data lag)

### Regressao

- Testes existentes de magic_formula_original, _brazil, _hybrid devem continuar passando
- computed_metrics existentes (12 metricas) nao devem ser alteradas
- Compat view deve manter todas as colunas anteriores

---

## 17. Current Status

- [x] Phase 0: Intake / Micro-feature framing
- [x] Phase 1: Map current system
- [x] Phase 2: Shape (v2 — Tech Lead gates addressed)
- [x] Phase 3: Set appetite
- [x] Phase 4: Boundaries / no-gos / out of scope
- [x] Phase 5: Rabbit holes / hidden risks
- [x] Phase 6: Breadboard
- [x] Phase 7: Slice into build scopes
- [x] Phase 8: Build (S1-S5 complete)
- [x] Phase 9: Validate (per-scope + final)
- [x] Phase 10: Close
- [x] Phase 11: Tech Lead handoff

**Final status**: Build APPROVED. Release BLOCKED (coverage gates not met).

---

## 18. Close Summary

### Delivered scope

All 6 build scopes completed and Tech Lead approved:

| Scope | Status | Key outcome |
|-------|--------|-------------|
| S1 | Done | DFC mapping (552 issuers), shares_outstanding column, canonical keys |
| S2 | Done | TTM engine, Dividend Yield metric (178 issuers) |
| S3 | Done | Net Buyback Yield metric (259 issuers), snapshot anchoring |
| S3.5 | Done | Data remediation (market_cap, shares backfill, propagation) |
| S4 | Done | Net Payout Yield = DY + NBY, pure composition (176 issuers) |
| S5 | Done | Compat view with 3 new columns, migration, validation report |

### Explicit cuts and deferrals

- **S6 (ranking integration)**: Deferred to Plan 3B. Blocked by coverage gates.
- **Plan 3A release**: Blocked. Coverage (DY 24.1%, NBY 35.0%, NPY 23.8%) well below release thresholds (70%, 80%, 60%).
- **Plan 3C proposed**: Research-grade data infrastructure (entity master, point-in-time panel, source tiers).

### Known limitations

1. 245 distribution issuers lack `securities` table entry (CVM-only, no market linkage)
2. 355 issuers have multiple `is_primary=true` securities (ON+PN dual-class inflation)
3. Historical shares data sparse for Q2 2024 (annual balance sheet doesn't align)
4. 13 NBY outliers (abs > 0.50) — all investigated, all plausible (restructuring/recovery)
5. SYNE3 DY=89.8% — special dividend, plausible but extreme

### Open follow-ups

1. **Plan 3B**: Ranking integration (greenblatt_npy) — blocked until coverage sufficient
2. **Plan 3C**: Data infrastructure (entity master, point-in-time panel, source tiers, reproducibility)
3. **is_primary deduplication**: Resolve 355 issuers with multiple primary securities
4. **Securitizacao sector**: 0% NPY coverage — structural (SPVs), not a bug

### Final validation status

| Gate | Threshold | Result | Status |
|------|-----------|--------|--------|
| G4: Identity | NPY=DY+NBY 100% | 100% (max diff 4.3e-15) | PASS |
| G5: No double-counting | 0 violations | 0 | PASS |
| G6: Outliers investigated | all reviewed | 13 reviewed | PASS |
| G1: Coverage DY | >= 70% | 24.1% | FAIL |
| G2: Coverage NBY | >= 80% | 35.0% | FAIL |
| G3: Coverage NPY | >= 60% | 23.8% | FAIL |

### Final feature status

**Build: DONE. Release: BLOCKED by data coverage.**

### Follow-up decision

Follow-up required as new plan: **Plan 3C — NPY Research Dataset & Coverage Infrastructure**.

---

## 19. Tech Lead Handoff

### Micro feature summary

NPY (Net Payout Yield) = Dividend Yield TTM + Net Buyback Yield, implemented as foundation metric in Q3. Captures total shareholder return including buybacks and dilution.

### Selected shape and rationale

CVM DFC for distributions + yfinance sharesOutstanding for shares. TTM as separate compute path (not IndicatorStrategy). NPY as pure composition. Chosen because CVM is source of truth for payout data and yfinance provides canonical share counts without fragile derivation.

### Appetite used

Medium — 5 build scopes (S6 ranking deferred). Actual execution: 6 scopes (S3.5 remediation added mid-flight to unblock zero coverage).

### What changed

| Area | Change |
|------|--------|
| `entities.py` | +1 CanonicalKey, +3 MetricCode |
| `canonical_mapper.py` | DFC label-based matching for shareholder_distributions |
| `metrics/ttm.py` | NEW — TTM quarter extraction engine |
| `metrics/dividend_yield.py` | NEW — DY = abs(TTM distributions) / market_cap |
| `metrics/net_buyback_yield.py` | NEW — NBY = (shares_t4 - shares_t) / shares_t4 |
| `metrics/net_payout_yield.py` | NEW — NPY = DY + NBY (pure composition) |
| `metrics/snapshot_anchor.py` | NEW — reusable snapshot temporal anchoring |
| `metrics/engine.py` | TTM metrics section after single-period strategies |
| `market_snapshots` | shares_outstanding column (Alembic migration) |
| `v_financial_statements_compat` | +3 columns (DY, NBY, NPY) |
| `providers/yahoo/adapter.py` | sharesOutstanding extraction |

### Rabbit holes and residual risks

1. **Entity master**: 245 issuers without securities linkage — primary coverage ceiling
2. **is_primary duplication**: 355 issuers with multiple primaries inflate compat view
3. **Shares temporal coverage**: Q2 2024 low (35 issuers) — annual balance sheet gap
4. **Derived data provenance**: Remediated market_cap/shares are marked but mixed with provider-native data

### Test coverage

184 tests passing, 0 regressions. Tests cover: TTM extraction (22), DY (8), NBY (15), NPY (11), plus all existing tests.

### Where to focus review

1. `metrics/ttm.py` — most complex logic (YTD deaccumulation, scope consistency, DFP>ITR priority)
2. `metrics/snapshot_anchor.py` — temporal anchoring correctness
3. Migration `20260320_0016` — compat view safety

### Residual risk hotspots

- TTM deaccumulation for edge cases (non-standard fiscal years)
- Shares propagation quality for historical periods
- is_primary multi-selection inflating downstream counts

### Questions requiring Tech Lead attention

1. Plan 3C scope and priority
2. is_primary deduplication strategy (most liquid class? volume-based?)
3. Whether to pursue CVM FRE for official share structure data
4. Source tier framework design
