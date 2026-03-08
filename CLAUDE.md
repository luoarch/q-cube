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

# PM2 process manager (all 5 services)
pnpm pm2:start
pnpm pm2:logs
pnpm pm2:stop
```

### Python services (quant-engine / market-ingestion / fundamentals-engine)

```bash
cd services/quant-engine
python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]

python -m q3_quant_engine                    # FastAPI on :8100
celery -A q3_quant_engine.celery_app worker -Q strategy --loglevel=info

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

## Architecture

**Polyglot monorepo** — TypeScript frontend/API + Python quant engine, connected via Redis job queue.

```
Next.js (:3000) → NestJS API (:4000) → Redis Queue → Celery Worker → PostgreSQL
                                                    ↗
                   FastAPI quant-engine (:8100) ────┘
                   FastAPI market-ingestion (:8200) ──→ PostgreSQL
                   FastAPI fundamentals-engine (:8300) ─→ PostgreSQL
```

### Contract-first (SSOT)

All domain schemas live in `packages/shared-contracts` (Zod 4). Any payload change starts here.

- `domains/strategy.ts` — StrategyType enum, create/response schemas
- `domains/jobs.ts` — RunStatus, JobKind, queued event schema (imports strategyTypeSchema from strategy.ts)
- `shared-types` re-exports `RunStatus` from shared-contracts — no manual duplicates

### Dual ORM — same schema, two runtimes

| Layer | ORM | Models |
|-------|-----|--------|
| NestJS API | Drizzle | `apps/api/src/db/schema.ts` |
| Python workers | SQLAlchemy 2.x | `packages/shared-models-py/src/q3_shared_models/entities.py` |

Both define the same tables/enums. Migrations are managed by **Alembic only** (in quant-engine).

### Async job flow

1. API creates `StrategyRun` + `Job` (status: pending) in a Drizzle transaction
2. API pushes `strategyRunQueuedEvent` to Redis list `q3:strategy:jobs`
3. Celery worker dequeues, updates status to running, executes, then marks completed/failed
4. Task implementation: `services/quant-engine/src/q3_quant_engine/tasks/strategy.py`

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

## Stack Versions

Node.js 24.x, Python 3.13+, PostgreSQL 18, Redis 8, PM2 6, NestJS 11, Zod 4, Celery 5.6, SQLAlchemy 2.x, Drizzle ORM
