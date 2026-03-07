# Tenant Audit

Scan all database queries in the codebase to verify tenant isolation. Every operation on a tenant-scoped table must filter by `tenantId`.

## Procedure

1. **Identify tenant-scoped tables** by reading:
   - `apps/api/src/db/schema.ts` — tables with a `tenantId` column
   - `services/quant-engine/src/q3_quant_engine/models/entities.py` — models with `tenant_id`
   - System tables without `tenantId` (e.g., `tenants`, `users`) are excluded from the audit

2. **Scan Drizzle queries** in `apps/api/src/`:
   - Search for `db.select()`, `db.insert()`, `db.update()`, `db.delete()`, `tx.select()`, `tx.insert()`, `tx.update()`, `tx.delete()`
   - For each query on a tenant-scoped table, verify that `.where()` includes an `eq(table.tenantId, ...)` condition
   - Flag any query that accesses a tenant-scoped table without tenant filtering

3. **Scan SQLAlchemy queries** in `services/quant-engine/src/`:
   - Search for `session.execute(select(...))`, `session.query(...)`, `session.get(...)`
   - For each query on a tenant-scoped model, verify the `.where()` includes `Model.tenant_id == ...`
   - Flag any query missing tenant scope

4. **Check insert operations**:
   - Every insert into a tenant-scoped table must include `tenantId` / `tenant_id`
   - Flag inserts that omit tenant assignment

5. **Check API endpoints**:
   - Verify that tenant ID comes from authenticated context (not request body alone in production)
   - Note: current MVP uses body input — flag as acceptable for now but note the future risk

6. **Report**:
   - List of all queries found, grouped by file
   - Status: PASS (tenant-scoped) or FAIL (missing tenant filter)
   - Summary count: X/Y queries properly scoped
   - Recommendations for any violations found

## Severity Levels

- **CRITICAL**: SELECT/UPDATE/DELETE without tenant filter — data leak across tenants
- **HIGH**: INSERT without tenant_id — orphaned or misassigned records
- **INFO**: System table access without tenant filter — expected, no action needed
