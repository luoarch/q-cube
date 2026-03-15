# Shaping: Complete Frontend Feature Gaps (Portfolio + Dashboard)

## 1. Micro Feature

**Complete the two missing frontend pages** -- Portfolio (stub) and Dashboard (nonexistent) -- consuming their already-implemented APIs.

## 2. Problem

Two backend APIs are fully built and tested but have no usable frontend:
- `GET /portfolio` returns top-10 holdings, factor tilts, totals -- but the page is just a 3D scene with zero data UI.
- `GET /dashboard/summary` returns KPIs, pipeline status, top ranked, sector distribution -- but no page exists at all.

Users cannot see portfolio composition or a system overview without these pages.

## 3. Outcome

- `/portfolio` shows holdings table, allocation stats, and factor tilt -- with the existing 3D constellation below the data section.
- `/dashboard` shows KPI cards, pipeline status indicator, top-5 ranked table, and sector distribution -- following established page patterns.
- Both pages are visually consistent with the existing dark-theme design system.

## 4. Why Now

These are the only two frontend gaps identified in the full feature review. All other 10 pages are fully functional end-to-end.

## 5. Current System Summary

### Portfolio (`/portfolio`)
- **Page**: `apps/web/app/(dashboard)/portfolio/page.tsx` -- 23 lines, renders only `PortfolioConstellationScene` (3D). No data UI.
- **Hook**: `apps/web/src/hooks/api/usePortfolio.ts` -- exists, calls `GET /portfolio`, returns `PortfolioData`. Already consumed by 3D scene.
- **API**: `apps/api/src/portfolio/portfolio.service.ts` -- queries latest completed strategy run, extracts top 10 tickers, builds equal-weight holdings with ROIC/market cap from `financialStatements`, computes factor tilts (ROIC, Quality). Returns validated `PortfolioData`.
- **3D Scene**: `apps/web/src/components/three/scenes/PortfolioConstellationScene.tsx` -- positions holdings in 3D by weight/sector, calls `usePortfolio()` internally. Self-contained (SceneCanvas, SceneCamera, SceneControls, SceneLights, AssetParticle, ConnectionLine). Handles own loading overlay and error state.
- **Schema**: `packages/shared-contracts/src/domains/portfolio.ts`

### Dashboard
- **Page**: Does NOT exist. No directory `apps/web/app/(dashboard)/dashboard/`.
- **Hook**: Does NOT exist. No `useDashboard.ts` in `apps/web/src/hooks/api/`.
- **API**: `apps/api/src/dashboard/dashboard.service.ts` -- 3 SQL queries (asset count, avg metrics, latest run) + ranking service call. Returns validated `DashboardSummary`. Cached 5 min via Redis.
- **Schema**: `packages/shared-contracts/src/domains/dashboard.ts`

### Sidebar
- **File**: `apps/web/src/components/layout/Sidebar.tsx`
- **Current nav**: Home | Strategy | Ranking | Universe | Compare | Portfolio | Backtest | AI Council (8 items in `NAV_ITEMS` array)
- **Footer**: Profile
- Portfolio already listed at `/portfolio` (wallet icon)
- No Dashboard entry exists

### Canonical UI Reference Files

| Pattern | Reference file | Lines |
|---------|----------------|-------|
| StatCard (bg-surface, border, 8px radius, gold monospace value) | `universe/page.tsx` | 16-38 |
| SectorBar (table row with horizontal bar) | `universe/page.tsx` | 40-62 |
| Page shell (.dashboard-page > .dashboard-header > content) | `universe/page.tsx` | 93-226 |
| Filter bar (inline inputs, selects, bg-canvas) | `ranking/page.tsx` | 61-111 |
| Data table (ranking-table class, sticky headers, row hover) | `ranking/page.tsx` | 120-182 |
| Ticker link (accent-gold, fontWeight 600, to /assets/:ticker) | `ranking/page.tsx` | 141-145 |
| Quality badge (colored pill, 11px, border-radius 10) | `ranking/page.tsx` | 162-173 |
| MetricCard (bg-canvas variant of StatCard) | `assets/[ticker]/page.tsx` | 26-48 |
| FactorBar (label + progress bar + % label) | `assets/[ticker]/page.tsx` | 50-71 |
| Loading state (centered text, text-secondary) | `universe/page.tsx` | 102-105 |
| Empty/error state (centered text, text-secondary) | `universe/page.tsx` | 106-109 |
| Hero StatChip (glassmorphic, smaller values) | `home/page.tsx` | 13-32 |
| Primary button (accent-gold bg, dark text) | `home/page.tsx` | 76-86 |
| Secondary button (glassmorphic, border-color) | `home/page.tsx` | 89-100 |

