# MF-RUNTIME-01A — Pilot Runtime Test Harness

## Status: BUILD APPROVED — TL approved 2026-03-26 (5 corrections applied)

---

## 1. Micro Feature

**Provar automaticamente que o pipeline do piloto (snapshot ranking + forward returns + scheduler) funciona end-to-end, via testes unitarios, integracao e E2E, sem depender de ambiente real de producao.**

O produto NAO e "piloto rodando em producao". E: "pipeline provado automaticamente e pronto para implantar sem adivinhacao."

## 2. Problem

O piloto do Q3 nao tem nenhuma infraestrutura persistente. Hoje:
- Decisoes salvas como JSON em disco (`results/pilot/2026-04/decision_journal.json`)
- Forward returns = `null` (nao computados)
- Scheduler = inexistente (scripts manuais)
- Zero tabelas no banco para snapshot ou retornos
- Impossivel validar se o pipeline funciona sem rodar tudo manualmente

Sem prova automatica de que o pipeline funciona, qualquer deploy e adivinhacao.

## 3. Outcome

- Testes unitarios: logica pura de snapshot mapping, calculo de retorno, idempotencia
- Testes de integracao: jobs persistem no banco real, rerun nao duplica
- Testes E2E: fluxo completo (snapshot → precos → forward return) verde
- Contratos: `SnapshotService`, `ForwardReturnService`, `JobScheduler` testavel
- Migration: tabelas `ranking_snapshots` + `forward_returns` criadas
- Modelos: SQLAlchemy + Drizzle alinhados
- Scheduler abstraction: registra jobs, disparavel via fake nos testes

## 4. Why Now

- Piloto Phase 1 ativo — sem runtime, forward returns nao sao coletados
- Plan 5+6 entregaram ranking com NPY — agora precisa capturar snapshots desse ranking
- MEMORY CRITICAL BLOCKER: "subir runtime minimo do piloto antes de esperar dados"

### Follow-up ledger

Nenhum follow-up diretamente absorvido. O CRITICAL BLOCKER do MEMORY e o driver.

---

## 5. Current System Summary

### O que existe

| Componente | Status | Local |
|------------|--------|-------|
| Monthly pilot script | Manual | `scripts/run_pilot_month.py` — gera JSON, nao persiste em DB |
| Decision journal | JSON em disco | `results/pilot/YYYY-MM/decision_journal.json` |
| Forward returns | NULL | Campo existe no JSON mas nunca computado |
| DB tables | NENHUMA | Sem `ranking_snapshots`, sem `forward_returns` |
| Scheduler | NENHUM | Celery beat existe (ai-assistant) mas sem tasks de pilot |
| Market snapshots | Existe | `market_snapshots` com price/mcap — fonte de precos para retornos |
| Split ranking | Existe | Plan 6 entregou `primaryRanking` (179 NPY_ROC) + `secondaryRanking` (58 EY_ROC) |

### O que precisa ser criado

```
[ranking_snapshots] — captura diaria do ranking (ticker, model, rank, score, snapshot_date)
[forward_returns]   — retorno realizado (ticker, snapshot_date, horizon, return_value)
[SnapshotService]   — createDailySnapshot(date) → persiste ranking no banco
[ForwardReturnService] — computeForwardReturns(date, horizon) → calcula e persiste
[JobScheduler]      — interface abstrata, testavel via fake
```

---

## 6. Requirements

### R1: Tabelas + Modelos

**`ranking_snapshots`**:

| Coluna | Tipo | Semantica |
|--------|------|-----------|
| id | UUID PK | |
| snapshot_date | DATE NOT NULL | Data da captura |
| ticker | VARCHAR NOT NULL | |
| model_family | VARCHAR NOT NULL | 'NPY_ROC' ou 'EY_ROC' |
| rank_within_model | INTEGER NOT NULL | Posicao no modelo |
| composite_score | NUMERIC | Score final |
| investability_status | VARCHAR NOT NULL | 'fully_evaluated' ou 'partially_evaluated' |
| created_at | TIMESTAMPTZ | |

Unique: `(snapshot_date, ticker)`

**`forward_returns`**:

