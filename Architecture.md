# Architecture.md — Q³ (Q-Cube)

## 1. Objetivo Arquitetural

Q³ é uma plataforma de pesquisa quantitativa orientada a jobs assíncronos para análise de ações e backtesting. A arquitetura prioriza:

- separação clara entre produto e engine quantitativo
- escalabilidade horizontal para processamento de estratégias
- reprodutibilidade de resultados
- contratos tipados fim a fim (SSOT)

## 2. Princípios

- Quant first: decisões da plataforma devem suportar experimentação quantitativa.
- Contract first: contratos em `packages/shared-contracts` são a referência oficial.
- Async by default: cálculos pesados não bloqueiam UX.
- Observable by design: métricas, tracing e logs estruturados desde o início.
- Multi-tenant secure: isolamento lógico e autorização por tenant/papel.

## 3. Visão de Alto Nível

```text
[Web App - Next.js]
        |
        | HTTPS (REST)
        v
[API - NestJS]
        |
        | enqueue jobs
        v
[Redis Queue] ----> [Python Workers - Quant Engine]
        |                         |
        |                         | writes
        v                         v
   [PostgreSQL] <---------> [Parquet Datasets]
```

## 4. Componentes

### 4.1 `apps/web` (Next.js 16)

Responsabilidades:

- autenticação e sessão
- dashboards de ranking/backtest
- controle de execução de estratégia
- visualização de carteira e resultados

Padrões:

- App Router
- Server Components por padrão
- TanStack Query para estado assíncrono de cliente

### 4.2 `apps/api` (NestJS 10)

Responsabilidades:

- autenticação/autorização (RBAC)
- controle multi-tenant
- validação de payloads
- orquestração de jobs
- API pública para frontend
- acesso a dados com Drizzle ORM

Módulos iniciais previstos:

- `auth`
- `tenancy`
- `strategy`
- `backtest`
- `portfolio`
- `jobs`

### 4.3 `services/quant-engine` (Python 3.13)

Responsabilidades:

- executar estratégia quantitativa
- aplicar pipeline de fatores/filtros/ranking
- rodar backtests
- persistir resultados agregados/detalhados

Stack:

- FastAPI (admin/status endpoints)
- Celery (execução distribuída)
- Pydantic v2 (tipagem/validação)
- SQLAlchemy 2.x (ORM/Core)
- Alembic (migrações)

### 4.4 `services/market-ingestion`

Responsabilidades:

- ingestão incremental de dados de mercado e fundamentos
- normalização de dados por ticker/período
- persistência em PostgreSQL e snapshots em Parquet

### 4.5 `packages/shared-contracts`

SSOT para contratos de domínio e payloads.

Tecnologia:

- TypeScript
- Zod

Domínios iniciais:

- `auth`
- `tenancy`
- `rbac`
- `market`
- `portfolio`
- `strategy`
- `backtest`
- `jobs`
- `events`
- `errors`

### 4.6 `packages/shared-types`

Tipos utilitários semânticos e aliases cross-app.

### 4.7 `packages/shared-events`

Schemas/tipos de eventos internos e integração event-driven.

## 5. Fluxos Críticos

### 5.1 Execução de Estratégia

```text
User -> Web -> API (/strategy-runs)
API valida contrato + RBAC + tenant
API cria StrategyRun (pending)
API publica job no Redis
Worker consome job e executa pipeline
Worker persiste resultados + atualiza status
API/Web consultam status e exibem output
```

### 5.2 Backtest

```text
User define parâmetros (janela, rebalance, universo)
API cria BacktestRun
Celery dispara tarefas particionadas
Workers agregam métricas (CAGR, Sharpe, MDD...)
Resultados consolidados em PostgreSQL/Parquet
```

### 5.3 Ingestão de Mercado

```text
Scheduler -> market-ingestion
Coleta dados brutos
Normaliza e valida schema
Upsert em PostgreSQL
Gera snapshot Parquet para analytics
Emite eventos de atualização
```

## 6. Modelo de Dados (Inicial)

Tabelas principais:

- `tenants`
- `users`
- `memberships`
- `assets`
- `prices`
- `financial_statements`
- `portfolios`
- `positions`
- `strategy_runs`
- `backtest_runs`
- `jobs`
- `events`

Diretrizes:

- todas as entidades com `id`, `created_at`, `updated_at`
- entidades de negócio com `tenant_id`
- índices por (`tenant_id`, `status`, `created_at`) em runs/jobs
- versionamento de datasets para reprodutibilidade

## 7. Contratos e Tipagem

Regras:

- payloads de API validados por Zod no backend
- frontend consome tipos inferidos dos contratos
- Python usa modelos gerados/equivalentes Pydantic
- nenhum endpoint sem schema explícito

## 8. Multi-Tenant e Segurança

Entidades de acesso:

- `Tenant`
- `User`
- `Membership`
- `Role`

Papéis:

- `owner`
- `admin`
- `member`
- `viewer`

Controles:

- autorização no nível de rota + recurso
- scoping obrigatório por `tenant_id`
- auditoria de ações críticas (execução, integração, permissão)

## 9. Processamento Assíncrono

Particionamento de workload por:

- `ticker`
- `período`
- `estratégia`
- `janela de backtest`

Estados de execução:

- `pending`
- `running`
- `completed`
- `failed`

Políticas:

- retry com backoff exponencial em falhas transitórias
- idempotência por `run_id + partition_key`
- dead-letter para jobs inválidos

## 10. Observabilidade

Instrumentação inicial:

- tracing distribuído (OpenTelemetry)
- métricas de API, fila e worker (Prometheus)
- dashboards operacionais e de produto (Grafana)

KPIs técnicos mínimos:

- latência p95 API
- tempo médio por `strategy_run`
- throughput da fila
- taxa de falha e retry
- latência de ingestão

## 11. Padrões Arquiteturais

Aplicações previstas:

- Strategy: estratégias quantitativas intercambiáveis
- Template Method: pipeline fixo de cálculo
- Factory: criação de strategy/provider/notifier
- Adapter: conectores externos (B3/Fintz)
- Facade: interface simplificada para módulos API
- Command: jobs de run/backtest
- Observer: eventos de conclusão/falha
- State: ciclo de vida de execução
- Repository/Specification: persistência e consulta de domínio

## 12. Decisões Técnicas (ADRs iniciais)

- ADR-001: Arquitetura polyglot (Node + Python)
- ADR-002: Redis como broker de jobs
- ADR-003: PostgreSQL como store transacional principal
- ADR-004: Parquet para datasets analíticos
- ADR-005: SSOT com Zod em pacote compartilhado
- ADR-006: Persistência sem SQL cru na aplicação (Drizzle + SQLAlchemy 2.x + Alembic)

## 13. Roadmap Arquitetural

### Fase 1 (MVP)

- auth + tenancy + RBAC base
- universe B3
- Magic Formula original
- pipeline de strategy run assíncrono

### Fase 2

- Magic Formula Brasil e híbrida
- integração de carteira
- melhoria de performance de workers

### Fase 3

- comparação avançada de estratégias
- backtests distribuídos em larga escala
- assistente de pesquisa quantitativa

## 14. Critérios de Pronto (Arquitetura)

Uma entrega arquitetural é considerada pronta quando:

- contratos e tipos foram definidos em SSOT
- fluxo assíncrono está observável (trace + métricas)
- isolamento multi-tenant está coberto por testes
- documentação técnica e diagrama foram atualizados
