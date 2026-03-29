# MF-RUNTIME-01B — Pilot Scheduler Wiring

## Status: SHAPED — awaiting TL review

---

## 1. Micro Feature

**Conectar o pipeline do piloto (MF-RUNTIME-01A) ao Celery beat real. Snapshot diário + forward returns computados automaticamente sem intervenção manual.**

## 2. Problem

MF-RUNTIME-01A provou que o pipeline funciona via testes. Mas em produção, ninguém dispara os jobs — não existe scheduling real. Sem isso, o piloto não coleta forward returns automaticamente.

## 3. Outcome

- Celery beat dispara `create_daily_snapshot` todo dia útil às 18h BRT (pós-fechamento B3)
- Celery beat dispara `compute_forward_returns` para horizons 1d/5d/21d quando preços disponíveis
- Snapshots e returns persistidos automaticamente em `ranking_snapshots` + `forward_returns`
- Idempotente: rerun não duplica (provado por 01A)

## 4. Why Now

Piloto Phase 1 ativo. Forward returns não estão sendo coletados. Cada dia sem snapshot é dado perdido.

---

## 5. Current System

| Componente | Status |
|------------|--------|
| Pipeline (snapshot + returns) | PROVADO (43 testes em 01A) |
| SnapshotService | Implementado, idempotente |
| ForwardReturnService | Implementado, idempotente |
| Celery beat | Ativo em ai-assistant (3 tasks existentes) |
| PM2 `q3-ai-beat` | Rodando |
| Quant-engine celery | Workers ativos, sem beat schedule |

---

## 6. Requirements

### R1: Beat tasks no quant-engine

Duas opções investigadas:

**Opção A (RECOMENDADA)**: Adicionar beat schedule ao quant-engine celery_app + novo processo PM2 `q3-quant-beat`.

**Justificativa**: Pilot pertence ao quant-engine (ownership), não ao ai-assistant. Criar beat no quant-engine mantém ownership limpo. Um novo processo PM2 é trivial.

**Opção B (REJEITADA)**: Usar ai-assistant beat existente. Viola ownership — ai-assistant dispara tasks do quant-engine.

### R2: Snapshot task

```python
@celery_app.task
def take_daily_snapshot():
    """Fetch current ranking from /ranking endpoint, persist as snapshot."""
    # 1. HTTP GET localhost:8100/ranking
    # 2. SnapshotService.create_daily_snapshot(session, today, items)
    # 3. Log result
```

Schedule: `crontab(hour=18, minute=0, day_of_week='1-5')` (seg-sex 18h BRT)

### R3: Forward returns task

```python
@celery_app.task
def compute_all_forward_returns():
    """For each past snapshot, compute missing forward returns."""
    # 1. Query ranking_snapshots with dates where returns are missing
    # 2. For each (snapshot_date, horizon): ForwardReturnService.compute_forward_returns()
    # 3. Log results
```

Schedule: `crontab(hour=19, minute=0, day_of_week='1-5')` (1h após snapshot, preços atualizados)

### R4: Idempotência garantida

Services já são idempotentes (unique constraints + upsert). Se beat dispara 2x no mesmo dia, zero duplicatas.

---

## 7. Appetite

- **Level**: Small — 3 arquivos novos (task, celery config, PM2 entry)
- **Must-fit**: Beat tasks + PM2 + idempotência
- **First cuts**: Forward returns pode ser manual (script) se beat for complexo

---

## 8. Boundaries / No-Gos

- NAO modificar SnapshotService ou ForwardReturnService (já provados)
- NAO criar novo endpoint HTTP
- NAO tocar ai-assistant
- NAO adicionar alertas/monitoring (MF separado)

---

## 9. Risks

### RH1: Quant-engine precisa de HTTP client para consumir /ranking

O snapshot task precisa do ranking atual. Opções:
- HTTP GET `localhost:8100/ranking` (endpoint já existe)
- Chamar `_run_hybrid_no_gates()` diretamente (evita HTTP)

**Decisão**: chamar diretamente — task roda no mesmo processo. Sem network hop.

### RH2: Preços não disponíveis quando returns roda

Forward returns dependem de market_snapshots com preço no dia correto. Se Yahoo adapter não rodou ainda, preço pode não existir.

**Mitigação**: ForwardReturnService já faz skip quando preço não existe. Returns são recomputados no dia seguinte (idempotente).

---

## 10. Build Scope

**Scope único**:
1. `quant-engine/tasks/pilot_tasks.py` — 2 Celery tasks
2. `quant-engine/celery_app.py` — beat_schedule com 2 entries
3. `ecosystem.config.cjs` — novo PM2 process `q3-quant-beat`

**Done**: `pm2 restart q3-quant-beat` → snapshot criado automaticamente → returns computados no dia seguinte.
