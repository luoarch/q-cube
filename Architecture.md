# Architecture.md — Q³ (Q-Cube)

## 1. Objetivo

Q³ e uma plataforma de pesquisa quantitativa para o mercado brasileiro (B3). A arquitetura prioriza:

- Separacao clara entre produto (web/API), engines quantitativos (Python), e assistente AI
- Processamento assincrono para calculos pesados (Celery/Redis)
- Contratos tipados fim a fim (SSOT via Zod + SQLAlchemy)
- Reprodutibilidade de resultados (formula_version + inputs_snapshot + weights_version)
- AI assistiva e educacional — nunca altera scores/rankings determinísticos

## 2. Diagrama — 10 processos PM2

```text
[q3-web]                    Next.js :3000 (ranking, backtest, compare, chat, 3D viz)
    |
    | HTTPS (REST)
    v
[q3-api]                    NestJS :4000 (Drizzle ORM, 17 modules)
    |
    | enqueue jobs + proxy AI
    v
[Redis]                     Broker + cache
    |
    +---> [q3-quant-worker]             Celery (queues: strategy, backtest)
    |         ranking + refiner + backtest
    |
    +---> [q3-fundamentals-worker]      Celery (queue: fundamentals)
    |         CVM import + metrics
    |
    +---> [q3-ai-worker]               Celery (queues: ai-ranking, ai-backtest)
              ranking explainer + backtest narrator

[q3-quant-engine]           FastAPI :8100 (admin/status + queue poller)
[q3-market-ingestion]       FastAPI :8200 (data client adapters)
[q3-fundamentals-engine]    FastAPI :8300 (CVM pipeline + market snapshots)
[q3-ai-assistant]           FastAPI :8400 (council, chat, RAG, AI modules)
[q3-ai-beat]                Celery Beat (scheduled AI tasks)
    |
    v
[PostgreSQL]                30+ tabelas + views + pgvector embeddings
```

Configuracao PM2: `ecosystem.config.cjs`

## 3. Componentes

### 3.1 `apps/web` — Next.js 16

Dashboard completo com:

- **Ranking** — visualizacao de resultados de estrategia com scores refiner
- **Backtest** — configuracao, execucao e visualizacao de resultados (equity curve, metricas, trades)
- **Compare** — comparacao side-by-side de 2-3 ativos com winner chips
- **Chat** — interface conversacional com modos (free chat, solo agent, roundtable, debate, comparison)
- **Universe** — explorador de ativos do universo B3
- **Portfolio** — gestao de carteira
- **3D Visualization** — React Three Fiber layer para exploracao de dados

### 3.2 `apps/api` — NestJS 11 (Drizzle ORM)

17 modulos ativos:

| Modulo | Responsabilidade |
|--------|-----------------|
| `strategy` | Strategy run CRUD + job enqueue |
| `backtest` | Backtest run CRUD + job enqueue |
| `ranking` | Ranking results serving |
| `refiner` | Refinement results serving |
| `comparison` | Deterministic asset comparison |
| `intelligence` | Company intelligence aggregation |
| `chat` | Chat sessions + messages + proxy to AI assistant |
| `ai` | AI suggestions serving (ranking explainer, backtest narrator) |
| `asset` | Asset/issuer data |
| `universe` | B3 universe browser |
| `portfolio` | Portfolio management |
| `dashboard` | Dashboard aggregations |
| `auth` | Authentication |
| `health` | Health checks |
| `database` | Drizzle connection |
| `redis` | Redis connection |
| `common` | Shared guards, filters |

### 3.3 `services/quant-engine` — FastAPI + Celery

Responsabilidades:

- Executar estrategias quantitativas (3 variantes Magic Formula)
- Ranking pipeline (`strategies/ranking.py`)
- **Top 30 Refiner** — scoring deterministico de qualidade/seguranca/consistencia/disciplina de capital
- **Backtest engine** — backtests historicos com dados PIT, custo de transacao, benchmark
- **Compare engine** — comparacao deterministica de ativos com tolerancia e winner
- **Queue poller** — bridge Redis lists → Celery task queues (strategy + backtest)

Stack: FastAPI, Celery (queues: `strategy`, `backtest`), SQLAlchemy 2.x, Alembic (todas as migrations).

### 3.4 `services/fundamentals-engine` — FastAPI + Celery

Pipeline CVM-first de dados fundamentalistas:

1. Download ZIPs da CVM (DFP/ITR/FCA) com SHA-256 dedup
2. Parse (DfpParser, ItrParser, FcaParser) com version dedup
3. Normalizacao (canonical mapper, sign normalizer, scope resolver)
4. Resolucao de emissores/tickers (FCA → Cadastro → Manual)
5. Deteccao de restatements + invalidacao de metricas
6. Calculo de 12+ metricas derivadas (ROIC, EBITDA, margins, net_debt, debt/EBITDA, interest coverage, etc.)
7. Market snapshots (Yahoo/brapi) → EV, earnings_yield

Stack: FastAPI, Celery (queue: `fundamentals`), SQLAlchemy 2.x.

