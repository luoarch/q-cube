# Plan 7 — B3 COTAHIST: Precos Oficiais da Bolsa

## Status: SHAPING — awaiting TL review

---

## 1. Micro Feature

**Internalizar precos da B3 via COTAHIST como fonte primaria de market data, derivar market_cap = B3_close × CVM_net_shares, e eliminar dependencia do Yahoo para price/mcap no universo Core.**

## 2. Problem

42 tickers Core nao tem market_cap porque o Yahoo nao os cobre (404/no data). Isso impede o calculo de DY (que requer mcap) e deixa esses ativos no secondaryRanking.

Alem disso, o Yahoo (via yfinance) e:
- Fonte nao-oficial (community scraper, pode quebrar)
- Cobertura parcial (~80% do B3)
- Nao auditavel para fins academicos
- Rate-limited e instavel

A B3 publica dados oficiais de negociacao (COTAHIST) gratuitamente com 100% de cobertura.

## 3. Outcome

- Parser de COTAHIST (fixed-width B3 format)
- Adapter B3 registrado na factory de market data
- market_cap derivado: `B3_close_price × CVM_net_shares` para TODOS os Core issuers
- 16 dos 42 tickers ganham mcap via B3 (26 restantes sao delisted/OTC — structural)
- Cobertura mcap sobe de 195/237 (82%) para ~211/237 (89%)
- Backfill historico (2020-2024) para PIT-correctness
- Zero dependencia do Yahoo para price (Yahoo pode ser desligado)

## 4. Why Now

- 42 tickers sem mcap = structural gap que nenhum vendor resolve
- B3 COTAHIST = 100% cobertura, gratis, oficial, auditavel
- CVM shares ja no DB (Plan 5) → so falta price para derivar mcap
- Piloto ativo — cada dia sem mcap = forward returns incompletos
- Transforma o Q3 de "quant com dados best-effort" para "modelo com base 100% regulatoria"

### Follow-up ledger

| ID | Decisao |
|----|---------|
| FU-P5-2 (structural) | **Absorvido** — B3 resolve o gap de 42 tickers que Yahoo nao cobre |

---

## 5. Current System Summary

### Market data flow atual

```
Yahoo/yfinance → MarketSnapshotProvider (factory)
    → market_snapshots (price, market_cap, volume)
        → compat view (ranking)
        → snapshot_anchor (NBY)
        → forward returns (pilot)
```

### Adapter pattern existente

```python
class MarketSnapshotProvider(Protocol):
    async def get_snapshot(ticker: str) -> MarketSnapshotData | None
    async def get_snapshots_batch(tickers: list[str]) -> list[MarketSnapshotData]
    async def get_historical(ticker: str, period: str, interval: str) -> list[OHLCVRecord]
```

Factory: `MarketSnapshotProviderFactory.create(source)` → lazy-loads adapter.
Config: `MARKET_SNAPSHOT_SOURCE=yahoo` (env var).

### SourceProvider enum

`cvm`, `brapi`, `dados_de_mercado`, `manual`, `yahoo`. Falta `b3`.

### O que muda com B3

**Nada downstream.** Compat view, NBY, ranking, forward returns — todos consultam `market_snapshots` por `security_id` sem se importar com `source`. O adapter e a unica peça nova.

---

## 6. Requirements

### R1: Parser COTAHIST

B3 COTAHIST e arquivo fixed-width. Formato documentado pela B3:

```
Pos  Tam  Campo              Descricao
001  002  TIPREG             Tipo registro (01=header, 99=trailer, 00=detalhe)
003  008  DATA               Data YYYYMMDD
011  002  CODBDI             Codigo BDI
013  012  CODNEG             Codigo de negociacao (ticker)
025  003  TPMERC             Tipo de mercado (010=vista)
...
109  013  PREULT             Preco ultimo (close) — formato N(11)V99 (centavos)
...
153  018  QUATOT             Quantidade total de titulos negociados
171  018  VOLTOT             Volume total negociado (centavos)
```