Components to **reuse as-is** from asset detail page:
- `FactorBar` pattern (label + bar + %) -- copy inline, identical structure to `assets/[ticker]/page.tsx:50-71`

Components to **replicate from pattern** (local to each page, per existing convention):
- `StatCard` -- same structure as `universe/page.tsx:16-38`
- Table layout -- same structure as `ranking/page.tsx:120-182`

**Convention**: Every existing page defines its helper components (StatCard, SectorBar, MetricCard, FactorBar) inline as local functions in the same file. No shared component library. This shaping follows the same pattern.

## 6. Requirements

### Portfolio Page
- R1: Show totalValue and totalReturn as StatCards at the top
- R2: Holdings table with columns: ticker (gold link), name, sector, weight%, value (BRL formatted), return%
- R3: Factor tilt bars (reuse FactorBar pattern from asset detail)
- R4: 3D constellation scene below data section, height-constrained (400px)
- R5: Empty state when holdings array is empty
- R6: Loading state while fetching
- R7: Error state on request failure

### Dashboard Page
- R8: KPI cards grid (4 cards from kpis array)
- R9: Pipeline status section (stage badge + progress bar + lastRun timestamp)
- R10: Top-5 ranked assets table (rank, ticker link, name)
- R11: Sector distribution table with horizontal bars (reuse SectorBar pattern from universe)
- R12: Loading state
- R13: Error state
- R14: Add "Dashboard" to sidebar navigation

## 7. Candidate Shapes

### Shape A: Data-First (tables + cards, no new 3D)
- Portfolio: stat cards + holdings table + factor bars above, 3D scene below (height-capped)
- Dashboard: KPI cards + pipeline section + top-5 table + sector bars
- Follows existing inline-component-per-page convention exactly
- Pros: Simple, fast, zero new dependencies, pattern-proven
- Cons: Dashboard could feel sparse without charts

### Shape B: Rich Dashboard (charts + visual indicators)
- Portfolio: Same as A
- Dashboard: KPI cards + animated pipeline gauge + top-5 with sparklines + SVG pie for sectors
- Pros: Visually richer
- Cons: Needs chart library or custom SVG work, exceeds gap-fill appetite

## 8. Selected Shape

**Shape A: Data-First** -- follows existing patterns exactly, zero new dependencies, proven by 10 existing pages.

## 9. Appetite

- **Level**: Small-Medium -- max 1 session, but with tight spec
- **Why this appetite is enough**: Both APIs return all data. Frontend is pure consumption + layout. All UI patterns are proven in existing pages. No new components, no new libraries. The main work is wiring data to established visual patterns.
- **Must-fit items**: R1-R14 (all requirements)
- **First cuts if exceeded**:
  1. Factor tilt bars (R3) -- degrade to plain text "ROIC: 15.2% | Quality: 80%"
  2. Sector distribution bars (R11) -- degrade to plain count column without visual bar
  3. 3D scene height constraint (R4) -- remove 3D scene entirely, link to standalone 3D view

## 10. Boundaries / No-Gos / Out of Scope

### Boundaries
- **Files touched**:
  - CREATE `apps/web/src/hooks/api/useDashboard.ts`
  - CREATE `apps/web/app/(dashboard)/dashboard/page.tsx`
  - REWRITE `apps/web/app/(dashboard)/portfolio/page.tsx`
  - EDIT `apps/web/src/components/layout/Sidebar.tsx` (1 object added to NAV_ITEMS)
- Reuse existing CSS variables and inline style patterns from reference files

### No-Gos
- No API changes (backend is final and tested)
- No new npm dependencies
- No schema changes in shared-contracts
- No modifications to PortfolioConstellationScene.tsx (3D scene is self-contained)
- No CSS modules (follow inline style convention of universe/ranking/assets pages)
- No shared component extraction (follow per-page local component convention)

