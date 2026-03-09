# Contributing — Q³ (Q-Cube)

Obrigado por contribuir com o Q³.

## 1. Pre-requisitos

- Node.js 24.x
- `pnpm` (via Corepack)
- Python 3.13+
- PostgreSQL 18 em execucao local (com extensao `pgvector`)
- Redis 8 em execucao local
- PM2 (`npm i -g pm2`)

## 2. Setup local

```bash
corepack enable
pnpm install
```

Para servicos Python:

```bash
cd services/quant-engine && python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

cd ../market-ingestion && python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

cd ../fundamentals-engine && python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

cd ../ai-assistant && python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Padrao Python do projeto:

- `src/` layout para pacotes
- imports absolutos
- execucao via modulo (`python -m q3_quant_engine` / `python -m q3_market_ingestion` / `python -m q3_fundamentals_engine` / `python -m q3_ai_assistant`)

Variaveis de ambiente:

```bash
cp .env.example .env
```

Chaves necessarias para AI (no `.env`):

```bash
Q3_AI_OPENAI_API_KEY=sk-...          # Required for council/chat
Q3_AI_ANTHROPIC_API_KEY=sk-ant-...   # Fallback provider
Q3_AI_GOOGLE_API_KEY=...             # Fallback provider
Q3_AI_BRAVE_SEARCH_API_KEY=...       # Optional, for web search
```

Bootstrap local completo (valida PostgreSQL/Redis e sobe PM2):

```bash
pnpm bootstrap:local
```

O script usa `.env` automaticamente e resolve host/porta a partir de `DATABASE_URL` e `REDIS_URL` (com fallback para `127.0.0.1:5432` e `127.0.0.1:6379`).

## 3. Estrutura do repositorio

```text
/apps
  /web                    → Next.js frontend (ranking, backtest, compare, chat, 3D viz)
  /api                    → NestJS backend (17 modules, Drizzle ORM)
/services
  /quant-engine           → Strategy execution, ranking, refiner, backtest, comparison (FastAPI + Celery)
  /fundamentals-engine    → CVM ingestion, normalization, metrics (FastAPI + Celery)
  /market-ingestion       → Data client adapters (brapi, CVM, Dados de Mercado)
  /ai-assistant           → AI Council, free chat, RAG, ranking explainer, backtest narrator (FastAPI + Celery)
/packages
  /shared-contracts       → Zod schemas — SSOT for API payloads (18 domain files)
  /shared-fundamentals    → Canonical keys, metric codes, domain enums (TypeScript)
  /shared-models-py       → SQLAlchemy models — SSOT for all Python services
  /shared-events          → Event schemas
  /shared-types           → Re-exported types from shared-contracts
```

## 4. Fluxo de trabalho

1. Crie uma branch a partir de `main`.
2. Implemente a mudanca com commits pequenos e claros.
3. Garanta lint, typecheck e testes locais.
4. Abra PR com descricao objetiva de problema/solucao.

Convencao de branch:

```text
feat/<escopo>-<resumo>
fix/<escopo>-<resumo>
chore/<escopo>-<resumo>
```

## 5. Convencao de commits

Padrao: Conventional Commits.

```text
feat(strategy): add magic formula ranking pipeline
fix(api): enforce tenant scope in strategy run list
feat(council): add Greenblatt specialist agent
chore(repo): add workspace typecheck script
```

## 6. Padroes de codigo

- TypeScript em modo strict
- Zod para contratos de entrada/saida
- Sem `any` sem justificativa tecnica
- Python com tipagem explicita (type hints + mypy)
- SQLAlchemy models compartilhados em `packages/shared-models-py`
- Logs estruturados (JSON) em componentes backend/worker
- Persistencia Node/NestJS via Drizzle ORM
- Persistencia Python via SQLAlchemy 2.x
- Migracoes via Alembic
- Nao usar SQL cru na camada de aplicacao
- AI: contratos Zod para input/output, disclaimers obrigatorios, custo rastreado por chamada

## 7. Testes

Minimo por PR:

- testes unitarios da logica alterada
- teste de integracao para fluxos criticos de API
- validacao de contrato (quando alterar SSOT)

Comandos:

```bash
pnpm lint
pnpm typecheck
pnpm test

# Python
cd services/quant-engine && python -m pytest
cd services/fundamentals-engine && python -m pytest
cd services/ai-assistant && python -m pytest
```

Banco de dados:

```bash
pnpm db:migrate
pnpm db:seed
```

## 8. Process manager (PM2)

10 processos gerenciados via `ecosystem.config.cjs`:

```bash
pnpm pm2:start          # Start all 10 processes
pnpm pm2:status
pnpm pm2:logs
pnpm pm2:stop
```

## 9. Contratos compartilhados (SSOT)

Qualquer alteracao de payload deve comecar por `packages/shared-contracts`.

Dominios existentes: strategy, backtest, refiner, council, chat, comparison, intelligence, ai, asset, auth, dashboard, jobs, portfolio, ranking, universe, user-context, versioning.

Checklist de mudanca de contrato:

1. Atualizar schema Zod em `shared-contracts`.
2. Atualizar tipos/exportacoes.
3. Atualizar consumidores (`web`, `api`, `python`).
4. Atualizar documentacao de API.

## 10. Pull Request

Todo PR deve conter:

- contexto do problema
- decisao tecnica adotada
- riscos/regressoes possiveis
- evidencias (logs, prints, metricas, testes)

Template sugerido:

```text
## Contexto

## Solucao

## Como testar

## Riscos

## Checklist
- [ ] lint
- [ ] typecheck
- [ ] testes
- [ ] docs atualizadas
```

## 11. Seguranca e dados

- Nunca comitar segredos/chaves.
- Usar `.env.example` para variaveis necessarias.
- Dados sensiveis devem ser mascarados em logs.
- AI: input sanitization + output guards em todos os modulos.
- Disclaimers CVM 20/178 obrigatorios em outputs do council.

## 12. Decisoes arquiteturais

Mudancas estruturais relevantes devem registrar ADR (Architecture Decision Record) em `docs/adr` (quando o diretorio for criado).
