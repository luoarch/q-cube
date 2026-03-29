# FU-P6-1 — Frontend Ranking Adaptation

## Status: SHAPED — awaiting TL review

---

## 1. Micro Feature

**Adaptar o frontend Next.js ao novo shape split-model do ranking (`primaryRanking`/`secondaryRanking`), substituindo todas as referências a `magicFormulaRank` por `rankWithinModel` e consumindo a nova resposta sem shim.**

## 2. Problem

O backend agora retorna `{ primaryRanking, secondaryRanking, summary }` mas o frontend espera `{ data: RankingItem[] }` com campo `magicFormulaRank`. A página `/ranking` e todos os componentes 3D estão quebrados.

## 3. Outcome

- Página `/ranking` funcional com dados reais do split-model
- Componentes 3D (QCube, Galaxy, ParticleCloud) funcionam com `rankWithinModel`
- Dashboard home mostra top-5 do primaryRanking
- Zero shim — frontend consome shape novo diretamente

## 4. Why Now

App quebrado. Ranking é a feature principal do Q3.

---

## 5. Current System — Impacto

6 arquivos frontend precisam mudar:

| Arquivo | Severidade | Mudança |
|---------|-----------|---------|
| `hooks/api/useRanking.ts` | CRITICAL | Consumir `splitRankingResponse` em vez de `paginatedRanking` |
| `ranking/page.tsx` | HIGH | `magicFormulaRank` → `rankWithinModel`, tabs primary/secondary |
| `assets/[ticker]/page.tsx` | HIGH | Rank display |
| `three/objects/AssetParticleCloud.tsx` | HIGH | Top-10 highlighting usa `rankWithinModel` |
| `three/ui/HudTooltip.tsx` | HIGH | Rank no tooltip |
| `three/hooks/useAssetPositions.ts` | CRITICAL | `qualityScore` não existe — derivar de `quality` enum |

## 6. Requirements

### R1: Hook `useRanking`

Retorna `{ primaryRanking, secondaryRanking, summary, isLoading, error }`. Sem paginação (D1 do Plan 6).

### R2: Ranking page com tabs

- Tab "Primary (NPY+ROC)" — 179 ativos fully_evaluated
- Tab "Secondary (EY+ROC)" — 58 ativos partially_evaluated com badge visual
- Coluna `#` usa `rankWithinModel`
- Filtros de setor/quality permanecem

### R3: Componentes 3D

- `rankWithinModel` substitui `magicFormulaRank` em top-10 highlighting
- `qualityScore` derivado: high=0.8, medium=0.5, low=0.2
- Dados vêm de `primaryRanking` apenas (secondary não aparece no 3D)

### R4: Dashboard

- Top-5 do `primaryRanking`
- Contadores: `summary.primaryCount`, `summary.secondaryCount`

---

## 7. Appetite

- **Level**: Small — 6 arquivos, substituições mecânicas
- **Must-fit**: Hook + ranking page + 3D fix + dashboard
- **First cuts**: Tabs primary/secondary (pode ser MVP sem tabs, mostrando só primary)

---

## 8. Boundaries / No-Gos

- NAO mudar backend
- NAO criar endpoint de compat
- NAO mexer em thesis ranking (separado)
- NPY/model badges são enhancement, não blocker

---

## 9. Build Scope

**Scope único**: Adaptar 6 arquivos ao novo shape.

**Done**: Página `/ranking` funcional, 3D renderiza, dashboard mostra top-5.