### Out of Scope
- Portfolio equity curve (API returns null -- future feature)
- Dashboard real-time updates / WebSocket / polling
- Dashboard customization (drag/reorder cards)
- Portfolio rebalancing UI
- Mobile-specific responsive breakpoints beyond basic grid auto-fill

## 11. Rabbit Holes / Hidden Risks

| Risk | Analysis | Mitigation |
|------|----------|------------|
| Double fetch: page + 3D scene both call usePortfolio() | React Query deduplicates by queryKey `['portfolio']`. Verified: both call `apiClient.get<PortfolioData>('/portfolio')` with same key. Single HTTP request, shared cache. | No action needed. Proven by React Query design. |
| KPI `value` is `number \| string` union | API service (`dashboard.service.ts:54-59`) always produces numbers for current KPIs. The union exists for forward compatibility. `format` field is always set: `'number'` or `'percent'`. | Render: if `format === 'percent'`, show `${value}%`; if `format === 'number'`, show `String(value)`; else `String(value)`. |
| `price` and `change` in topRanked are nullable | RankingService may return null for these when market data is missing (see staleness policy). | Show "---" for null values. These fields are not critical for dashboard overview. |
| `factorTilt[].max` could be 0 | API service always sets `max: 100` (see `portfolio.service.ts:115-121`). But defensive check is cheap. | Guard: `const pct = max > 0 ? Math.min(value / max, 1) : 0`. Same pattern as `assets/[ticker]/page.tsx:51`. |
| `pipelineStatus.stage` is free string | API produces: `'idle'`, `'pending'`, `'running'`, `'completed'`, `'failed'` (matches RunStatus enum). | Map to colors: completed=#22c55e, running=#3b82f6, pending=#fbbf24, failed=#ef4444, idle=#94a3b8. |
| `pipelineStatus.lastRun` is nullable | Null when no strategy runs exist for tenant. | Show "Nenhuma execucao" when null. |
| `pipelineStatus.progress` could be unexpected value | API produces exactly 0, 50, or 100. | Clamp: `Math.min(Math.max(progress, 0), 100)`. |
| Sidebar position for Dashboard | See justification in section 12E. | Add as first item in NAV_ITEMS array. |

## 12. Data Contracts (Field-Level Rendering Spec)

### A. PortfolioData (from `GET /portfolio`)

```
{
  totalValue: number        // sum of (marketCap * weight) per holding. Can be 0.
                            // Format: BRL currency. Use formatNumber() from universe pattern.
                            // Fallback: "R$ 0" when 0.

  totalReturn: number       // avg ROIC * 100, rounded to 2 decimals. Can be 0.
                            // Format: percentage. Show as "{value}%".
                            // Fallback: "0.00%" when 0.

  holdings: Array<{
    ticker: string          // Always non-empty. Gold link to /assets/{ticker}.
    name: string            // Always non-empty. Company name, truncated with ellipsis if long.
    sector: string          // Always non-empty. May be "Sem Setor" for unknowns.
    weight: number          // Already in % (e.g. 10.00 for 10%). Equal-weight = 100/n.
                            // Format: "{value.toFixed(1)}%"
    value: number           // marketCap * weight. Can be 0 if no market data.
                            // Format: BRL currency via formatNumber().
                            // Fallback: "R$ 0" when 0.
    return: number          // ROIC * 100, rounded to 2 decimals. Can be 0.
                            // Format: "{value.toFixed(2)}%"
                            // Color: green (#22c55e) if > 0, red (#ef4444) if < 0, default if 0.
  }>                        // Max 10 items. Empty array when no completed strategy run.

  equityCurve: null         // Always null in current API. Not rendered.

  factorTilt: Array<{
    name: string            // "ROIC" or "Quality". Always non-empty.
    value: number           // 0-100 scale. ROIC = avgRoic*100. Quality = 20|50|80.
    max: number             // Always 100 in current API.
                            // Render: bar width = (value/max)*100%, clamped.
                            // Color: green if >70%, gold if >40%, red otherwise.
  }>                        // Currently always 2 items. Empty array if no holdings.
}
```

### B. DashboardSummary (from `GET /dashboard/summary`)

