# Contributing — Q³ (Q-Cube)

Obrigado por contribuir com o Q³.

## 1. Pré-requisitos

- Node.js 24.x
- `pnpm` (via Corepack)
- Python 3.13+
- PostgreSQL 18 em execução local
- Redis 8 em execução local
- PM2 (`npm i -g pm2`)

## 2. Setup local

```bash
corepack enable
pnpm install
```

Para serviços Python:

```bash
cd services/quant-engine && python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

cd ../market-ingestion && python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Padrão Python do projeto:

- `src/` layout para pacotes
- imports absolutos
- execução via módulo (`python -m q3_quant_engine` / `python -m q3_market_ingestion`)

Variáveis de ambiente:

```bash
cp .env.example .env
```

Bootstrap local completo (valida PostgreSQL/Redis e sobe PM2):

```bash
pnpm bootstrap:local
```

O script usa `.env` automaticamente e resolve host/porta a partir de `DATABASE_URL` e `REDIS_URL` (com fallback para `127.0.0.1:5432` e `127.0.0.1:6379`).

## 3. Estrutura do repositório

```text
/apps
  /web
  /api
/services
  /quant-engine
  /market-ingestion
/packages
  /shared-contracts
  /shared-events
  /shared-types
```

## 4. Fluxo de trabalho

1. Crie uma branch a partir de `main`.
2. Implemente a mudança com commits pequenos e claros.
3. Garanta lint, typecheck e testes locais.
4. Abra PR com descrição objetiva de problema/solução.

Convenção de branch:

```text
feat/<escopo>-<resumo>
fix/<escopo>-<resumo>
chore/<escopo>-<resumo>
```

## 5. Convenção de commits

Padrão recomendado: Conventional Commits.

```text
feat(strategy): add magic formula ranking pipeline
fix(api): enforce tenant scope in strategy run list
chore(repo): add workspace typecheck script
```

## 6. Padrões de código

- TypeScript em modo strict
- Zod para contratos de entrada/saída
- Sem `any` sem justificativa técnica
- Python com tipagem explícita (Pydantic + mypy)
- Logs estruturados (JSON) em componentes backend/worker
- Persistência Node/NestJS via Drizzle ORM
- Persistência Python via SQLAlchemy 2.x
- Migrações via Alembic
- Não usar SQL cru na camada de aplicação

## 7. Testes

Mínimo por PR:

- testes unitários da lógica alterada
- teste de integração para fluxos críticos de API
- validação de contrato (quando alterar SSOT)

Comandos-alvo (a serem evoluídos):

```bash
pnpm lint
pnpm typecheck
pnpm test
```

Banco de dados:

```bash
pnpm db:migrate
pnpm db:seed
```

## 8. Process manager (PM2)

Comandos recomendados:

```bash
pnpm pm2:start
pnpm pm2:status
pnpm pm2:logs
pnpm pm2:stop
```

## 9. Contratos compartilhados (SSOT)

Qualquer alteração de payload deve começar por `packages/shared-contracts`.

Checklist de mudança de contrato:

1. Atualizar schema Zod.
2. Atualizar tipos/exportações.
3. Atualizar consumidores (`web`, `api`, `python`).
4. Atualizar documentação de API.

## 10. Pull Request

Todo PR deve conter:

- contexto do problema
- decisão técnica adotada
- riscos/regressões possíveis
- evidências (logs, prints, métricas, testes)

Template sugerido:

```text
## Contexto

## Solução

## Como testar

## Riscos

## Checklist
- [ ] lint
- [ ] typecheck
- [ ] testes
- [ ] docs atualizadas
```

## 11. Segurança e dados

- Nunca comitar segredos/chaves.
- Usar `.env.example` para variáveis necessárias.
- Dados sensíveis devem ser mascarados em logs.

## 12. Decisões arquiteturais

Mudanças estruturais relevantes devem registrar ADR (Architecture Decision Record) em `docs/adr` (quando o diretório for criado).
