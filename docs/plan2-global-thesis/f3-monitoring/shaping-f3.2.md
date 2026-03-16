# Shape Up — F3.2: NestJS Proxy + Monitoring Dashboard

## Micro Feature
NestJS proxy for F3.1 monitoring endpoints + internal monitoring dashboard page with 4 cards.

## Shape
3 layers:
1. NestJS proxy: 4 endpoints that forward to quant-engine (:8100)
2. Web hooks: `useThesisMonitoring` for monitoring/drift/aging/review-queue
3. Web page: `/thesis/monitoring` with 4 cards

## Build Scopes

### Scope 1: NestJS proxy — DONE
- 4 new controller endpoints: `GET /thesis/monitoring`, `/monitoring/drift`, `/monitoring/rubric-aging`, `/monitoring/review-queue`
- Service methods proxy to `QUANT_ENGINE_URL` (defaults to `http://localhost:8100`)
- `getLatestRunId()` helper finds latest completed run for tenant
- Typecheck clean, build clean

### Scope 2: Web hooks — DONE
- `useThesisMonitoring.ts` with 4 hooks: `useMonitoringSummary`, `useDrift`, `useRubricAging`, `useReviewQueue`
- Full TypeScript types mirroring Python dataclasses
- Typecheck clean

### Scope 3: Dashboard page — DONE
- `/thesis/monitoring` page with 4 cards in 2x2 grid:
  - **Monitoring Summary**: evidence quality bar, provenance mix bar, dimension coverage table
  - **Drift**: bucket changes, top-10 changes, fragility deltas, entered/exited lists
  - **Rubric Aging**: stale count, stale by dimension, oldest stale rubrics table
  - **Review Queue**: priority summary (HIGH/MEDIUM/LOW counters), prioritized item table with reasons
- Sidebar nav item added ("Monitoring" with bar chart icon)
- Typecheck clean

## Validation
- `pnpm --filter @q3/api typecheck` — clean
- `pnpm --filter @q3/api build` — clean
- `pnpm --filter @q3/web typecheck` — clean
- `python -m pytest` (quant-engine) — 391 passed

## Files Changed
- `apps/api/src/thesis/thesis.controller.ts` — 4 new endpoints
- `apps/api/src/thesis/thesis.service.ts` — 5 new methods (getLatestRunId, getMonitoringSummary, getDrift, getRubricAging, getReviewQueue)
- `apps/web/src/hooks/api/useThesisMonitoring.ts` — NEW (4 hooks + types)
- `apps/web/app/(dashboard)/thesis/monitoring/page.tsx` — NEW (dashboard page with 4 cards)
- `apps/web/src/components/layout/Sidebar.tsx` — added Monitoring nav item

## Close Summary

F3.2 delivers the full monitoring dashboard stack:
- NestJS proxies to quant-engine F3.1 endpoints
- Web dashboard answers the 4 governance questions visually

Each card answers one question:
1. **Monitoring Summary** → "o quanto do ranking esta sustentado por cada tipo de evidencia"
2. **Drift** → "o que mudou desde a run anterior"
3. **Rubric Aging** → "quais rubricas estao velhas"
4. **Review Queue** → "o que precisa de revisao primeiro e por que" (com reasons explícitos)
