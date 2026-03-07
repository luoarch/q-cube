# Contract Propagator

Propagate a change in the Zod SSOT (`packages/shared-contracts`) to all consumers across the monorepo.

## Input

The user will describe a contract change (new field, renamed field, new schema, changed enum, etc.) or will have already edited a file in `shared-contracts`.

## Procedure

1. **Identify the change**:
   - Read the modified schema(s) in `packages/shared-contracts/src/domains/`
   - If not yet changed, apply the user's requested change to the Zod schema first
   - Determine what types/schemas were affected

2. **Find all consumers** by searching for imports of the changed exports:
   - Search `from "@q3/shared-contracts"` across all `.ts` files
   - Search for equivalent Python types in `services/*/src/`
   - Check `packages/shared-types/src/index.ts` for re-exports
   - Check `packages/shared-events/src/index.ts` for event schemas using the changed types

3. **Update TypeScript consumers**:
   - `apps/api/` — controllers, services: update `.parse()` calls, method signatures, response shapes
   - `apps/web/` — any type references, form schemas, API calls
   - `packages/shared-types/` — update re-exports if RunStatus or other re-exported types changed
   - `packages/shared-events/` — update event schemas if they reference changed types

4. **Update Python consumers**:
   - `services/quant-engine/src/q3_quant_engine/models/entities.py` — sync enum values if StrategyType/RunStatus/JobKind changed
   - `services/quant-engine/src/q3_quant_engine/tasks/strategy.py` — update task signatures/logic if event schema changed
   - If Pydantic models exist, update them to match the new Zod schema

5. **Update Drizzle schema** if enum values changed:
   - `apps/api/src/db/schema.ts` — pgEnum values must match Zod enum values exactly

6. **Build and typecheck**:
   - Run `pnpm --filter @q3/shared-contracts build`
   - Run `pnpm typecheck` to catch any remaining type errors across the workspace

7. **Report** a changelog:
   - What changed in the contract
   - Which files were updated
   - Any manual steps needed (e.g., migration for new enum values)

## Rules

- The Zod schema in `shared-contracts` is always the source of truth — never derive backwards
- If adding a new enum value, check if a DB migration is needed (new values in PostgreSQL enums require `ALTER TYPE ... ADD VALUE`)
- Re-exports in `shared-types` must use `export type { X } from "@q3/shared-contracts"` — never redefine
- When a field is added to a response schema, check if the Drizzle select and SQLAlchemy query return it
