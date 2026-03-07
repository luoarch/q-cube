# Q³ — Q-Cube

**Quantity · Quality · Quant Technology**

Q³ is a **quantitative equity research platform** for the Brazilian market (B3). It automates stock selection using disciplined, reproducible quantitative methods — starting with the Magic Formula and its variations.

---

## Vision vs current scope

### Vision

A full **Quant Strategy Lab** capable of:

- analyzing the entire B3 universe
- executing multiple quantitative strategies
- generating ranked stock lists
- running historical backtests
- comparing strategies side-by-side
- analyzing personal portfolios

### MVP scope (current)

- **CVM-first fundamentals pipeline** — filing data (DFP/ITR) parsed, normalized, and stored with derived metrics (ROIC, EBITDA, margins, net_debt)
- **Market snapshots** (opt-in via `ENABLE_BRAPI`) — brapi.dev quotes provide `market_cap` for Enterprise Value and Earnings Yield
- **Magic Formula ranking** — requires both CVM fundamentals **and** market snapshots for the complete strategy
- **Next.js scaffold** — auth UI + empty dashboard, no real product functionality yet
- **Single-tenant** auth scaffold (multi-tenant schema ready, not enforced yet)

> **Important:** Magic Formula = fundamentals + market snapshots. Without `ENABLE_BRAPI=true`, Enterprise Value and Earnings Yield cannot be calculated (`EV = market_cap + net_debt` requires market data). What exists without snapshots is the **CVM-first fundamentals pipeline** — ROIC, margins, EBITDA, net_debt — not the Magic Formula. The ranking falls back to EBIT margin + ROIC, which is a partial approximation.

### Post-MVP roadmap

- Magic Formula Brasil (sector/liquidity filters)
- Magic Formula Hybrid (quality score, momentum, ROIC, Debt/EBITDA, margin stability)
- Full backtesting engine (CAGR, Sharpe, max drawdown, volatility, hit rate)
- Strategy comparison
- Multi-user onboarding
- B3 Investor API integration (requires CNPJ + licensing)

---

## Architecture

Polyglot monorepo — TypeScript frontend/API + Python engines, connected via Celery/Redis broker.

```text
Next.js (:3000)
      ↓
NestJS API (:4000)
      ↓
Celery / Redis broker
      ↓
┌─────────────────────────┐
│  fundamentals-engine    │  CVM ingestion, normalization, derived metrics
│  (:8300)                │
├─────────────────────────┤
│  quant-engine           │  Strategy execution, ranking, backtests
│  (:8100)                │
├─────────────────────────┤
│  market-ingestion       │  Data client adapters (brapi, CVM, Dados de Mercado)
│  (:8200)                │
└─────────────────────────┘
      ↓
PostgreSQL
```

### Data domains

| Domain | Source | Storage | Purpose |
|--------|--------|---------|---------|
| **Raw filings** | CVM (DFP/ITR/FCA) | `raw_source_batches` + `raw_source_files` | Audit trail / data lake |
| **Canonical fundamentals** | CVM → normalization pipeline | `issuers` + `filings` + `statement_lines` | Issuer-centric financial data |
| **Computed metrics** | Derived from statement_lines | `computed_metrics` | ROIC, EBITDA, margins, net_debt |
| **Market snapshots** | brapi.dev quotes | `market_snapshots` | Price, market_cap, volume per security |
| **Market-derived metrics** | market_cap + filing data | `computed_metrics` (EV, earnings yield) | Requires both CVM + snapshot data |

### Fundamentals pipeline

```text
raw ingestion → parsing → normalization → issuer/security mapping → restatement detection → derived metrics → serving
```

### Market enrichment

```text
snapshot fetch → staleness validation (7-day window) → market-derived metrics (EV, earnings yield) → compat view refresh
```

### Async job flow

1. API creates `StrategyRun` + `Job` (status: pending) in a Drizzle transaction
2. API pushes `strategyRunQueuedEvent` to Redis list `q3:strategy:jobs`
3. Celery worker dequeues, updates status to running, executes, then marks completed/failed

---

## Repository structure

```text
apps/
  web/                → Next.js frontend (scaffold — auth UI + empty dashboard)
  api/                → NestJS backend (Drizzle ORM)

services/
  fundamentals-engine/  → CVM ingestion, normalization, metrics (FastAPI + Celery)
  quant-engine/         → Strategy execution, ranking (FastAPI + Celery, Alembic migrations)
  market-ingestion/     → Data client adapters (brapi, CVM, Dados de Mercado)

packages/
  shared-contracts/     → Zod schemas — SSOT for API payloads and domain types
  shared-fundamentals/  → Canonical keys, metric codes, domain enums (TypeScript)
  shared-models-py/     → SQLAlchemy models — SSOT for all Python services
  shared-types/         → Re-exported types from shared-contracts
  shared-events/        → Event schemas
```

---

## Shared contracts and SSOT

The system has two layers of SSOT:

