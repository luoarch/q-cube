# Architecture.md — Q3 (Q-Cube)

## 1. Objetivo

Q3 e uma plataforma de pesquisa quantitativa para o mercado brasileiro (B3). A arquitetura prioriza:

- Separacao clara entre produto (web/API) e engines quantitativos (Python)
- Processamento assincrono para calculos pesados (Celery/Redis)
- Contratos tipados fim a fim (SSOT via Zod + SQLAlchemy)
- Reprodutibilidade de resultados (formula_version + inputs_snapshot)

## 2. Diagrama — 7 processos PM2

```text
[q3-web]                    Next.js :3000 (scaffold)
    |
    | HTTPS (REST)
    v
[q3-api]                    NestJS :4000 (Drizzle ORM)
    |
    | enqueue jobs
    v
[Redis]                     Broker + cache
    |
    +---> [q3-quant-worker]             Celery (queue: strategy)
    |         uses quant-engine code
    |
    +---> [q3-fundamentals-worker]      Celery (queue: fundamentals)
              uses fundamentals-engine code

[q3-quant-engine]           FastAPI :8100 (admin/status)
[q3-market-ingestion]       FastAPI :8200 (data client adapters)
[q3-fundamentals-engine]    FastAPI :8300 (CVM pipeline + market snapshots)
    |
    v
[PostgreSQL]                17 tabelas + 1 materialized view
```

Configuracao PM2: `ecosystem.config.cjs`

## 3. Componentes

### 3.1 `apps/web` — Next.js 16 (scaffold)

Status: scaffold apenas. Auth UI + dashboard vazio, sem funcionalidade real de produto.

- App Router
- Server Components

### 3.2 `apps/api` — NestJS 11 (Drizzle ORM)

Responsabilidades implementadas:

- Strategy run CRUD + job enqueue via Redis
- Tenant guard (header `x-tenant-id`)
- Zod validation filter
- Health check

Modulos ativos: `strategy`, `health`, `database`, `redis`.

### 3.3 `services/quant-engine` — FastAPI + Celery

Responsabilidades:

- Executar estrategias quantitativas (3 tipos: Magic Formula Original, Brasil, Hybrid)
- Ranking pipeline (`strategies/ranking.py`)
- Consumir `v_financial_statements_compat` view para dados

Stack: FastAPI, Celery (queue: `strategy`), SQLAlchemy 2.x, Alembic (todas as migrations).

> **Dependencia critica:** Magic Formula Original requer `market_cap` de market snapshots para calcular Enterprise Value e Earnings Yield. Sem `ENABLE_BRAPI=true`, EV/EY ficam NULL e o ranking usa EBIT margin + ROIC como fallback.

### 3.4 `services/fundamentals-engine` — FastAPI + Celery

Pipeline CVM-first de dados fundamentalistas:

1. Download ZIPs da CVM (DFP/ITR/FCA) com SHA-256 dedup
2. Parse (DfpParser, ItrParser, FcaParser) com version dedup
3. Normalizacao (canonical mapper, sign normalizer, scope resolver)
4. Resolucao de emissores/tickers (FCA -> Cadastro -> Manual)
5. Deteccao de restatements + invalidacao de metricas
6. Calculo de metricas derivadas (ROIC, EBITDA, margins, net_debt)
7. Market snapshots (brapi.dev) -> EV, earnings_yield (quando `ENABLE_BRAPI=true`)

Stack: FastAPI, Celery (queue: `fundamentals`), SQLAlchemy 2.x.

Doc detalhada: `docs/fundamentals-engine.md`

### 3.5 `services/market-ingestion` — FastAPI

Data client adapters para fontes externas:

- `clients/brapi.py` — brapi.dev quotes
- `clients/cvm.py` — CVM dados.gov.br
- `clients/dadosdemercado.py` — Dados de Mercado API

Ingest handlers: `handlers/ingest.py`

### 3.6 Shared packages

| Package | Tecnologia | Escopo |
|---------|-----------|--------|
| `shared-contracts` | Zod 4 | SSOT para API payloads (strategy, jobs, events) |
| `shared-fundamentals` | TypeScript | Canonical keys, metric codes, domain enums |
| `shared-models-py` | SQLAlchemy 2.x | SSOT para todas as tabelas Python |
| `shared-types` | TypeScript | Re-export de tipos de shared-contracts |
| `shared-events` | TypeScript | Event schemas |

## 4. Fluxos

### 4.1 Strategy run

```text
User -> Web -> API POST /strategy-runs
API valida contrato + tenant guard
API cria StrategyRun + Job (pending) via Drizzle
API publica strategyRunQueuedEvent no Redis (q3:strategy:jobs)
Celery worker (q3-quant-worker) consome job
Worker executa ranking pipeline
Worker persiste resultados + atualiza status (completed/failed)
API/Web consultam status e exibem output
```