Parser extrai: ticker, date, close_price, volume, n_trades.

### R2: Adapter B3 seguindo factory pattern

```python
class B3CotahistAdapter(MarketSnapshotProvider):
    async def get_snapshot(ticker) -> MarketSnapshotData | None
    async def get_snapshots_batch(tickers) -> list[MarketSnapshotData]
```

`market_cap` NAO vem do COTAHIST (nao tem). E derivado: `close_price × CVM_net_shares`.

### R3: Derivacao de market_cap

```python
market_cap = b3_close_price × cvm_net_shares
```

Ambas fontes regulatorias. Derivacao feita no adapter ou no loader. `inputs_snapshot` registra ambas fontes.

### R4: Backfill historico

COTAHIST disponivel como ZIP anual: `COTAHIST_AYYYY.ZIP`.
Backfill 2020-2024 para ter serie temporal PIT.

### R5: SourceProvider enum + config

Adicionar `b3 = "b3"` ao enum. `ENABLE_B3=true`. Factory registra lazy.

---

## 7. Candidate Shapes

### Shape A: Adapter completo na factory (RECOMENDADA)

- Parser COTAHIST como modulo puro
- B3 adapter implementa `MarketSnapshotProvider` protocol
- market_cap derivado no adapter (close × CVM shares)
- Registrado na factory com lazy load
- Backfill via script (ZIPs anuais 2020-2024)
- Downstream zero changes

**Pros**: segue pattern existente, zero breaking change, 100% cobertura B3.
**Cons**: COTAHIST e diario — precisa de download diario ou bulk.

### Shape B: Tabela separada b3_prices (REJEITADA)

- Nova tabela so para precos B3
- Downstream teria que consultar duas tabelas

**Problemas**: viola single-path (duas fontes de price). Downstream teria que saber de onde vem.

### Shape C: Enriquecer market_snapshots com B3 como fallback (REJEITADA)

**Problemas**: fallback silencioso = Plan 6 matou isso.

---

## 8. Selected Shape

**Shape A** — Adapter completo integrado na factory existente.

### Diferencial: market_cap derivado

COTAHIST NAO tem market_cap. O adapter B3 faz:

1. Parse COTAHIST → close_price
2. Query CVM shares: `find_cvm_shares(issuer_id, quarter_end)`
3. Derivar: `market_cap = close × net_shares`
4. Persist como MarketSnapshot com `source=b3`

Isso e o UNICO adapter que combina duas fontes regulatorias.

### Pair shaping
- Triggered: no
- Triggers matched: none (single service, existing pattern)
- Decision: async review

---

## 9. Appetite

- **Level**: Medium — 3 build scopes
- **Why**: Parser novo + adapter + backfill. Pattern existente, zero schema change.
- **Must-fit**: S1 (parser), S2 (adapter + derivacao), S3 (backfill + validacao)
- **First cuts**: Backfill pode ser reduzido (so 2024 em vez de 2020-2024)

---

## 10. Boundaries / No-Gos / Out of Scope

### Boundaries

- Tocar: fundamentals-engine (novo provider `b3/`), entities.py (enum), config
- Seguir: factory pattern existente (lazy load, protocol)

### No-Gos

- NAO mudar downstream (compat view, ranking, NBY, forward returns)
- NAO criar tabela nova (usar market_snapshots existente)
- NAO mixar fontes na mesma row (source=b3, nao source=yahoo+b3)
- NAO deletar Yahoo adapter (coexiste, selecionavel por config)

**Correcao TL**: `source_provider` E pgEnum no Postgres. Migration necessaria: `ALTER TYPE source_provider ADD VALUE 'b3'`. Adicionada ao S2.

### Out of Scope

- Intraday data (COTAHIST e diario)
- B3 WebSocket/API real-time
- Remocao do Yahoo (coexiste)
- UI para selecao de provider

---