| Coluna | Tipo | Semantica |
|--------|------|-----------|
| id | UUID PK | |
| snapshot_date | DATE NOT NULL | Data do snapshot de referencia |
| ticker | VARCHAR NOT NULL | |
| horizon | VARCHAR NOT NULL | '1d', '5d', '21d' |
| price_t0 | NUMERIC | Preco na data do snapshot |
| price_tn | NUMERIC | Preco na data t+horizon |
| return_value | NUMERIC | (price_tn - price_t0) / price_t0 |
| computed_at | TIMESTAMPTZ | |

Unique: `(snapshot_date, ticker, horizon)`

### R2: Logica pura (testavel sem DB)

```python
def map_ranking_to_snapshot_rows(ranking: list[dict], snapshot_date: date) -> list[SnapshotRow]
def calculate_forward_return(price_t0: float, price_tn: float) -> float | None
def resolve_horizon_date(snapshot_date: date, horizon: str) -> date
```

### R3: Services (testavel com DB)

```python
class SnapshotService:
    def create_daily_snapshot(
        self, session: Session, snapshot_date: date, ranking_items: list[dict],
    ) -> CreateResult
    # session explícita, ranking_items injetado. Sem fetch, sem rede.

class ForwardReturnService:
    def compute_forward_returns(
        self, session: Session, snapshot_date: date, horizon: str,
    ) -> ComputeResult
    # Busca precos de market_snapshots via session (DB local). Sem fetch externo.
    # PRICE_WINDOW_DAYS = 5, cast(fetched_at, Date) para comparação segura.
```

Idempotentes: rerun nao duplica. Ranking SEMPRE injetado — nunca fetchado internamente.

### R4: Scheduler abstraction

```python
class JobScheduler(Protocol):
    def register(self, name: str, schedule: str, handler: Callable) -> None

class FakeScheduler(JobScheduler):
    # Para testes — captura handlers, dispara manualmente
```

### R5: Owner

Tudo em quant-engine (pilot e funcao do quant-engine, nao do fundamentals-engine).

---

## 7. Selected Shape

**Test harness com implementacao minima**:

1. Migration cria tabelas
2. Funcoes puras implementadas e testadas (unit)
3. Services implementados e testados (integration com DB real)
4. Scheduler abstraction + fake para testes
5. E2E: boot app → snapshot → precos → returns → verifica DB

### Pair shaping
- Triggered: no
- Triggers matched: none (single service, clear contracts)
- Decision: async review

---

## 8. Appetite

- **Level**: Medium — 3 build scopes (S1 unit, S2 integration, S3 E2E)
- **Why**: Tabelas novas + logica nova + testes em 3 camadas. Sem UI, sem deploy.
- **Must-fit**: Migration + pure functions + services + testes nas 3 camadas
- **First cuts**: E2E (S3) pode ser simplificado para integration-level se appetite exceder

---

## 9. Boundaries / No-Gos / Out of Scope

### Boundaries

- Tocar: quant-engine (novo modulo `pilot/`), shared-models-py (novos modelos), Drizzle schema, Alembic migration
- Criar: testes unitarios, de integracao e E2E

### No-Gos

- NAO fazer deploy real
- NAO configurar cron/systemd/PM2 real
- NAO configurar server always-on
- NAO criar cloud infra
- NAO criar logs centralizados / observabilidade real
- NAO testar uptime
- NAO tocar UI/frontend
- Scheduler SEMPRE via abstraction/fake nos testes

### Out of Scope

- Deploy em VPS/cloud
- Celery beat integration real (sera MF-RUNTIME-01B)
- API endpoints para pilot (sera separado)
- UI de pilot dashboard
- Alertas de falha

---

## 10. Rabbit Holes / Hidden Risks

### RH1: Fonte de precos para forward returns (MEDIO)

Forward returns precisam de preco em t0 e t+n. market_snapshots tem precos mas nao diarios para todos os tickers.

**Mitigacao**: Nos testes, precos vem de fixtures / DB de teste. Estrategia de preco em producao fica para MF-RUNTIME-01B ou MF separado. Este MF testa a logica, nao a ingestao de precos.

### RH2: Ranking source para snapshot (BAIXO)

Snapshot precisa consumir o ranking. O ranking agora vem do quant-engine `/ranking` endpoint.

**Mitigacao**: SnapshotService recebe ranking como parametro (injecao), nao faz HTTP call. Testavel com fixture.

### RH3: Timezone de snapshot_date (BAIXO)

