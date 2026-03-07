# Q³ — Q-Cube

**Quantity • Quality • Quant Technology**

Q³ (Q-Cube) é uma plataforma de **pesquisa quantitativa para investimento em ações**, projetada para automatizar a seleção de ativos utilizando **métodos quantitativos disciplinados**.

A plataforma combina três pilares:

```text
Quantity
Quality
Quant Technology
```

O objetivo é eliminar vieses emocionais e permitir **análise sistemática e reproduzível de estratégias de investimento**.

---

## Visão

Q³ é um **Quant Strategy Lab** capaz de:

- analisar todas as ações da B3
- executar estratégias quantitativas
- gerar rankings de ativos
- rodar backtests históricos
- comparar estratégias
- analisar carteiras pessoais

Inicialmente o sistema implementa a **Magic Formula** de Joel Greenblatt e suas variações.

---

## Arquitetura

Arquitetura **polyglot orientada a quant research**.

```text
Next.js (Frontend)
      ↓
NestJS (Application Backend)
      ↓
Redis Queue
      ↓
Python Quant Engine (Workers)
      ↓
PostgreSQL + Parquet
```

Essa separação permite:

- alta escalabilidade
- execução paralela de estratégias
- desacoplamento entre produto e motor quantitativo

---

## Stack Tecnológica

### Frontend

- Next.js **16.x**
- React **19**
- TypeScript
- TailwindCSS
- TanStack Query

Next.js 16 introduziu melhorias importantes de performance, caching e integração com React moderno. ([Next.js][1])

### Runtime

- Node.js **24.x**

Node 24 é a versão corrente recomendada para aplicações modernas.

### Backend (Application Layer)

- NestJS **11.x**
- TypeScript
- Zod
- Drizzle ORM

Responsável por:

- autenticação
- RBAC
- multi-tenant
- API pública
- orquestração de jobs

### Quant Engine

- Python **3.13**
- FastAPI
- Pydantic **2.x**
- SQLAlchemy **2.x**
- Alembic

FastAPI é amplamente usado para APIs de alta performance em Python. ([Medium][2])

### Workers / Processing

- Celery **5.6**
- Redis **8**

Celery é usado para execução de tarefas distribuídas e processamento paralelo. ([Celery Documentation][3])

### Banco de Dados

- PostgreSQL **18**

Armazena:

- dados de mercado
- usuários
- estratégias
- resultados

### Analytics Storage

- Apache Parquet

Utilizado para:

- séries históricas
- snapshots de mercado
- datasets de backtest

### Observabilidade

- OpenTelemetry
- Prometheus
- Grafana

---

## Estrutura do Repositório

Monorepo.

```text
/apps
  /web        → Next.js frontend
  /api        → NestJS backend

/services
  /quant-engine
  /market-ingestion

/packages
  /shared-contracts
  /shared-events
  /shared-types
```

---

## Shared Contracts (SSOT)

O sistema utiliza **Single Source of Truth** para contratos compartilhados.

Todos os schemas são definidos em:

```text
packages/shared-contracts
```

Tecnologia:

```text
TypeScript + Zod
```

Esses contratos são consumidos por:

- Next.js
- NestJS
- Python (via geração de schemas)

Domínios do SSOT:

```text
auth
tenancy
rbac
market
portfolio
strategy
backtest
jobs
events
errors
```

---

## Estratégias Quantitativas

### 1 — Magic Formula (Original)

Baseada no livro de Joel Greenblatt.

Indicadores:

```text
Earnings Yield = EBIT / Enterprise Value
Return on Capital = EBIT / (NWC + Fixed Assets)
```

Ranking:

```text
Rank(EY) + Rank(ROC)
```

### 2 — Magic Formula Brasil

Filtros adicionais:

```text
excluir financeiras
excluir utilities
liquidez mínima
market cap mínimo
EBIT positivo
```

### 3 — Magic Formula Híbrida

Inclui fatores adicionais:

```text
quality score
momentum
ROIC
Debt / EBITDA
margin stability
```

Objetivo: reduzir **value traps**.

---

## Backtesting

O sistema permite simular estratégias em três cenários:

### Full Cycle

```text
10 anos de mercado
```

Inclui bull markets e crises.

### Stress Test

Simulações em períodos de crise.

Exemplos:

```text
2008
2020
```

### Recovery

Períodos de recuperação pós-crise.

Backtests geram:

```text
CAGR
Sharpe Ratio
Max Drawdown
Volatility
Hit Rate
```

---

## Execução de Estratégias

Execução assíncrona.

```text
User triggers strategy
        ↓
NestJS validates request
        ↓
StrategyRun created
        ↓
Job published to Redis
        ↓
Python worker processes
        ↓
Results persisted
        ↓
User notified
```

---

## Multi-Tenant

Sistema projetado para múltiplos usuários.

Entidades principais:

```text
Tenant
User
Membership
Role
Portfolio
BrokerConnection
```

Papéis:

```text
owner
admin
member
viewer
```

---

## Padrões Arquiteturais

O sistema utiliza padrões **GoF** e padrões arquiteturais modernos.

Principais:

- Strategy
- Template Method
- Factory
- Adapter
- Facade
- Command
- Observer
- State
- Chain of Responsibility
- Specification
- Repository

---

## Roadmap

### Fase 1 — MVP

- autenticação
- universo da B3
- Magic Formula original
- ranking de ações
- execução de estratégias

### Fase 2

- Magic Formula Brasil
- Magic Formula híbrida
- filtros avançados de qualidade

### Fase 3

- backtests avançados
- comparação de estratégias
- onboarding multi-usuário

---

## Filosofia do Projeto

Q³ segue três princípios fundamentais:

```text
Disciplina quantitativa
Reprodutibilidade
Arquitetura modular
```

O objetivo é construir uma **plataforma evolutiva de pesquisa quantitativa**, não apenas um screener de ações.

---

## Decisão de Persistência

Padrão oficial:

- Node/NestJS: Drizzle ORM
- Python services: SQLAlchemy 2.x
- Migrações: Alembic

Regra: evitar SQL cru na camada de aplicação.

---

## Licença

Proprietary — All rights reserved.

---

## Autor

Lucas Moraes  
(Q³ Project Founder)

---

[1]: https://nextjs.org/blog/next-16 "Next.js 16"
[2]: https://medium.com/%40faizulkhan56/building-advanced-fastapi-applications-a-comprehensive-guide-to-middleware-versioning-and-04d0b49769b4 "Building advanced FastAPI applications"
[3]: https://docs.celeryq.dev/en/main/changelog.html "Celery changelog"
