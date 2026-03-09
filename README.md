# Q³ — Q-Cube

**Quantity · Quality · Quant Technology**

Q³ is a **quantitative equity research platform** for the Brazilian market (B3). It automates stock selection using disciplined, reproducible quantitative methods, enriched by AI-powered analysis.

---

## What it does

- **CVM-first fundamentals pipeline** — filing data (DFP/ITR/FCA) parsed, normalized, and stored with 12+ derived metrics (ROIC, EBITDA, margins, net_debt, debt/EBITDA, interest coverage, etc.)
- **Market snapshots** — Yahoo/yfinance (default) or brapi.dev provide `market_cap` for Enterprise Value and Earnings Yield
- **Magic Formula ranking** — 3 strategy variants (Original, Brasil, Hybrid) with full-universe ranking
- **Top 30 Refiner** — deterministic quality/safety/consistency scoring on top-N ranked assets using 3-period trends
- **Backtesting engine** — historical backtests with PIT (point-in-time) data, cost modeling, benchmark comparison (CAGR, Sharpe, Sortino, max drawdown, hit rate, turnover)
- **Compare Assets** — deterministic comparison (2–3 assets) across 11 metrics with tolerance bands and winner determination
- **Company Intelligence** — per-company page aggregating base factors, refiner scores, trend data, flags, and AI explanations
- **AI Council** — multi-agent system with 4 investment-school-inspired specialists (Greenblatt, Graham, Buffett, Barsi) + Moderator, supporting solo analysis, roundtable, 4-round debate, and comparison modes
- **Free chat** — conversational interface with internal tools, RAG retrieval, and LLM synthesis
- **RAG** — pgvector embeddings for strategy runs, refiner results, and council opinions
- **Observability** — OpenTelemetry distributed tracing (OTLP gRPC), structured logging, full audit trail (input_hash, latency_ms, cost per call)
- **Per-tenant governance** — configurable rate limits (RPM) and daily AI cost budgets per tenant, PII redaction (CPF/CNPJ/email/phone/card), session archival
- **User profiles** — preferred strategy, watchlist, favorite agents, default chat mode
- **3D visualization** — React Three Fiber layer for data exploration

### Regulatory framing

Product positioned as analytical/educational tool, not personalized investment advice (CVM 20, CVM 178, ANBIMA). Agents use "-inspired" naming, disclaimers always present, no direct buy/sell orders.

---

## Architecture

Polyglot monorepo — TypeScript frontend/API + Python engines + AI assistant, connected via Redis/Celery.

```text
Next.js (:3000)
      |
NestJS API (:4000)
      |
      +--- Redis Queue ---+
      |                   |
      v                   v
  Celery Workers      AI Assistant (:8400)
  (strategy,          (council, chat,
   backtest,           ranking explainer,
   fundamentals)       backtest narrator)
      |                   |
      v                   v
PostgreSQL            LLM Cascade
(pgvector)            (OpenAI -> Anthropic -> Google)
      ^
      |
  FastAPI Services
  quant-engine (:8100)
  fundamentals-engine (:8300)
  market-ingestion (:8200)
```

### 10 PM2 processes

| Process | Runtime | Port | Role |
|---------|---------|------|------|
| q3-web | Next.js | 3000 | Frontend |
| q3-api | NestJS | 4000 | API gateway |
| q3-quant-engine | FastAPI | 8100 | Quant admin + queue poller |
| q3-quant-worker | Celery | — | Strategy, backtest, refiner execution |
| q3-market-ingestion | FastAPI | 8200 | Data client adapters |
| q3-fundamentals-engine | FastAPI | 8300 | CVM pipeline + market snapshots |
| q3-fundamentals-worker | Celery | — | CVM import, metrics computation |
| q3-ai-assistant | FastAPI | 8400 | Council, chat, AI modules |
| q3-ai-worker | Celery | — | Ranking explainer, backtest narrator |
| q3-ai-beat | Celery Beat | — | Scheduled AI tasks |

### Data domains

| Domain | Source | Storage | Purpose |
|--------|--------|---------|---------|
| **Raw filings** | CVM (DFP/ITR/FCA) | `raw_source_batches` + `raw_source_files` | Audit trail / data lake |
| **Canonical fundamentals** | CVM → normalization | `issuers` + `filings` + `statement_lines` | Issuer-centric financial data |
| **Computed metrics** | Derived from statement_lines | `computed_metrics` | 12+ indicators (ROIC, EBITDA, margins, etc.) |
| **Market snapshots** | Yahoo/yfinance, brapi.dev | `market_snapshots` | Price, market_cap, volume per security |
| **Refinement results** | Top-N refiner | `refinement_results` | Quality/safety/consistency scores + flags |
| **Backtest results** | Backtest engine | `backtest_runs` | Equity curve, metrics, trade log |
| **Chat/Council** | AI assistant | `chat_sessions` + `chat_messages` + `council_*` | Conversations, agent opinions, debates |
| **RAG embeddings** | Auto-indexer | `embeddings` (pgvector) | Semantic retrieval for AI |
| **User profiles** | User settings | `user_context_profiles` | Watchlist, strategy, agent preferences |

