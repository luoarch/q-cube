# Strategy Scaffold

Scaffold all the boilerplate needed to add a new quantitative strategy to the Q3 platform.

## Input

The user provides:
- **Strategy name** in snake_case (e.g., `graham_net_net`)
- **Description** (optional) — what the strategy does
- **Ranking indicators** (optional) — which financial metrics it uses

## Procedure

1. **Update Zod enum** in `packages/shared-contracts/src/domains/strategy.ts`:
   - Add the new value to `strategyTypeSchema` z.enum array

2. **Update SQLAlchemy enum** in `packages/shared-models-py/src/q3_shared_models/entities.py`:
   - Add new member to `StrategyType(str, enum.Enum)`

3. **Update Drizzle enum** in `apps/api/src/db/schema.ts`:
   - Add new value to `strategyTypeEnum` pgEnum array

4. **Create Alembic migration** for the new enum value:
   - New file in `services/quant-engine/alembic/versions/`
   - `upgrade()`: `op.execute("ALTER TYPE strategy_type ADD VALUE IF NOT EXISTS '<name>'")`
   - `downgrade()`: comment explaining PostgreSQL cannot remove enum values (note only)

5. **Add Celery task handler** in `services/quant-engine/src/q3_quant_engine/tasks/strategy.py`:
   - Add strategy-specific logic branch or create a dedicated task function
   - Follow existing pattern: receive `(job_id, run_id, tenant_id, strategy)`, update DB status, return result

6. **Build and verify**:
   - `pnpm --filter @q3/shared-contracts build`
   - `pnpm --filter @q3/api typecheck`
   - Verify enum values are consistent across all three layers

7. **Report**:
   - List of all files modified
   - The new enum value added
   - Reminder: run `pnpm db:migrate` after deploying the migration

## Rules

- Strategy names are always snake_case
- The Zod enum is the SSOT — update it first, then propagate
- Never modify the Celery task signature — new strategies use the same `run_strategy_task` with branching on `strategy` parameter
- Alembic migration for enum values must use `IF NOT EXISTS` for idempotency