### 4.2 CVM import

```text
POST /batches/cvm/2024 -> fundamentals-engine
Cria raw_source_batches (pending)
Enqueue import_cvm_batch no Redis
Worker: download -> parse -> normalize -> resolve issuers -> detect restatements -> compute metrics -> refresh compat view
```

### 4.3 Market snapshots

```text
POST /batches/snapshots/refresh -> fundamentals-engine
Enqueue fetch_market_snapshots no Redis
Worker: fetch brapi quotes -> persist market_snapshots -> chain compute_market_metrics
compute_market_metrics: EV + earnings_yield para issuers com snapshot fresco (< 7 dias) -> refresh compat view
```

## 5. Data model — 17 tabelas + 1 view

### Tenant-scoped (infra)

| Tabela | Descricao |
|--------|-----------|
| `tenants` | Organizacao multi-tenant |
| `users` | Usuarios do sistema |
| `memberships` | Relacao tenant-user com role |

### Tenant-scoped (domain)

| Tabela | Descricao |
|--------|-----------|
| `assets` | Ativo financeiro (ticker, legacy) |
| `financial_statements` | Demonstracao financeira (legacy, flat columns) |
| `strategy_runs` | Execucao de estrategia quantitativa |
| `backtest_runs` | Execucao de backtest (schema pronto, nao implementado) |
| `jobs` | Job assincrono (strategy_run, backtest_run) |

### Fundamentals — Raw Layer (sem tenant)

| Tabela | Descricao |
|--------|-----------|
| `raw_source_batches` | Batch de download (source, year, doc_type, status) |
| `raw_source_files` | Arquivo baixado (filename, sha256, size_bytes) |

### Fundamentals — Normalized Layer (sem tenant)

| Tabela | Descricao |
|--------|-----------|
| `issuers` | Emissor CVM (cvm_code, cnpj, sector) |
| `securities` | Ticker de um emissor (issuer_id, ticker, is_primary) |
| `filings` | Demonstracao financeira (issuer_id, filing_type, reference_date, version) |
| `statement_lines` | Linha contabil normalizada (canonical_key, normalized_value, scope) |

### Fundamentals — Derived Layer (sem tenant)

| Tabela | Descricao |
|--------|-----------|
| `computed_metrics` | Indicador derivado (metric_code, value, formula_version, inputs_snapshot) |
| `restatement_events` | Retificacao detectada (original_filing_id, new_filing_id) |

### Market Layer (sem tenant)

| Tabela | Descricao |
|--------|-----------|
| `market_snapshots` | Quote point-in-time (security_id, price, market_cap, volume, fetched_at) |

### Views

| View | Descricao |
|------|-----------|
| `v_financial_statements_compat` | Materialized view — projeta dados canonicos + market snapshots em colunas compativeis com modelo legado |

## 6. SSOT — 4 camadas

```text
1. shared-contracts (Zod 4)     → API payloads, domain types
2. shared-fundamentals (TS)     → Canonical keys, metric codes, enums
3. shared-models-py (SQLAlchemy) → Tabelas, SSOT para Python services
4. apps/api/src/db/schema.ts    → Mirror Drizzle (manual, sem geracao automatica nem CI check)
```

Regra: mudanca de payload comeca em `shared-contracts`. Mudanca de tabela comeca em `shared-models-py` + migration Alembic.

## 7. Multi-tenant

Schema suporta isolamento multi-tenant:

- UUID PKs em todas as tabelas
- `tenant_id` com cascade delete de `tenants`
- Roles: owner, admin, member, viewer

**Status atual:** schema pronto, nao enforced na pratica. Tenant guard existe no API (`x-tenant-id` header) mas nao ha validacao real de autenticacao/autorizacao.

## 8. Processamento assincrono

| Queue | Worker | Tasks |
|-------|--------|-------|
| `strategy` | q3-quant-worker | `execute_strategy_run` |
| `fundamentals` | q3-fundamentals-worker | `import_cvm_batch`, `compute_metrics_for_issuer`, `fetch_market_snapshots`, `compute_market_metrics` |

Estados de execucao: `pending` -> `running` -> `completed` | `failed`

Broker: Redis 8.x. Celery 5.6.x com prefork pool.

## 9. Observabilidade

**Estado atual:** apenas logs estruturados via `logging` module (Python) e NestJS logger (TypeScript).

Nao implementado:
- Tracing distribuido
- Metricas de aplicacao
- Dashboards operacionais
- Alertas

Isso e divida tecnica reconhecida — a prioridade atual e funcionalidade do pipeline.
