# C1 — Source-Specific Data Origin

## Status: BUILD COMPLETE — Approved

---

## 1. Micro Feature

**Add provenance metadata to ranking and portfolio API responses, and display a ProvenanceFooter on each surface so the user can always answer: "where did this data come from?"**

---

## 2. Problem

After D1 (enforcement) and D2 (language), the remaining risk is **provenance confusion**:
- Portfolio shows "Top 10" but doesn't say from which run/config/date
- Ranking shows scores but doesn't say what data source or universe policy
- User can't distinguish stale results from current ones

---

## 3. Design

### API: `DataProvenance` schema

```typescript
dataProvenanceSchema = z.object({
  source: z.string(),             // 'compat_view' | 'strategy_run'
  runId: z.string().optional(),   // UUID of the run (portfolio)
  strategy: z.string().optional(), // strategy type
  runDate: z.string().optional(),  // when the run was executed
  asOfDate: z.string().optional(), // reference date
  topN: z.number().optional(),     // number of picks
  universePolicy: z.string().optional(), // 'v1'
  dataSource: z.string().optional(), // 'CVM filings + Yahoo snapshots'
});
```

### Ranking provenance

```json
{
  "source": "compat_view",
  "strategy": "magic_formula_brazil",
  "dataSource": "CVM filings + Yahoo snapshots",
  "universePolicy": "v1"
}
```

### Portfolio provenance

```json
{
  "source": "strategy_run",
  "runId": "abc-123",
  "strategy": "magic_formula_brazil",
  "runDate": "2026-03-20T15:30:00Z",
  "topN": 10,
  "universePolicy": "v1"
}
```

### ProvenanceFooter component

Compact monospace footer at bottom of data surfaces. Shows:
- Source (compat view / strategy run)
- Strategy used
- Run date + ID (for portfolio)
- Data source
- Universe policy

---

## 4. Surfaces covered

| Surface | Provenance source | Footer shows |
|---------|------------------|-------------|
| `/ranking` | API `provenance` field | Fonte: compat view, Estratégia: MF brazil, Dados: CVM+Yahoo, Universo: v1 |
| `/portfolio` | API `provenance` field | Run: date+time, Estratégia: MF brazil, Top 10, ID: abc123, Universo: v1 |

---

## 5. Close Summary

### Delivered

1. `DataProvenance` schema in `shared-contracts/domains/portfolio.ts`
2. `ProvenanceFooter` component in `src/components/ProvenanceFooter.tsx`
3. Ranking API returns provenance in `PaginatedRanking` response
4. Portfolio API returns provenance from `latestRun` metadata
5. `useRanking` hook returns `{data, provenance}` (not raw array)
6. 3D scenes updated for new ranking shape

### What did NOT change
- API computation logic
- Strategy registry
- Backtest engine
- Ranking algorithm

---

## 6. Tech Lead Handoff

### Files changed
- `packages/shared-contracts/src/domains/portfolio.ts` — DataProvenance schema
- `packages/shared-contracts/src/domains/ranking.ts` — provenance on PaginatedRanking
- `apps/api/src/ranking/ranking.controller.ts` — provenance in response
- `apps/api/src/portfolio/portfolio.service.ts` — provenance from latestRun
- `apps/web/src/components/ProvenanceFooter.tsx` — new component
- `apps/web/src/hooks/api/useRanking.ts` — returns {data, provenance}
- `apps/web/app/(dashboard)/ranking/page.tsx` — ProvenanceFooter added
- `apps/web/app/(dashboard)/portfolio/page.tsx` — ProvenanceFooter added
- 3D scenes: QCubeScene, RankingGalaxyScene — adapted to new ranking shape