```
{
  kpis: Array<{
    label: string           // "Total Assets" | "Avg ROC" | "Avg EY" | "Strategy Runs"
                            // Rendered as uppercase 11px secondary text.
    value: number | string  // Currently always number from API.
                            // Format depends on `format` field.
    change?: number         // Optional. Not currently produced by API. Not rendered.
    positive?: boolean      // Optional. Not currently produced by API. Not rendered.
    format?: string         // "number" or "percent". Always present from current API.
                            // "number" -> String(value)
                            // "percent" -> "{value}%"
                            // undefined -> String(value)
  }>                        // Always 4 items from current API. Render as grid.

  pipelineStatus: {
    stage: string           // "idle" | "pending" | "running" | "completed" | "failed"
                            // Badge color mapping:
                            //   completed -> #22c55e (green)
                            //   running   -> #3b82f6 (blue)
                            //   pending   -> #fbbf24 (gold)
                            //   failed    -> #ef4444 (red)
                            //   idle      -> #94a3b8 (gray)
                            // Label: capitalize first letter.
    progress: number        // 0 | 50 | 100. Clamp to [0, 100].
                            // Render: progress bar width as percentage.
                            // Bar bg: var(--grid-color). Fill: same color as stage badge.
    lastRun: string | null  // ISO 8601 timestamp or null.
                            // null -> "Nenhuma execucao"
                            // string -> format as "DD/MM/YYYY HH:mm" (pt-BR convention)
  }

  topRanked: Array<{
    ticker: string          // Always non-empty. Gold link to /assets/{ticker}.
    name: string            // Always non-empty. Truncated with ellipsis.
    rank: number            // Magic formula rank. Always positive integer.
                            // Render in first column, centered, secondary text.
    price: number | null    // Nullable. Format: "R$ {value.toFixed(2)}". Null -> "---".
    change: number | null   // Nullable. Not rendered in V1 (dashboard is overview, not quotes).
  }>                        // 0-5 items. Empty when no ranking data.

  sectorDistribution: Array<{
    name: string            // Sector name. "Sem Setor" for unknowns.
    value: number           // Count of assets in sector. Always >= 1.
                            // Render: horizontal bar proportional to max value.
                            // Bar pattern identical to SectorBar in universe/page.tsx:40-62.
  }>                        // 0-N items. Empty when no ranking data.
                            // Sort: by value descending before rendering.
}
```

## 13. State Matrix

### Portfolio Page States

| State | Condition | Render |
|-------|-----------|--------|
| **Loading** | `isLoading === true` | `.dashboard-page` > header > centered "Carregando portfolio..." in text-secondary |
| **Error** | `isLoading === false && error` | `.dashboard-page` > header > centered "Erro ao carregar portfolio." in #ef4444 |
| **Empty** | `data.holdings.length === 0` | `.dashboard-page` > header > centered "Nenhum portfolio disponivel. Execute uma estrategia primeiro." in text-secondary. Link to /strategy. No stat cards, no table, no 3D scene. |
| **Success** | `data.holdings.length > 0` | Full render: stat cards + table + factor bars + 3D scene |
| **Partial: value=0** | `data.totalValue === 0 && holdings exist` | Stat card shows "R$ 0". Table renders normally. This is valid (no market data). |
| **Partial: factorTilt empty** | `data.factorTilt.length === 0` | Factor section not rendered. Rest of page renders normally. |
| **Partial: max=0 in factor** | `factorTilt[n].max === 0` | Bar width = 0%. Shows "0%" label. Does not divide by zero. |

### Dashboard Page States

| State | Condition | Render |
|-------|-----------|--------|
| **Loading** | `isLoading === true` | `.dashboard-page` > header > centered "Carregando dashboard..." in text-secondary |
| **Error** | `isLoading === false && error` | `.dashboard-page` > header > centered "Erro ao carregar dashboard." in #ef4444 |
| **Success** | `data exists` | Full render: KPIs + pipeline + top ranked + sector dist |
| **Empty KPIs** | `data.kpis.length === 0` | KPI grid not rendered. Rest renders. (Unlikely -- API always returns 4.) |
| **Empty topRanked** | `data.topRanked.length === 0` | Top ranked section shows "Nenhum ativo ranqueado." in text-secondary. |
| **Empty sectorDist** | `data.sectorDistribution.length === 0` | Sector section shows "Sem dados de setor." in text-secondary. |
| **Pipeline idle** | `stage === 'idle' && lastRun === null` | Gray "Idle" badge, progress bar at 0%, "Nenhuma execucao" timestamp. |
| **Pipeline failed** | `stage === 'failed'` | Red "Failed" badge, progress bar at 0% (red), lastRun timestamp shown. |
| **Progress out of range** | `progress < 0 \|\| progress > 100` | Clamped to [0, 100] before rendering. |

