# Schema Sync

Synchronize a database table definition across the three persistence layers of the Q3 monorepo.

## Input

The user will describe a table (name, columns, types, constraints, relations). If they provide only one layer (e.g., just the Drizzle definition), derive the other two from it.

## Procedure

1. **Read current state** of all three files in parallel:
   - `apps/api/src/db/schema.ts` (Drizzle ORM)
   - `packages/shared-models-py/src/q3_shared_models/entities.py` (SQLAlchemy 2.x)
   - Latest migration in `services/quant-engine/alembic/versions/`

2. **Generate/update the Drizzle definition** in `schema.ts`:
   - Use existing enum patterns (`pgEnum`)
   - UUID PKs via `uuid().defaultRandom().primaryKey()`
   - `createdAt` / `updatedAt` with `timestamp({ withTimezone: true })`
   - Foreign keys with `references(() => tenants.id)` and `onDelete: "cascade"` where appropriate
   - Always include `tenantId` column for tenant-scoped tables

3. **Generate/update the SQLAlchemy model** in `entities.py`:
   - Mirror the exact same columns, types, enums, and constraints
   - Use `Mapped[]` type hints and `mapped_column()`
   - Enums as `str, enum.Enum` classes
   - UUID via `UUID(as_uuid=True)`
   - DateTime with `timezone=True`
   - Reuse existing enums (e.g., `RunStatus`) — do not duplicate

4. **Generate Alembic migration**:
   - Create a new file in `services/quant-engine/alembic/versions/`
   - Naming: `YYYYMMDD_NNNN_<description>.py`
   - Include `upgrade()` with `op.create_table()` / `op.add_column()` etc.
   - Include `downgrade()` with the reverse operations
   - If new enums are needed, create them with `op.execute("CREATE TYPE ...")`

5. **Validate consistency**:
   - Column names match (snake_case in both)
   - Types are equivalent (e.g., Drizzle `text()` ↔ SQLAlchemy `Text`)
   - Nullable/not-null match
   - Default values match
   - Foreign key targets match
   - Enum values are identical

6. **Report** a summary table showing the column mapping across all three layers.

## Rules

- Never add a table without `tenantId` unless it's a system-level table (like `tenants` itself)
- Enums shared across tables must be defined once and reused
- SQLAlchemy enum columns that reuse an existing DB enum must use `create_type=False`
- The Drizzle schema is the "readable reference"; the SQLAlchemy model is the "executable truth"; the migration is the "deployment artifact"
