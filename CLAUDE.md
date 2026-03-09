# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Dev Commands

```bash
# Full local bootstrap (validates PG/Redis, installs deps, builds packages, starts PM2)
pnpm bootstrap:local

# Build all TypeScript packages (shared-contracts must build first)
pnpm build

# Typecheck / lint entire workspace
pnpm typecheck
pnpm lint

# Single package filter
pnpm --filter @q3/shared-contracts build
pnpm --filter @q3/api typecheck

# Database
pnpm db:migrate          # Alembic upgrade head
pnpm db:seed             # Demo tenant + user

# PM2 process manager (all 10 processes)
pnpm pm2:start
pnpm pm2:logs
pnpm pm2:stop
```

### Python services (quant-engine / market-ingestion / fundamentals-engine / ai-assistant)

```bash
cd services/quant-engine
python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]

python -m q3_quant_engine                    # FastAPI on :8100
celery -A q3_quant_engine.celery_app worker -Q strategy,backtest --loglevel=info

python -m ruff check src                     # Lint
python -m mypy src                           # Typecheck
python -m pytest                             # Tests
python -m pytest -k "test_name"              # Single test
```

```bash
cd services/fundamentals-engine
python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]

python -m q3_fundamentals_engine             # FastAPI on :8300
celery -A q3_fundamentals_engine.celery_app worker -Q fundamentals --loglevel=info

python -m ruff check src tests               # Lint
python -m pytest                             # Tests
```

```bash
cd services/ai-assistant
python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]

python -m q3_ai_assistant                    # FastAPI on :8400
celery -A q3_ai_assistant.celery_app worker -Q ai-ranking,ai-backtest --loglevel=info

python -m ruff check src                     # Lint
python -m pytest                             # Tests
```

## Architecture

**Polyglot monorepo** — TypeScript frontend/API + Python engines + AI assistant, connected via Redis job queue.

```
Next.js (:3000) → NestJS API (:4000) → Redis Queue → Celery Workers → PostgreSQL
                                                    ↗
                   FastAPI quant-engine (:8100) ────┘ (+ queue poller)
                   FastAPI market-ingestion (:8200) ──→ PostgreSQL
                   FastAPI fundamentals-engine (:8300) ─→ PostgreSQL
                   FastAPI ai-assistant (:8400) ──→ LLM cascade + pgvector
```

### Contract-first (SSOT)

All domain schemas live in `packages/shared-contracts` (Zod 4). Any payload change starts here.

- `domains/strategy.ts` — StrategyType enum, create/response schemas
- `domains/backtest.ts` — BacktestConfig, metrics, equity curve schemas
- `domains/refiner.ts` — Refinement scores, flags, adjusted rank
- `domains/council.ts` — AgentVerdict, AgentOpinion, CouncilResult, debate schemas
- `domains/chat.ts` — ChatSession, ChatMessage, SendMessage schemas
- `domains/comparison.ts` — ComparisonMatrix, MetricComparison, WinnerSummary
- `domains/intelligence.ts` — Company intelligence aggregation
- `domains/jobs.ts` — RunStatus, JobKind, queued event schema
- `domains/user-context.ts` — UserContextProfile, preferences schemas
- `domains/versioning.ts` — AnalysisVersionSet for reproducibility
### Dual ORM — same schema, two runtimes

| Layer | ORM | Models |
|-------|-----|--------|
| NestJS API | Drizzle | `apps/api/src/db/schema.ts` |
| Python workers | SQLAlchemy 2.x | `packages/shared-models-py/src/q3_shared_models/entities.py` |

Both define the same tables/enums. Migrations are managed by **Alembic only** (in quant-engine).

### Async job flow

1. API creates run + job (status: pending) in a Drizzle transaction
2. API pushes event to Redis list (`q3:strategy:jobs` or `q3:backtest:jobs`)
3. Queue poller (`quant-engine/queue_poller.py`) bridges Redis lists → Celery via `send_task()`
4. Celery worker executes, runs refiner (strategy) or backtest engine
5. Task implementation: `services/quant-engine/src/q3_quant_engine/tasks/strategy.py`

### AI Council flow