## 14. Component Composition

### Dashboard Page (`dashboard/page.tsx`)

```
DashboardPage (default export, 'use client')
|
|-- Local helpers:
|   |-- formatKpiValue(value, format) -> string
|   |-- formatDate(iso) -> string (DD/MM/YYYY HH:mm)
|   |-- STAGE_COLORS: Record<string, string>
|
|-- Local components:
|   |-- KpiCard({ label, value, format })
|   |   Pattern source: universe/page.tsx StatCard (lines 16-38)
|   |   Difference: value formatting uses format field
|   |
|   |-- PipelineStatus({ stage, progress, lastRun })
|   |   Unique to this page. Contains:
|   |   - Stage badge (colored pill, 11px, same pattern as QualityBadge)
|   |   - Progress bar (same pattern as SectorBar's bar: grid-color bg, colored fill)
|   |   - Timestamp or fallback text
|   |
|   |-- SectorBar({ name, count, maxCount })
|   |   Pattern source: universe/page.tsx SectorBar (lines 40-62)
|   |   Simplified: no marketCap column (API doesn't provide it here)
|
|-- Page structure:
|   .dashboard-page
|     header.dashboard-header "Dashboard" + subtitle
|     Loading | Error | Content:
|       KPI grid (auto-fill, minmax 200px)
|       Pipeline section (bg-surface card)
|       Top ranked section (bg-surface card with table)
|       Sector distribution section (bg-surface card with table)
```

**Why these local components**:
- `KpiCard`: same as StatCard but with format-aware value rendering. Defined locally per existing convention (universe defines StatCard locally, assets defines MetricCard locally).
- `PipelineStatus`: unique widget, no existing pattern to reuse. Must be local.
- `SectorBar`: simplified copy of universe's SectorBar (2 columns instead of 4). Local per convention.

### Portfolio Page (`portfolio/page.tsx`)

```
PortfolioPage (default export, 'use client')
|
|-- Local helpers:
|   |-- formatNumber(n) -> string (BRL currency, same as universe/page.tsx)
|   |-- formatPercent(n) -> string
|
|-- Local components:
|   |-- StatCard({ label, value, subtitle? })
|   |   Pattern source: universe/page.tsx StatCard (lines 16-38). Identical.
|   |
|   |-- FactorBar({ name, value, max })
|   |   Pattern source: assets/[ticker]/page.tsx FactorBar (lines 50-71). Identical.
|
|-- Existing import (dynamic, SSR disabled):
|   |-- PortfolioConstellationScene (from three/scenes/)
|       Self-contained: calls usePortfolio() internally, handles own loading/error.
|       NOT modified. Rendered below data section, height-capped at 400px.
|
|-- Page structure:
|   .dashboard-page
|     header.dashboard-header "Portfolio" + subtitle
|     Loading | Error | Empty | Content:
|       Stat cards grid (2 cards: Total Value, Total Return)
|       Holdings table (bg-surface card with table)
|       Factor tilt section (bg-surface card with FactorBars) -- conditional on factorTilt.length > 0
|       3D scene container (height: 400px, border-top) -- conditional on holdings.length > 0
```

**Why this structure**:
- StatCard and FactorBar are proven patterns copied from their reference files. Each existing page defines them locally -- we follow the same convention.
- PortfolioConstellationScene is imported unchanged. It already calls usePortfolio() and React Query deduplicates.
- The 3D scene is placed below data (not above) so the data UI is immediately visible without scrolling.
- Height cap (400px) ensures the scene doesn't push content off-screen while still being visible.

### Sidebar Change

```
Sidebar.tsx NAV_ITEMS array:
  BEFORE: [Home, Strategy, Ranking, Universe, Compare, Portfolio, Backtest, AI Council]
  AFTER:  [Dashboard, Home, Strategy, Ranking, Universe, Compare, Portfolio, Backtest, AI Council]

Single object insertion at index 0:
{
  href: '/dashboard',
  label: 'Dashboard',
  icon: <svg ... /> (grid/dashboard icon, 20x20, stroke style matching existing icons)
}
```