Mercado B3 fecha ~18h BRT. snapshot_date deve ser date (nao datetime).

**Mitigacao**: Usar `date` puro. Sem timezone.

---

## 11. Breadboard

```
[Ranking data] (injetado, nao fetchado)
    |
    v
[map_ranking_to_snapshot_rows()] — pure function
    |
    v
[SnapshotService.create_daily_snapshot()] — persiste em ranking_snapshots
    |                                        idempotente (upsert)
    v
[ranking_snapshots table]
    |
    v
(tempo passa... precos disponíveis)
    |
    v
[ForwardReturnService.compute_forward_returns()]
    |   - busca price_t0 de market_snapshots
    |   - busca price_tn de market_snapshots
    |   - calcula return = (tn - t0) / t0
    |
    v
[forward_returns table]
    |
    v
[FakeScheduler] — registra e dispara jobs nos testes
```

---

## 12. Build Scopes

### S1: Unit Tests + Pure Functions

**Objective**: Implementar e testar logica pura sem banco.

**Files**:
- `services/quant-engine/src/q3_quant_engine/pilot/__init__.py`
- `services/quant-engine/src/q3_quant_engine/pilot/snapshot.py` — `map_ranking_to_snapshot_rows()`
- `services/quant-engine/src/q3_quant_engine/pilot/returns.py` — `calculate_forward_return()`, `resolve_horizon_date()`
- `services/quant-engine/src/q3_quant_engine/pilot/scheduler.py` — `JobScheduler`, `FakeScheduler`
- `services/quant-engine/tests/pilot/test_snapshot_pure.py`
- `services/quant-engine/tests/pilot/test_returns_pure.py`
- `services/quant-engine/tests/pilot/test_scheduler.py`

**Spec tests**:
- `map_ranking_to_snapshot_rows`: transforma ranking em rows, preserva model_family e rank_within_model
- `map_ranking_to_snapshot_rows`: input vazio → output vazio
- `calculate_forward_return(price_t0=100, price_tn=110)` → +0.10 (subiu 10%)
- `calculate_forward_return(price_t0=110, price_tn=100)` → -0.0909 (caiu ~9.1%)
- `calculate_forward_return(price_t0=100, price_tn=100)` → 0.0
- `calculate_forward_return(price_t0=0, price_tn=100)` → None (div by zero)
- `calculate_forward_return(price_t0=None, price_tn=100)` → None
- Formula: `(price_tn - price_t0) / price_t0` — sem ambiguidade
- `resolve_horizon_date`: '1d' → +1 weekday (Mon-Fri), '5d' → +5 weekdays, '21d' → +21 weekdays
- Simplificacao: weekday-only, SEM calendario de feriados B3 (feriados ficam para MF futuro)
- `FakeScheduler`: registra handler, dispara manualmente, captura chamadas
- (idempotencia pertence a S2 via unique keys + rerun, NAO a logica pura)

**Dependencies**: Nenhuma
**V1**: Sim

---

### S2: Integration Tests + Migration + Services

**Objective**: Criar tabelas, modelos, services e testar com DB real.

**Files**:
- `services/quant-engine/alembic/versions/YYYYMMDD_XXXX_create_pilot_tables.py`
- `packages/shared-models-py/src/q3_shared_models/entities.py` — `RankingSnapshot`, `ForwardReturn`
- `apps/api/src/db/schema.ts` — `rankingSnapshots`, `forwardReturns`
- `services/quant-engine/src/q3_quant_engine/pilot/services.py` — `SnapshotService`, `ForwardReturnService`
- `services/quant-engine/tests/pilot/test_snapshot_integration.py`
- `services/quant-engine/tests/pilot/test_returns_integration.py`

**Spec tests**:
- `SnapshotService.create_daily_snapshot()`: persiste N rows em ranking_snapshots
- Rerun create_daily_snapshot com mesma data: 0 inserts (idempotente)
- `ForwardReturnService.compute_forward_returns()`: persiste rows com return_value correto
- Rerun compute: 0 inserts (idempotente)
- Schema correto (colunas, constraints, unique keys)
- Migration up + down funciona

**Dependencies**: S1
**V1**: Sim

---

### S3: E2E Tests

**Objective**: Provar fluxo completo snapshot → precos → returns.

