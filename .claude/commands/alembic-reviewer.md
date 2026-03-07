# Alembic Reviewer

Review Alembic migrations for correctness by comparing them against both ORM schemas (Drizzle and SQLAlchemy).

## Input

The user points to a specific migration file, or asks to review the latest migration, or asks to check for schema drift.

## Procedure

### Mode 1: Review a specific migration

1. **Read the migration file** in `services/quant-engine/alembic/versions/`
2. **Read both ORM schemas**:
   - `apps/api/src/db/schema.ts` (Drizzle — the "readable reference")
   - `services/quant-engine/src/q3_quant_engine/models/entities.py` (SQLAlchemy — the "executable truth")
3. **Verify the migration matches**:
   - Every `op.create_table()` column matches both schemas
   - Column types are correct PostgreSQL types
   - Nullable/NOT NULL constraints are correct
   - Default values and server defaults are correct
   - Foreign keys point to correct targets with correct ON DELETE behavior
   - Indexes and unique constraints are present where defined in models
   - Enum types are created before tables that use them
4. **Verify downgrade**:
   - `downgrade()` is the exact reverse of `upgrade()`
   - Tables dropped in reverse order of creation (FK dependencies)
   - Enum types dropped after tables that use them
5. **Check for risks**:
   - Data loss operations (DROP COLUMN, DROP TABLE) flagged as WARNING
   - Non-reversible operations (ALTER TYPE ADD VALUE) noted
   - Missing `IF NOT EXISTS` / `IF EXISTS` guards where appropriate

### Mode 2: Detect schema drift

1. **Read all migration files** and reconstruct expected schema state
2. **Compare against SQLAlchemy models** — find tables/columns/enums that:
   - Exist in models but have no migration (missing migration)
   - Exist in migrations but not in models (orphaned migration)
   - Have different types/constraints between models and migrations
3. **Compare Drizzle vs SQLAlchemy**:
   - Every table in Drizzle must exist in SQLAlchemy and vice versa
   - Column names, types, nullable, defaults must match
   - Enum values must be identical
   - Foreign key relationships must match

## Report Format

```
## Migration Review: <filename>

### Tables
| Table | Status | Notes |
|-------|--------|-------|

### Columns
| Table.Column | Migration | SQLAlchemy | Drizzle | Match |
|-------------|-----------|------------|---------|-------|

### Enums
| Enum | Migration Values | SQLAlchemy Values | Drizzle Values | Match |
|------|-----------------|-------------------|----------------|-------|

### Risks
- [ ] ...

### Verdict: PASS / NEEDS FIX
```

## Rules

- A migration that doesn't match both ORMs is always a FAIL
- Drizzle ↔ SQLAlchemy drift is a FAIL even if the migration is correct (means one ORM is outdated)
- Enum value order matters in PostgreSQL — check that order is consistent
- `create_type=False` in SQLAlchemy means the enum is shared — verify it's created in an earlier migration