## 11. Rabbit Holes / Hidden Risks

### RH1: COTAHIST fixed-width parsing (MEDIO)

Formato e documentado mas com nuances: preco em centavos (N11V99), ticker com padding de espacos, filtro por TPMERC=010 (mercado a vista).

**Mitigacao**: Spike com arquivo real. Formato estavel desde 1990s.

### RH2: Ticker matching COTAHIST → securities (MEDIO)

COTAHIST usa CODNEG (ex: "PETR4       "). Securities usa ticker sem padding. Precisa de strip + match.

**Mitigacao**: `codneg.strip()` → match com `securities.ticker`. Trivial.

### RH3: market_cap derivado precisa de CVM shares alinhado temporalmente (MEDIO)

`close_price` e diario. `CVM_net_shares` e trimestral. Para derivar mcap no dia 15/fev, usa shares do ultimo quarter-end (31/dez).

**Mitigacao**: `find_cvm_shares(issuer_id, quarter_end)` ja existe (Plan 5). Usa o mesmo lookup PIT.

### RH4: ZIP download pode ser lento (BAIXO)

COTAHIST anual ~30MB. Download + parse ~10s.

**Mitigacao**: Cache local. Download uma vez por dia.

---

## Decisoes Tecnicas (TL Challenge Round)

### D1: pgEnum migration obrigatoria

`source_provider` e pgEnum. `ALTER TYPE source_provider ADD VALUE 'b3'` em migration S2.

### D2: Ticker matching = exato, sem cross-class

COTAHIST CODNEG matchado por `ticker.strip() == security.ticker`. Sem fallback ON→PN. Se nao encontra, skip.

### D3: B3 substitui Yahoo (switch, nao fallback)

`MARKET_SNAPSHOT_SOURCE=b3` + `ENABLE_B3=true` + `ENABLE_YAHOO=false`. Single source. Nao coexistem no mesmo dia. B3 e oficial > Yahoo community scraper.

### D4: Adapter bulk-first

`get_snapshots_batch(tickers)` e o metodo principal. Download COTAHIST uma vez, parse, filter. `get_snapshot(ticker)` delega para batch de 1.

### D5: Horario de disponibilidade

COTAHIST diario disponivel ~19-20h BRT. Beat snapshot muda para 20:00 quando source=b3. Ou: retry natural se 404.

### D6: market_cap derivado e estimativa documentada

`close × CVM_net_shares` e derivacao, nao dado oficial. CVM shares e trimestral, price e diario. Divergencia esperada vs Yahoo mcap: < 5% para maioria (shares mudam pouco intra-quarter). Documentar como estimativa em qualquer export.

### D7: Backfill agrupado por quarter

Para backfill historico: 1 CVM lookup por issuer por quarter (nao por dia). 8k lookups vs 500k. ~10min total.

---

## 12. Breadboard

```
B3 Portal (bvmf.bmfbovespa.com.br)
    |
    v
[COTAHIST ZIP download]  → COTAHIST_AYYYY.ZIP (anual) ou COTAHIST_DDDMMYYYY.ZIP (diario)
    |
    v
[cotahist_parser.py]  → parse_cotahist(file_bytes) → list[CotahistRecord]
    |                     (pure function: ticker, date, close, volume)
    v
[B3CotahistAdapter]  → implements MarketSnapshotProvider
    |   - get_snapshot(ticker) → parse latest COTAHIST + derive mcap
    |   - mcap = close × find_cvm_shares(issuer, quarter)
    |
    v
[market_snapshots]  → source='b3', price=close, market_cap=derived
    |
    v
(downstream unchanged: compat view, ranking, NBY, forward returns)
```

### Code Affordances (NEW)

| Affordance | Location | Type |
|------------|----------|------|
| `CotahistRecord` | providers/b3/parser.py | Frozen dataclass |
| `parse_cotahist()` | providers/b3/parser.py | Pure function |
| `B3CotahistAdapter` | providers/b3/adapter.py | MarketSnapshotProvider impl |
| `SourceProvider.b3` | entities.py | Enum value |
| `ENABLE_B3` | config.py | Feature flag |