**Files**:
- `services/quant-engine/tests/pilot/test_e2e_runtime.py`

**Spec tests**:
- E2E-1: Cria snapshot a partir de ranking fixture → verifica rows em DB
- E2E-2: Snapshot existe + precos inseridos → computa returns → verifica DB
- E2E-3: Full chain: ranking → snapshot → precos → returns → estado final correto
- FakeScheduler: registra jobs, dispara sequencialmente, verifica resultado
- Logs minimos emitidos (capturados via `caplog`)

**Dependencies**: S2
**V1**: Sim

---

## 13. Validation Plan

### Unit (S1)

- 100% paths criticos de calculo de retorno
- Cenarios de erro e skip
- Zero dependencia externa

### Integration (S2)

- Banco Postgres real (local)
- Migrations reais
- Writes reais
- Idempotencia provada

### E2E (S3)

- Fluxo completo verde
- Estado final correto no banco
- Logs observaveis

### Criterio de done

Prova automatica de que:
1. Snapshot pode ser criado
2. Snapshot e persistido
3. Forward return pode ser calculado
4. Return e persistido
5. Jobs sao registraveis/disparaveis
6. Rerun nao duplica
7. Fluxo E2E completo passa

---

## 14. Current Status

- [x] Phase 0: Intake
- [x] Phase 1: Map current system
- [x] Phase 2: Shape
- [x] Phase 3: Appetite
- [x] Phase 4: Boundaries
- [x] Phase 5: Risks
- [x] Phase 6: Breadboard
- [x] Phase 7: Build scopes
- [x] Phase 8: Build (S1+S2+S3)
- [x] Phase 9: Validate (43 pilot tests, 457 total)
- [x] Phase 10: Close
- [x] Phase 11: Handoff

**DONE — S1+S2+S3 complete. All 7 criteria met.**

---

## 15. Close Summary

### Delivered

7/7 criteria de done provados automaticamente:

| Criterio | Evidencia |
|----------|-----------|
| 1. Snapshot pode ser criado | `test_e2e_snapshot_creation` PASS |
| 2. Snapshot e persistido | 3 rows in DB verified |
| 3. Forward return pode ser calculado | `calculate_forward_return(100, 112) = 0.12` PASS |
| 4. Return e persistido | `test_e2e_forward_returns` PASS — 3 returns with correct values |
| 5. Jobs sao registraveis/disparaveis | `test_e2e_full_chain_with_scheduler` PASS — FakeScheduler fires both |
| 6. Rerun nao duplica | `test_rerun_is_idempotent` PASS (snapshot + returns) |
| 7. Fluxo E2E completo passa | Full chain: ranking → snapshot → prices → returns → JOIN verify PASS |

### Test pyramid

| Level | Tests | Files |
|-------|-------|-------|
| Unit | 33 | `test_snapshot_pure.py`, `test_returns_pure.py`, `test_scheduler.py` |
| Integration | 7 | `test_snapshot_integration.py`, `test_returns_integration.py` |
| E2E | 3 | `test_e2e_runtime.py` |
| **Total** | **43** | 6 test files |

### Files touched

| File | Type |
|------|------|
| `pilot/__init__.py` | New |
| `pilot/snapshot.py` | New — `SnapshotRow`, `RankingItemInput`, `map_ranking_to_snapshot_rows()` |
| `pilot/returns.py` | New — `calculate_forward_return()`, `resolve_horizon_date()` |
| `pilot/scheduler.py` | New — `JobScheduler`, `FakeScheduler` |
| `pilot/services.py` | New — `SnapshotService`, `ForwardReturnService` |
| `alembic/.../20260326_0024` | New — `ranking_snapshots` + `forward_returns` tables |
| `entities.py` | Edit — `RankingSnapshot` + `ForwardReturn` models |
| `schema.ts` | Edit — Drizzle tables |

### Follow-ups

No follow-ups generated. Next step is MF-RUNTIME-01B (Celery beat integration, real scheduler wiring).

### Final status: DONE

---

## 16. Tech Lead Handoff

MF-RUNTIME-01A proves the pilot runtime pipeline works end-to-end via automated tests. Snapshot creation, forward return computation, idempotency, and scheduler dispatch are all verified without any production dependency. The pipeline is ready to be wired to real scheduling (MF-RUNTIME-01B) without guesswork.