### 3.5 `services/market-ingestion` — FastAPI

Data client adapters para fontes externas:

- `clients/brapi.py` — brapi.dev quotes
- `clients/cvm.py` — CVM dados.gov.br
- `clients/dadosdemercado.py` — Dados de Mercado API

### 3.6 `services/ai-assistant` — FastAPI + Celery

Sistema de AI com multiplas capacidades:

- **AI Council** — 4 agentes especialistas + moderador, 4 modos (solo, roundtable, debate, comparison)
- **Free chat** — interface conversacional com tools internos + RAG + LLM synthesis
- **Ranking explainer** — explicacao AI de resultados de estrategia
- **Backtest narrator** — narrativa AI de resultados de backtest
- **Metric explainer** — explicacao AI de metricas individuais
- **RAG** — pgvector embeddings para retrieval semantico
- **Web tools** — busca web + browse para enriquecimento de contexto
- **LLM cascade** — OpenAI → Anthropic → Google com fallback automatico

Stack: FastAPI, Celery (queues: `ai-ranking`, `ai-backtest`), Celery Beat, SQLAlchemy 2.x, pgvector.

### 3.7 Shared packages

| Package | Tecnologia | Escopo |
|---------|-----------|--------|
| `shared-contracts` | Zod 4 | SSOT para API payloads (18 dominios) |
| `shared-fundamentals` | TypeScript | Canonical keys, metric codes, domain enums |
| `shared-models-py` | SQLAlchemy 2.x | SSOT para todas as tabelas Python |
| `shared-types` | TypeScript | Re-export de tipos de shared-contracts |
| `shared-events` | TypeScript | Event schemas |

## 4. Fluxos

### 4.1 Strategy run + Refiner

```text
User → Web → API POST /strategy-runs
API valida contrato + tenant guard
API cria StrategyRun + Job (pending) via Drizzle
API publica evento no Redis (q3:strategy:jobs)
Queue poller (quant-engine) consome Redis → send_task Celery
Celery worker executa ranking pipeline
Worker executa Refiner no top 30 (deterministico)
Worker indexa resultados no RAG (pgvector)
Worker persiste resultados + atualiza status (completed/failed)
API/Web consultam status e exibem output com scores refiner
```

### 4.2 Backtest

```text
User → Web → API POST /backtest-runs
API cria BacktestRun + Job (pending) via Drizzle
API publica evento no Redis (q3:backtest:jobs)
Queue poller consome Redis → send_task Celery
Celery worker executa backtest com dados PIT:
  - market_snapshots: fetched_at <= as_of_date
  - filings: available_at <= cutoff (reference_date + 4 meses)
Worker calcula metricas (CAGR, Sharpe, Sortino, max drawdown, etc.)
Worker persiste equity curve + trades + metricas
API/Web consultam e exibem resultados
```

### 4.3 AI Council

```text
User → Web (chat UI) → API POST /chat/sessions/:id/messages
API detecta modo (solo/roundtable/debate/comparison)
API proxy → AI Assistant POST /council/analyze
AI Assistant constroi AssetAnalysisPacket do DB
  - computed_metrics, refinement_results, market_snapshots
  - data completeness + score reliability
AI Assistant roteia para CouncilOrchestrator
Agentes analisam em paralelo (ThreadPoolExecutor)
  - Hard rejects checados antes do LLM
  - LLM gera opiniao estruturada (AgentOpinion)
Moderador sintetiza (convergencias, divergencias, riscos)
Resultado retorna via API → persiste chat_messages
Web renderiza scoreboard, agent cards, debate timeline
```

### 4.4 CVM import

```text
POST /batches/cvm/2024 → fundamentals-engine
Cria raw_source_batches (pending)
Enqueue import_cvm_batch no Redis
Worker: download → parse → normalize → resolve issuers → detect restatements → compute metrics → refresh compat view
```

### 4.5 Market snapshots

```text
POST /batches/snapshots/refresh → fundamentals-engine
Worker: fetch Yahoo quotes → persist market_snapshots → chain compute_market_metrics
compute_market_metrics: EV + earnings_yield para issuers com snapshot fresco (< 7 dias)
```

## 5. Data model — 30+ tabelas + views

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
| `backtest_runs` | Execucao de backtest |
| `jobs` | Job assincrono (strategy_run, backtest_run) |

### Fundamentals — Raw Layer

| Tabela | Descricao |
|--------|-----------|
| `raw_source_batches` | Batch de download (source, year, doc_type, status) |
| `raw_source_files` | Arquivo baixado (filename, sha256, size_bytes) |

### Fundamentals — Normalized Layer

| Tabela | Descricao |
|--------|-----------|
| `issuers` | Emissor CVM (cvm_code, cnpj, sector, classification) |
| `securities` | Ticker de um emissor (issuer_id, ticker, is_primary) |
| `filings` | Demonstracao financeira (issuer_id, filing_type, reference_date, version, available_at) |
| `statement_lines` | Linha contabil normalizada (canonical_key, normalized_value, scope) |