## 15. Navigation & UX Justification

### Dashboard as first sidebar item

**Evidence**: The current first item is Home (`/home`), which is a hero/landing page with 3D background and 3 stat chips. It serves as a brand entry point, not an operational overview.

Dashboard is the **system overview** page (KPIs, pipeline status, rankings). In every existing analytics platform (Grafana, Datadog, Metabase, PostHog), the dashboard/overview is the first nav item. Placing it first follows the established convention of "overview first, then drill-down pages."

Home remains the second item -- it's the brand/welcome page, accessed less frequently during active use.

### Ticker links to /assets/:ticker

**Evidence**: `apps/web/app/(dashboard)/assets/[ticker]/page.tsx` is fully implemented (208 lines). It handles loading, empty, and full render states. Already linked from ranking page (`ranking/page.tsx:141-145`). The route is stable and tested.

### 3D scene as bottom section in Portfolio

**Evidence**: The current portfolio page is 100% 3D scene. Replacing it entirely would lose the visual investment. But the 3D scene provides no data at a glance -- it requires mental parsing of spatial positions.

Placing data first (stat cards + table) gives immediate value. The 3D scene below serves as supplementary visualization for users who want spatial sector clustering. Height cap at 400px ensures:
- Data is above the fold
- Scene is visible without requiring a toggle/tab
- No layout competition between data and 3D

This mirrors the asset detail page pattern where data (MetricCards + FactorBars) comes first, and any visual element (Factor Analysis section) comes after.

### Sector distribution as bars (not pie chart)

**Evidence**: `universe/page.tsx:40-62` already implements `SectorBar` with horizontal bars. Reusing this proven pattern is more consistent than introducing a pie chart (which would require SVG or a chart library, violating the no-new-dependencies boundary).

## 16. Build Scopes

### Scope 1: Dashboard Page (NEW)

- **Objective**: Create `/dashboard` page + hook + sidebar entry
- **Files**:
  - CREATE `apps/web/src/hooks/api/useDashboard.ts`
  - CREATE `apps/web/app/(dashboard)/dashboard/page.tsx`
  - EDIT `apps/web/src/components/layout/Sidebar.tsx` (add 1 object at index 0 of NAV_ITEMS)
- **Dependencies**: None (independent of scope 2)
- **Risk focus**:
  - KPI value formatting (number|string union + format field)
  - Pipeline stage color mapping (must handle all 5 stages)
  - Sidebar icon must match existing stroke style (20x20, strokeWidth 1.8)
- **Review focus**:
  - All CSS values use variables, no hardcoded colors except status indicators
  - State matrix: loading, error, success, empty sub-sections
  - Date formatting follows pt-BR convention
- **Done criteria**:
  - Page renders all 4 sections (KPIs, pipeline, top-5, sectors)
  - Loading state displays while fetching
  - Error state displays on request failure
  - Empty sub-sections show fallback text
  - Pipeline progress bar fills correctly
  - Ticker links navigate to /assets/:ticker
  - Sidebar shows Dashboard as first item
- **V1**: Yes

### Scope 2: Portfolio Page (COMPLETE)

- **Objective**: Add data UI to existing `/portfolio` stub
- **Files**:
  - REWRITE `apps/web/app/(dashboard)/portfolio/page.tsx`
- **Dependencies**: None (hook already exists, 3D scene unchanged)
- **Risk focus**:
  - React Query dedup between page and PortfolioConstellationScene (verified: same queryKey)
  - FactorBar division by zero (guarded: max > 0 check)
  - 3D scene height constraint (CSS only, no scene modification)
- **Review focus**:
  - Empty state includes link to /strategy
  - Holdings table ticker links work
  - Return column color-coded (green/red/default)
  - FactorBar color thresholds match asset detail page
- **Done criteria**:
  - Stat cards show totalValue (BRL) and totalReturn (%)
  - Holdings table renders all fields with correct formatting
  - Factor bars render with correct proportions and colors
  - 3D scene renders below data at 400px height
  - Loading state displays while fetching
  - Error state displays on failure
  - Empty state displays with link to /strategy when no holdings
