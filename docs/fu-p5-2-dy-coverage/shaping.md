# FU-P5-2 — DY Coverage Improvement

## Status: SHAPED — awaiting TL review

## IMPORTANT: STATUS CORRECTION + ROOT CAUSE

A investigação revelou que **DY já está em 80.2%** (190/237), passando o gate de 70%.

**Root cause dos 47 sem DY**: 43/47 não têm NENHUM market_cap em market_snapshots (Yahoo não cobre esses tickers). 4/47 têm market_cap mas fora da janela de anchoring. NÃO é problema de TTM insuficiente nem de DFC parsing.

**Fix real**: snapshot refresh para esses 43 tickers (Yahoo ou brapi). Recompute de DY sem market_cap é impossível.

**Reclassificação**: de "recompute script" para "market data ingestion gap" — escopo diferente.

---

## 1. Micro Feature

**Subir DY coverage de 81.9% para ~92% via ITR backfill (mais quarters no TTM), fechando o gap com NBY coverage.**

## 2. Problem

DY está em 81.9% (190/232). NBY está em 92.0%. A diferença (42 issuers) cria ativos no `secondaryRanking` desnecessariamente — têm NBY mas não DY, logo NPY=NULL.

Decomposição dos 42 missing:

| Causa | Count | Recuperável? |
|-------|-------|:----------:|
| TTM insuficiente (<4 quarters) | ~23 | Sim — ITR backfill |
| Yahoo market data gap | ~11 | Não (sem market_cap) |
| No-dividend genuíno + sem DFC | ~8 | Não (estrutural) |

## 3. Outcome

- DY coverage sobe de 81.9% para ~92% via ITR backfill
- ~23 issuers migram de `secondaryRanking` para `primaryRanking`
- NPY coverage sobe proporcionalmente
- Zero mudança de fórmula ou lógica

## 4. Why Now

O gap entre DY (81.9%) e NBY (92.0%) é a razão pela qual 42 ativos ficam no secondary. Fechar esse gap maximiza o primaryRanking sem mudar a fórmula.

**Correção do follow-up**: FU-P5-2 descrevia DY a 49.6% como "sole bottleneck blocking". Na realidade DY já passa o gate (81.9% > 70%). O follow-up deve ser reclassificado de `blocking` para `degraded` — melhoria, não blocker.

---

## 5. Current System

### DY coverage breakdown (pós zero-semantics)

| Status | Count | % |
|--------|-------|---|
| DY computed (TTM ou DY=0) | 190 | 81.9% |
| DY NULL — TTM insuficiente | 23 | 9.9% |
| DY NULL — sem market_cap | 11 | 4.7% |
| DY NULL — sem DFC coverage | 8 | 3.4% |

### TTM insuficiente — causa raiz

O TTM engine requer 4 quarters standalone consecutivos. Se um issuer tem DFP 2024 (annual) mas falta ITR 2024-Q1/Q2/Q3, o TTM não computa.

**Fix**: backfill de ITR 2024 para esses issuers. Os ZIPs CVM já foram baixados no Plan 5 — os statement_lines existem. O que falta é recomputar as métricas.

---

## 6. Requirements

### R1: Identificar os 23 issuers com TTM insuficiente

Query de diagnóstico para confirmar quais issuers ganhariam DY com mais quarters.

### R2: Recomputar DY/NPY para issuers com dados suficientes

Rodar MetricsEngine para os 23 issuers alvo.

### R3: Refresh compat view

Após recompute, refresh da materialized view.

### R4: Atualizar FU-P5-2 no ledger

Reclassificar de `blocking` para `degraded`. Documentar que DY já passa o gate.

---

## 7. Appetite

- **Level**: Small — diagnóstico + recompute + refresh
- **Must-fit**: R1 (diagnóstico) + R2 (recompute) + R3 (refresh)
- **First cuts**: Se recompute for complexo, aceitar coverage atual (81.9% já passa gate)

**NOTA**: Este FU pode ser um **script operacional** em vez de um plan completo. O shape existe para documentar a decisão, não para justificar semanas de build.

---

## 8. Boundaries / No-Gos

- NAO mudar canonical_mapper (patterns são suficientes)
- NAO mudar TTM engine
- NAO mudar DY formula
- NAO buscar fontes alternativas de market data neste scope
- NAO mexer no ranking (melhoria de dados, não de fórmula)

---

## 9. Risks

### RH1: Recompute pode não ganhar 23 issuers (BAIXO)

Alguns dos 23 podem ter dados insuficientes por outras razões (escopo mismatch, DFP vs ITR overlap).

**Mitigação**: diagnóstico primeiro (R1), depois recompute apenas para os confirmados.

---

## 10. Build Scope

**Scope único**: Script operacional.

1. Query de diagnóstico (quais issuers ganham DY com recompute)
2. Recompute DY + NPY para issuers alvo
3. Refresh compat view
4. Report: coverage antes/depois

**Done**: DY coverage >= 88%. Issuers migrados de secondary para primary documentados.
