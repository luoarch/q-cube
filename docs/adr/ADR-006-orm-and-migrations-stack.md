# ADR-006: ORM and Migration Stack

## Status
Accepted

## Date
2026-03-07

## Context
O projeto Q³ precisa de uma base transacional consistente entre serviços Node e Python, evitando divergência de schema e removendo SQL cru da camada de aplicação.

## Decision
Adotar o padrão abaixo como obrigatório:

- API Node/NestJS: Drizzle ORM
- Serviços Python: SQLAlchemy 2.x (ORM/Core)
- Migrações de schema: Alembic

## Consequences

### Positivas
- melhor maintainability de acesso a dados
- tipagem forte no lado TypeScript e Python
- fluxo formal de migração versionada

### Negativas
- maior custo inicial de setup e tooling
- necessidade de disciplina para manter models/schema sincronizados

## Rules
- Não usar SQL cru na camada de aplicação.
- Toda alteração estrutural passa por migração Alembic.
- Contratos de API seguem SSOT em `packages/shared-contracts`.