### Async job flow

1. API creates run + job (status: pending) in a Drizzle transaction
2. API pushes event to Redis list (`q3:strategy:jobs` or `q3:backtest:jobs`)
3. Queue poller bridges Redis lists → Celery task queues
4. Celery worker executes, runs refiner (if strategy run), updates status
5. API/Web poll for results

---

## Repository structure

```text
apps/
  web/                    → Next.js frontend (ranking, backtest, compare, chat, profile, 3D viz)
  api/                    → NestJS backend (18 modules, Drizzle ORM)

services/
  quant-engine/           → Strategy execution, ranking, refiner, backtest, comparison (FastAPI + Celery)
  fundamentals-engine/    → CVM ingestion, normalization, metrics (FastAPI + Celery)
  market-ingestion/       → Data client adapters (brapi, CVM, Dados de Mercado)
  ai-assistant/           → AI Council, free chat, RAG, ranking explainer, backtest narrator (FastAPI + Celery)

packages/
  shared-contracts/       → Zod 4 schemas — SSOT for API payloads (19 domain files)
  shared-fundamentals/    → Canonical keys, metric codes, domain enums (TypeScript)
  shared-models-py/       → SQLAlchemy models — SSOT for all Python services
  shared-types/           → Re-exported types from shared-contracts
  shared-events/          → Event schemas
```

---

## Quantitative strategies

### Magic Formula Original

Based on Joel Greenblatt's book. `Earnings Yield = EBIT / EV`, `Return on Capital = EBIT / (NWC + Fixed Assets)`.

### Magic Formula Brasil

Additional filters: exclude financials/utilities, minimum liquidity, minimum market cap, positive EBIT.

### Magic Formula Hybrid

Additional factors: quality score, momentum, ROIC, Debt/EBITDA, margin stability. Designed to reduce value traps.

> All three variants require `market_cap` from market snapshots for complete EV/EY calculation. Without market data, the ranking falls back to EBIT margin + ROIC.

---

## AI Council

Multi-agent investment analysis system with 4 specialist agents + moderator:

| Agent | Focus | Core Metrics |
|-------|-------|-------------|
| Greenblatt-inspired | Earnings yield, return on capital | EY, ROIC, EBIT margin |
| Graham-inspired | Margin of safety, price vs value | P/L, P/VPA, net debt |
| Buffett-inspired | Quality, moat, capital allocation | ROE, margins consistency, FCF |
| Barsi-inspired | Dividends, income, longevity | DY, payout, FCF, recurring profit |
| Moderator Q³ | Synthesize, compare views | All (meta-analysis) |

### Modes

- **Solo** — single specialist analyzes one asset
- **Roundtable** — all 4 specialists + moderator synthesis
- **Debate** — selected agents in 4-round protocol (initial → contestation → reply → synthesis)
- **Comparison** — deterministic compare + per-asset agent roundtables

### Free chat

Conversational mode with internal tools (get_ranked_assets, get_refinement_results, get_company_financials, compare_companies, etc.), RAG retrieval, and LLM synthesis.

---

## Data sources

| Domain | Source | Notes |
|--------|--------|-------|
| Fundamentals (filings, statements) | CVM | Sole source of truth for accounting data |
| Market snapshots (price, market_cap) | Yahoo/yfinance | Free, no token, default provider |
| Market snapshots (fallback) | brapi.dev | Requires `BRAPI_TOKEN` |

Feature flags: `ENABLE_CVM`, `ENABLE_YAHOO` (default ON), `ENABLE_BRAPI`, `ENABLE_DADOS_MERCADO`.

---

## Shared contracts and SSOT

| Layer | Package | Technology | Scope |
|-------|---------|------------|-------|
| **API contracts** | `shared-contracts` | Zod 4 | 19 domain files (strategy, backtest, refiner, council, chat, comparison, intelligence, etc.) |
| **Fundamentals domain** | `shared-fundamentals` | TypeScript | Canonical keys, metric codes, enums |
| **Persistence models** | `shared-models-py` | SQLAlchemy 2.x | All table definitions for Python services |
| **Persistence schema** | `apps/api/src/db/schema.ts` | Drizzle | Mirror of SQLAlchemy models for NestJS API |

Migrations managed by **Alembic only** (in `services/quant-engine/alembic/`).

---

## Stack versions

| Component | Version |
|-----------|---------|
| Node.js | 24.x |
| Python | 3.13+ |
| Next.js | 16.x |
| React | 19.x |
| NestJS | 11.x |
| PostgreSQL | 18.x (+ pgvector) |
| Redis | 8.x |
| Celery | 5.6.x |
| SQLAlchemy | 2.x |
| Drizzle | latest |
| Zod | 4.x |
| PM2 | 6.x |
| FastAPI | latest |
| React Three Fiber | latest |

---

## License

Proprietary — All rights reserved.

---

## Author

Lucas Moraes
(Q³ Project Founder)