---

## 13. Build Scopes

### S1: COTAHIST Parser (Unit)

**Objective**: Parser puro de fixed-width COTAHIST.

**Files**:
- `fundamentals-engine/src/.../providers/b3/__init__.py`
- `fundamentals-engine/src/.../providers/b3/parser.py`
- `fundamentals-engine/tests/test_b3_cotahist_parser.py`

**Spec tests (unit)**:
- Parse linha valida → CotahistRecord com ticker, date, close, volume
- Preco em centavos convertido corretamente (N11V99)
- Ticker com padding stripped
- Filtro TPMERC=010 (mercado a vista)
- Skip linhas de header/trailer (TIPREG != 00)
- Input vazio → lista vazia
- Frozen dataclass

**Gate checks**: Zero `any`, pure function, no DB.

---

### S2: B3 Adapter + market_cap Derivation (Integration)

**Objective**: Adapter integrado na factory. Deriva market_cap com CVM shares.

**Files**:
- `fundamentals-engine/src/.../providers/b3/adapter.py`
- `fundamentals-engine/src/.../providers/market_snapshot_factory.py` (register)
- `entities.py` (enum)
- `config.py` (flag)
- `fundamentals-engine/tests/test_b3_adapter.py`

**Spec tests (unit + integration)**:
- unit: adapter normaliza ticker, chama parser, deriva mcap
- unit: mcap = close × net_shares (formula correta)
- unit: mcap = None quando CVM shares indisponivel
- integration: adapter persiste MarketSnapshot com source=b3 e mcap derivado
- integration: factory.create("b3") retorna B3CotahistAdapter

**Gate checks**: SourceProvider.b3 adicionado, ENABLE_B3 flag, factory registration.

---

### S3: Backfill + Validacao

**Objective**: Popular market_snapshots com B3 data 2020-2024, validar cobertura.

**Files**:
- `fundamentals-engine/scripts/backfill_b3_cotahist.py`
- Refresh compat view

**Spec tests (integration)**:
- Backfill insere snapshots para tickers Core
- Idempotente (rerun nao duplica)
- market_cap derivado para issuers com CVM shares

**Validation checks**:
- Cobertura mcap: 237/237 Core (100% meta)
- 42 tickers antigos: agora tem mcap
- DY recompute possivel para issuers que tinham mcap=NULL
- secondaryRanking encolhe (ativos migram para primary)
- Reconciliacao B3 vs Yahoo para tickers com ambos

---

## 14. Validation Plan

### Por scope

- S1: Parser puro testado com fixture COTAHIST real
- S2: Adapter + factory integrados, mcap derivado
- S3: Cobertura 100% Core, 42 tickers resolvidos

### Final

1. Cobertura mcap: 237/237 (100%) vs 195/237 atual (82.3%)
2. DY coverage sobe (42 novos com mcap → DY computavel)
3. secondaryRanking shrinks (ativos migram para primary)
4. Reconciliacao B3 close vs Yahoo close para ~195 tickers com ambos (sanity)
5. Forward returns com dados completos

---

## 15. Current Status

- [x] Phase 0: Intake
- [x] Phase 1: Map current system
- [x] Phase 2: Shape
- [x] Phase 3: Appetite
- [x] Phase 4: Boundaries
- [x] Phase 5: Risks
- [x] Phase 6: Breadboard
- [x] Phase 7: Build scopes
- [ ] Phase 8: Build
- [ ] Phase 9: Validate
- [ ] Phase 10: Close
- [ ] Phase 11: Handoff

**Awaiting**: TL review.

---

## 16. Gate Verification

(Pendente — preenchido no close)

---

## 17. Close Summary

(Pendente)

---

## 18. Tech Lead Handoff

(Pendente)