### Fundamentals — Derived Layer

| Tabela | Descricao |
|--------|-----------|
| `computed_metrics` | Indicador derivado (metric_code, value, formula_version) |
| `restatement_events` | Retificacao detectada |

### Market Layer

| Tabela | Descricao |
|--------|-----------|
| `market_snapshots` | Quote point-in-time (security_id, price, market_cap, volume, fetched_at) |

### Refiner Layer

| Tabela | Descricao |
|--------|-----------|
| `refinement_results` | Scores de qualidade/seguranca/consistencia, flags, adjusted rank |

### AI Layer

| Tabela | Descricao |
|--------|-----------|
| `ai_suggestions` | Sugestoes AI (ranking explainer, backtest narrator, metric explainer) |
| `ai_explanations` | Explicacoes AI de metricas |
| `ai_research_notes` | Notas de pesquisa AI |
| `chat_sessions` | Sessoes de chat (modo, tenant, user) |
| `chat_messages` | Mensagens de chat (role, content, agent_id, cost, tokens) |
| `council_sessions` | Sessoes de conselho (mode, asset_ids, agent_ids) |
| `council_opinions` | Opinioes de agentes (verdict, confidence, opinion_json) |
| `council_debates` | Rounds de debate (round_number, agent_id, content) |
| `council_syntheses` | Sinteses do moderador (scoreboard, conflicts, synthesis) |
| `embeddings` | Vetores pgvector para RAG (entity_type, chunk_text, embedding) |

### Views

| View | Descricao |
|------|-----------|
| `v_financial_statements_compat` | Materialized view — projeta dados canonicos + market snapshots |

## 6. SSOT — 4 camadas

```text
1. shared-contracts (Zod 4)     → 18 dominios: strategy, backtest, refiner, council, chat, comparison, intelligence, etc.
2. shared-fundamentals (TS)     → Canonical keys, metric codes, enums
3. shared-models-py (SQLAlchemy) → Tabelas, SSOT para Python services
4. apps/api/src/db/schema.ts    → Mirror Drizzle (manual)
```

Regra: mudanca de payload comeca em `shared-contracts`. Mudanca de tabela comeca em `shared-models-py` + migration Alembic.

## 7. Multi-tenant

Schema suporta isolamento multi-tenant (UUID PKs, cascade deletes, `tenant_id` scoping). Roles: owner, admin, member, viewer. Tenant guard no API via `x-tenant-id` header.

## 8. Processamento assincrono

| Queue | Worker | Tasks |
|-------|--------|-------|
| `strategy` | q3-quant-worker | `run_strategy_task` (ranking + refiner) |
| `backtest` | q3-quant-worker | `backtest_run_task` |
| `fundamentals` | q3-fundamentals-worker | `import_cvm_batch`, `compute_metrics_for_issuer`, `fetch_market_snapshots`, `compute_market_metrics` |
| `ai-ranking` | q3-ai-worker | `generate_ranking_explanation` |
| `ai-backtest` | q3-ai-worker | `generate_backtest_narrative` |

**Queue poller**: `services/quant-engine/src/q3_quant_engine/queue_poller.py` — daemon thread que faz bridge entre Redis lists (`q3:strategy:jobs`, `q3:backtest:jobs`) e Celery task queues via `celery_app.send_task()`.

Estados de execucao: `pending` → `running` → `completed` | `failed`

Broker: Redis 8.x. Celery 5.6.x com prefork pool.

## 9. AI Architecture

### LLM Cascade

Multi-provider com fallback automatico:
1. OpenAI (gpt-4o-mini / gpt-5.4-pro)
2. Anthropic (claude-sonnet-4-6 / claude-opus-4-6)
3. Google (gemini-2.5-pro)

Configuracao via env vars com prefixo `Q3_AI_`. Cost limit: $10/day por tenant.

### Council — GoF Patterns

| Pattern | Onde |
|---------|------|
| **Strategy** | Cada perfil de investimento (StrategyProfile) |
| **Factory Method** | `agent_factory.py` — cria agente a partir do perfil |
| **Template Method** | `agent_base.py` — pipeline fixo: load data → check hard rejects → analyze → format opinion |
| **Mediator** | `orchestrator.py` — coordena agentes, roteia modos |
| **Adapter** | `packet.py` — normaliza dados de multiplas fontes em AssetAnalysisPacket |

### RAG Pipeline

```text
Strategy run / Refiner results → auto_indexer → chunker → embedder → pgvector
Free chat query → retriever → semantic search (halfvec, cosine) → context → LLM
```

### Source Precedence

1. Structured internal data (computed_metrics, statement_lines, refinement_results)
2. Internal docs / RAG
3. External web (news, context)
4. Model prior knowledge (educational only)

## 10. Observabilidade

**Estado atual:** logs estruturados via `logging` module (Python) e NestJS logger (TypeScript). AI calls tracked com tokens_used, cost_usd, provider_used, model_used, fallback_level.

Divida tecnica reconhecida: tracing distribuido, metricas de aplicacao, dashboards operacionais.