| Layer | Package | Technology | Scope |
|-------|---------|------------|-------|
| **API contracts** | `shared-contracts` | Zod 4 | Strategy types, job schemas, API payloads |
| **Fundamentals domain** | `shared-fundamentals` | TypeScript | Canonical keys, metric codes, enums |
| **Persistence models** | `shared-models-py` | SQLAlchemy 2.x | All table definitions for Python services |
| **Persistence schema** | `apps/api/src/db/schema.ts` | Drizzle | Manual mirror of SQLAlchemy models for the NestJS API (no auto-generation, no CI check) |

**Important distinction:**

- **Zod/contracts** = semantic truth (what the domain means)
- **SQLAlchemy/Drizzle** = persistence mirrors (how it's stored)
- Both ORMs define the same tables/enums. Migrations are managed by **Alembic only** (in `services/quant-engine/alembic/`).

---

## Quantitative strategies

### 1 — Magic Formula (Original) — fundamentals + market snapshots

Based on Joel Greenblatt's book.

```text
Earnings Yield = EBIT / Enterprise Value
Return on Capital = EBIT / (Net Working Capital + Fixed Assets)
Ranking = Rank(EY) + Rank(ROC)
```

> **Requires `market_cap` from market snapshots** (`ENABLE_BRAPI=true`). Without market data, EV cannot be calculated, EY remains NULL, and the strategy falls back to EBIT margin + ROIC (partial approximation). The CVM-first fundamentals pipeline provides the accounting base (ROIC, margins, net_debt, EBITDA), but the complete Magic Formula needs both CVM + brapi.dev data.

### 2 — Magic Formula Brasil (post-MVP)

Additional filters: exclude financials/utilities, minimum liquidity, minimum market cap, positive EBIT.

### 3 — Magic Formula Hybrid (post-MVP)

Additional factors: quality score, momentum, ROIC, Debt/EBITDA, margin stability. Objective: reduce value traps.

---

## Data sources

### Source priority

```text
CVM raw (audit trail) → Dados de Mercado (primary fundamentals) → brapi.dev (market quotes)
```

Feature flags control which sources are active: `ENABLE_CVM`, `ENABLE_BRAPI`, `ENABLE_DADOS_MERCADO`.

### CVM — source of truth

All fundamental data originates from CVM (Comissão de Valores Mobiliários) public filings.

- **DFP** (annual) and **ITR** (quarterly) filings provide financial statements
- **FCA** provides issuer metadata and ticker mapping
- **Cadastro** provides sector classification
- **Restatements** are detected and handled — superseded filings are marked, affected metrics invalidated

### brapi.dev — market snapshots (opt-in)

- Activated via `ENABLE_BRAPI=true`
- Provides `market_cap`, price, volume per security
- Free tier: 15k requests/month (~439 issuers)
- **Staleness policy**: snapshots older than 7 days are treated as stale (NULLed in compat view, skipped in metric computation)
- Endpoint: `POST /batches/snapshots/refresh`

---

## Multi-tenant

Schema supports multi-tenant isolation (UUID PKs, cascade deletes from `tenants`, `tenantId` scoping). Currently single-tenant in practice.

Roles: `owner`, `admin`, `member`, `viewer`.

---

## Persistence

| Runtime | ORM | Migrations |
|---------|-----|------------|
| NestJS API | Drizzle | — |
| Python services | SQLAlchemy 2.x | Alembic (in quant-engine) |

Rules:

- Avoid raw SQL in application/business logic
- Migrations may contain raw SQL when needed (DDL, views, indexes)
- Materialized views and compat views are acceptable infrastructure
- `ensure_psycopg_url()` converts `postgresql://` → `postgresql+psycopg://` for Python services

---

## Glossary

| Term | Definition |
|------|-----------|
| **Issuer** | A company registered with CVM (identified by `cvm_code` and `cnpj`) |
| **Security** | A tradable instrument (ticker) belonging to an issuer (e.g., PETR3, PETR4) |
| **Filing** | A CVM document submission (DFP, ITR, FCA) for a reference date |
| **Statement line** | A single accounting line item from a filing, with canonical key mapping |
| **Computed metric** | A derived indicator (ROIC, EBITDA, EV, etc.) calculated from statement lines |
| **Market snapshot** | A point-in-time quote (price, market_cap, volume) for a security |
| **Strategy run** | An execution of a quantitative strategy producing a ranked stock list |

---

## Stack versions

| Component | Version | Notes |
|-----------|---------|-------|
| Node.js | 24.x LTS | Runtime for Next.js and NestJS |
| Python | 3.13+ | Runtime for all Python services |
| Next.js | 16.x | Frontend framework |
| React | 19.x | UI library |
| NestJS | 11.x | Application backend |
| PostgreSQL | 18.x | Primary database |
| Redis | 8.x | Celery broker + cache |
| Celery | 5.6.x | Distributed task queue |
| SQLAlchemy | 2.x | Python ORM |
| Drizzle | latest | TypeScript ORM |
| Zod | 4.x | Schema validation |
| PM2 | 6.x | Process manager |
| FastAPI | latest | Python API framework ([docs](https://fastapi.tiangolo.com/)) |

> Versions pinned at bootstrap; no automated version checks in CI.

---

## License

Proprietary — All rights reserved.

---

## Author

Lucas Moraes
(Q³ Project Founder)