- **V1**: Yes

## 17. Validation Plan

### Per-Build Checks

**Scope 1 (Dashboard)**:
- [x] `pnpm --filter @q3/web build` passes with no type errors
- [x] Navigate to `/dashboard` -- page loads without crash (HTTP 200)
- [x] KPI cards show 4 items with correct formatting: "Total Assets: 0", "Avg ROC: 0%", "Avg EY: 0%", "Strategy Runs: 3"
- [x] Pipeline section: "Completed" badge (green), progress bar at 100%, timestamp "09/03/2026 12:42"
- [x] Top-5 table: ranks displayed, ticker links gold `rgb(251,191,36)` navigate to `/assets/:ticker`
- [x] Sector distribution: "Sem Setor: 710" with proportional gold bar
- [x] Loading: shows "Carregando dashboard..." (screenshot: dashboard-1-state.png)
- [x] Error: "Erro ao carregar dashboard." in red (screenshot: dashboard-error.png)
- [x] Sidebar: Dashboard is first item, grid icon renders, `sidebar__link--active` class applied

**Scope 2 (Portfolio)**:
- [x] `pnpm --filter @q3/web build` passes with no type errors
- [x] Navigate to `/portfolio` -- page loads without crash (HTTP 200)
- [x] Stat cards: "Valor Total: R$ 0", "Retorno Medio (ROIC): 0.00%", "Holdings: 10 / equal-weight"
- [x] Holdings table: 10 rows, ticker links gold, weight 10.0%, value R$ 0, return 0.00%
- [x] Return column: color coded (0% renders default, not green/red -- correct for zero)
- [x] Factor bars: ROIC 0% (gray), Quality 20% (red bar at 20% width)
- [x] 3D scene: height=400px container confirmed, canvas element present inside
- [x] Loading: shows "Carregando portfolio..." (screenshot: portfolio-1-state.png)
- [x] Error: "Erro ao carregar portfolio." in red (screenshot: portfolio-error.png)
- [x] Empty: not exercisable with current data (holdings always populated from ranking)

**Note on 3D scene**: WebGL context error in headless Chromium (Playwright) -- expected in
headless mode without GPU. Does not affect real browser rendering.

### Final Feature Validation
- [x] Both pages accessible from sidebar navigation (verified via Playwright DOM)
- [x] Visual consistency: colors, fonts, spacing match universe/ranking pages (screenshots confirm)
- [x] No page-level JavaScript errors (pageerror events: NONE except expected WebGL in headless)
- [x] `pnpm --filter @q3/web build` passes clean

### Runtime Evidence (Playwright, headless Chromium 1280x900)
- `/tmp/q3-screenshots/dashboard-success.png` -- Success state with real API data
- `/tmp/q3-screenshots/dashboard-1-state.png` -- Loading state
- `/tmp/q3-screenshots/dashboard-error.png` -- Error state (API offline)
- `/tmp/q3-screenshots/portfolio-success.png` -- Success state with real API data
- `/tmp/q3-screenshots/portfolio-1-state.png` -- Loading state
- `/tmp/q3-screenshots/portfolio-error.png` -- Error state (API offline)

### Sidebar Verification (Playwright DOM extract)
Order confirmed: Dashboard (active) > Home > Strategy > Ranking > Universe > Compare > Portfolio > Backtest > AI Council + Profile (footer)
Active state class: `sidebar__link sidebar__link--active` applied correctly per page

### Link Verification
Asset links confirmed working: `/assets/CGAS3`, `/assets/BRML3`, `/assets/HBRE3`
Color: `rgb(251, 191, 36)` (accent-gold)
Target route `/assets/:ticker` returns HTTP 200

## 18. Current Status

**Phase**: Build complete. Both scopes implemented. `pnpm --filter @q3/web build` passes clean.

### Build Evidence

