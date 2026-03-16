# Shape Up — F3.3: Automated Alerts

## Micro Feature
Automated governance alerts computed from monitoring data — surface anomalies as banners on the monitoring dashboard.

## Shape
3 layers:
1. Pure computation: `compute_run_alerts()` in quant-engine, 6 alert types with WARNING/CRITICAL thresholds
2. NestJS proxy: `GET /thesis/monitoring/alerts` proxies to quant-engine
3. Web UI: alerts banner on `/thesis/monitoring` page

## Build Scopes

### Scope 1: Alert computation module — DONE
- `alerts.py` with `compute_run_alerts()` pure function
- 6 alert types: BUCKET_DRIFT_HIGH, TOP10_CHANGED, LOW_CONFIDENCE_SURGE, STALE_RUBRICS_HIGH, REVIEW_QUEUE_HIGH_GROWTH, D_FRAGILE_SHIFT
- Each alert: code, severity, title, message, metric_value, threshold, context
- Severity sorting: CRITICAL first, then WARNING, then INFO
- 24 unit tests covering all 6 alert types + edge cases + sorting

### Scope 2: FastAPI endpoint — DONE
- `GET /plan2/runs/{run_id}/alerts?stale_days=30`
- Orchestrates all 4 monitoring functions + feeds results to `compute_run_alerts()`
- Returns: run_id, alert_count, critical_count, warning_count, alerts[]

### Scope 3: NestJS proxy + web hook — DONE
- `thesis.service.ts`: `getAlerts(tenantId, staleDays)` proxies to quant-engine
- `thesis.controller.ts`: `GET /thesis/monitoring/alerts`
- `useThesisMonitoring.ts`: `useMonitoringAlerts()` hook + `AlertItem`, `AlertsResponse` types

### Scope 4: Dashboard banner — DONE
- `AlertsBanner` component at top of monitoring page
- Each alert renders as a colored banner with severity icon, title, message, badge
- CRITICAL = red, WARNING = amber, INFO = blue
- Hidden when no alerts (zero visual noise on healthy runs)

## Alert Thresholds

| Code | WARNING | CRITICAL |
|------|---------|----------|
| BUCKET_DRIFT_HIGH | >= 10% | >= 20% |
| TOP10_CHANGED | any change | >= 3 changes |
| LOW_CONFIDENCE_SURGE | >= 10pp low | >= 20pp low |
| STALE_RUBRICS_HIGH | >= 20% | >= 35% |
| REVIEW_QUEUE_HIGH_GROWTH | >= 10 high-priority | >= 20 high-priority |
| D_FRAGILE_SHIFT | >= 2 entering | >= 5 entering |

## Validation
- `python -m pytest` (quant-engine) — 415 passed
- `pnpm --filter @q3/api typecheck` — clean
- `pnpm --filter @q3/web typecheck` — clean
- `ruff check alerts.py` — clean

## Files Changed
- `services/quant-engine/src/q3_quant_engine/thesis/alerts.py` — NEW (compute_run_alerts + 6 checkers)
- `services/quant-engine/tests/thesis/test_alerts.py` — NEW (24 tests)
- `services/quant-engine/src/q3_quant_engine/thesis/router.py` — added alerts endpoint
- `apps/api/src/thesis/thesis.controller.ts` — added monitoring/alerts endpoint
- `apps/api/src/thesis/thesis.service.ts` — added getAlerts proxy method
- `apps/web/src/hooks/api/useThesisMonitoring.ts` — added AlertItem, AlertsResponse, useMonitoringAlerts
- `apps/web/app/(dashboard)/thesis/monitoring/page.tsx` — added AlertsBanner component

## Not Doing (per shape)
- No webhooks, email, or external notifications
- No alert persistence / history
- No trend analysis across runs
- No alert indicator on ranking page (follow-up)

## Close Summary
F3.3 delivers automated governance alerts that surface anomalies immediately on the monitoring dashboard. The team sees CRITICAL/WARNING banners in seconds after a run, answering "is something wrong?" before even reading the cards.