1. Web sends message to `POST /chat/sessions/:id/messages` with mode + tickers
2. NestJS `chat.service.ts` proxies to AI assistant (`POST /council/analyze` or `POST /chat/free`)
3. AI assistant builds `AssetAnalysisPacket` from DB, routes to `CouncilOrchestrator`
4. Agents analyze in parallel, moderator synthesizes
5. Results returned to NestJS, persisted as chat messages + council records

### Multi-tenant

All queries must scope by `tenantId`. Tables use UUID PKs and cascade deletes from `tenants`. (Schema ready, not enforced in practice.)

## Key Conventions

- **TypeScript**: strict mode, no `any`, Zod validation at API boundaries, ESM with `.js` extensions in imports
- **Python**: type hints everywhere, `src/` layout, execution via `python -m`, logging module (not print)
- **DB URL**: Python services use `ensure_psycopg_url()` from `db/session.py` to convert `postgresql://` → `postgresql+psycopg://`
- **Commits**: Conventional Commits — `feat(strategy): ...`, `fix(api): ...`, `chore(repo): ...`
- **Branches**: `feat/<scope>-<summary>`, `fix/<scope>-<summary>`

### Market data separation

Filing data (CVM) and market snapshots (Yahoo/yfinance) are kept separate:

- **Filing data**: CVM raw filings → parsed → normalized into `filings` + `statement_lines` → derived `computed_metrics`
- **Market snapshots**: Yahoo/yfinance (default) or brapi.dev → `market_snapshots` table (keyed by `security_id`), provides `market_cap` for EV/earnings yield
- **Provider selection**: `MARKET_SNAPSHOT_SOURCE=yahoo` (default). Switch to `brapi` via env var. Factory: `MarketSnapshotProviderFactory.create()`
- **Config flags**: `ENABLE_YAHOO=true` (default ON), `ENABLE_BRAPI=false`. `SNAPSHOT_STALENESS_DAYS=7`
- **Adapter policy**: never import `yfinance` outside `providers/yahoo/adapter.py` — all Yahoo conventions (`.SA` suffix) stay inside the adapter
- **Staleness**: snapshots older than `SNAPSHOT_STALENESS_DAYS` are treated as stale — compat view NULLs out `market_cap`/`avg_daily_volume`, and `compute_market_metrics` skips them
- **Primary security**: EV/EY metrics use the issuer's `is_primary=true` security. Unique key: `(issuer_id, metric_code, period_type, reference_date)` — one active value per issuer
- **Idempotency**: `MetricsEngine._upsert_metric()` uses `SELECT FOR UPDATE` + UPDATE/INSERT — works with SQLAlchemy identity map and serializes concurrent writes. Unique index `(issuer_id, metric_code, period_type, reference_date)` is the final safety net
- **`POST /batches/snapshots/refresh`**: triggers snapshot fetch using the configured provider
- **Pipeline steps**: shared via `pipeline_steps.py` — both `facade.py` and `import_batch.py` task use the same step functions

### AI configuration

- **Env prefix**: `Q3_AI_` (e.g., `Q3_AI_OPENAI_API_KEY`, `Q3_AI_ANTHROPIC_API_KEY`)
- **Config file**: `services/ai-assistant/src/q3_ai_assistant/config.py` (pydantic-settings, loads `../../.env`)
- **LLM cascade**: OpenAI → Anthropic → Google with automatic fallback
- **Cost limit**: `Q3_AI_COST_LIMIT_USD_DAILY=10.0`
- **Council agents**: Greenblatt, Graham, Buffett, Barsi + Moderator Q³
- **RAG**: pgvector embeddings auto-indexed after strategy runs and refiner results
- **OTel**: real OpenTelemetry SDK with OTLP gRPC export (`OTEL_EXPORTER_OTLP_ENDPOINT`), spans on LLM cascade, agent analysis, council modes
- **Per-tenant limits**: `rate_limit_rpm` and `ai_daily_cost_limit_usd` columns on tenants table, enforced by `TenantThrottlerGuard` and `CostBudget`
- **PII redaction**: `contains_pii()` + `redact_pii()` for CPF, CNPJ, email, phone, card numbers
- **Audit trail**: SHA-256 `input_hash`, per-opinion `latency_ms`, full cost tracking

## Stack Versions

Node.js 24.x, Python 3.13+, PostgreSQL 18 (pgvector), Redis 8, PM2 6, NestJS 11, Zod 4, Celery 5.6, SQLAlchemy 2.x, Drizzle ORM, React Three Fiber