**Scope 1 (Dashboard)** -- DONE:
- [x] `pnpm --filter @q3/web build` passes with no type errors
- [x] Created `apps/web/src/hooks/api/useDashboard.ts` (12 lines)
- [x] Created `apps/web/app/(dashboard)/dashboard/page.tsx` (~230 lines)
- [x] Edited `apps/web/src/components/layout/Sidebar.tsx` (Dashboard added as first NAV_ITEM)
- [x] KpiCard: formats via `format` field (percent -> `${value}%`, number -> `String(value)`)
- [x] PipelineStatus: stage badge with STAGE_COLORS mapping (5 stages), progress bar clamped [0,100], lastRun formatted DD/MM/YYYY HH:mm or "Nenhuma execucao"
- [x] TopRanked: table with rank, ticker (gold link to /assets/:ticker), name, price (null -> "---")
- [x] SectorDistribution: sorted desc, horizontal bars proportional to max count
- [x] States: loading, error, empty sub-sections (topRanked, sectorDist)
- [x] exactOptionalPropertyTypes fix: KpiCard format prop typed as `string | undefined`

**Scope 2 (Portfolio)** -- DONE:
- [x] `pnpm --filter @q3/web build` passes with no type errors
- [x] Rewrote `apps/web/app/(dashboard)/portfolio/page.tsx` (~200 lines)
- [x] StatCards: Valor Total (BRL via formatNumber), Retorno Medio (%), Holdings count
- [x] Holdings table: ticker (gold link), name (ellipsis), sector, weight%, value (BRL), return% (color-coded green/red)
- [x] FactorBar: identical pattern to assets/[ticker]/page.tsx, guard for max=0
- [x] 3D scene: PortfolioConstellationScene below data section, height 400px, border-top separator
- [x] States: loading, error, empty (with link to /strategy)
- [x] React Query dedup: page and scene both use queryKey ['portfolio'] -- single HTTP request

## 19. Close Summary

### Delivered Scope
- `/dashboard` page: KPI cards, pipeline status, top-5 ranked table, sector distribution
- `/portfolio` page: stat cards, holdings table, factor tilt bars, 3D constellation scene
- Sidebar: Dashboard added as first navigation item with dashboard grid icon

### Files Changed
- CREATE `apps/web/src/hooks/api/useDashboard.ts`
- CREATE `apps/web/app/(dashboard)/dashboard/page.tsx`
- REWRITE `apps/web/app/(dashboard)/portfolio/page.tsx`
- EDIT `apps/web/src/components/layout/Sidebar.tsx`

### Explicit Cuts
- Portfolio equity curve: not rendered (API returns null, out of scope)
- Dashboard polling/real-time: not implemented (out of scope)
- topRanked `change` field: not rendered (dashboard is overview, not quotes)

### Known Limitations
- KPI `change` and `positive` fields exist in schema but are not produced by current API -- not rendered
- Portfolio data comes from latest completed strategy run only -- no historical portfolio view
- 3D scene height is fixed at 400px -- not responsive to viewport

### Follow-up Decision
No follow-up required. Both pages are functionally complete for current API capabilities.

### Final Feature Status
**DONE** -- Approved by Tech Lead after 3 review rounds (shaping v1 blocked, shaping v2 approved, runtime validated).

### Known Test Environment Limitation
WebGL context error in headless Chromium (Playwright) -- expected behavior without GPU acceleration. Does not affect real browser rendering. If automated visual regression is added later, classify this as known environment limitation.

## 20. Tech Lead Handoff

### What Changed
4 files touched. 2 new pages, 1 new hook, 1 sidebar edit. Zero API or schema changes.

### Pattern Adherence
- Dashboard page follows universe/page.tsx patterns: StatCard, SectorBar, page shell
- Portfolio page follows universe/page.tsx + assets/[ticker]/page.tsx patterns: StatCard, FactorBar, table layout
- All colors use CSS variables except status indicators (green/blue/gold/red/gray for stages)
- All local components defined inline per existing convention

### Where to Focus Review
1. `dashboard/page.tsx` PipelineStatus component -- unique widget, verify stage color mapping covers all cases
2. `portfolio/page.tsx` 3D scene coexistence -- verify React Query dedup works correctly (single network request)
3. `Sidebar.tsx` -- verify Dashboard icon renders consistently in collapsed/expanded states
4. Date formatting in Dashboard -- manual DD/MM/YYYY implementation, no Intl API

### Residual Risks
- If API changes KPI format field behavior, dashboard formatting would need update
- If strategy results shape changes, portfolio empty state could trigger unexpectedly
- Sidebar now has 9 items -- may feel crowded on small screens (not in scope to fix)
