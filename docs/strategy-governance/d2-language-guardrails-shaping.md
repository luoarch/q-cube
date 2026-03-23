# D2 — Language Guardrails

## Status: BUILD COMPLETE — Approved

---

## 1. Micro Feature

**Enforce methodologically honest language across all product surfaces.** Every page that shows strategy results, rankings, or scores includes a disclaimer anchoring interpretation. Tooltips clarify ambiguous metrics. Terminology updated to avoid over-claiming.

---

## 2. Problem

The system computes rankings, scores, and backtests — but the UI labels could imply recommendation, validated performance, or investment advice. Without language guardrails:

- "Top #1" implies the system recommends that stock
- "Holdings do ranking" implies a portfolio recommendation
- "Composite Score" with HIGH/MEDIUM/LOW badges implies quality judgment
- Backtest results shown without context could imply validated alpha

---

## 3. Design

### Core principle

> The system describes what it computed, never what the user should do. Rankings are orderings, not recommendations.

### Centralized module: `MethodologicalDisclaimer.tsx`

4 disclaimer components + 1 tooltip map, imported by each surface.

### Disclaimers applied

| Surface | Component | Message |
|---------|-----------|---------|
| `/ranking` | `RankingDisclaimer` | Ranking quantitativo baseado em EY + ROC (Greenblatt). Ordenação por fórmula, não recomendação de investimento. Nenhuma estratégia deste sistema foi empiricamente promovida. |
| `/portfolio` | `PortfolioDisclaimer` | Composição derivada do último ranking executado. Não constitui carteira recomendada. Estratégia subjacente não promovida — resultados de pesquisa, não evidência de performance. |
| `/backtest` | `BacktestDisclaimer` | Backtest com dados PIT e custos reais (BRAZIL_REALISTIC). Resultados passados não garantem performance futura. Universo congelado (frozen policy), benchmark price-only (sem reinvestimento de dividendos). |
| `/home` | `HomeDisclaimer` | Ferramenta quantitativa de screening. Ordenações por fórmula, não recomendações. |
| `/dashboard` | `RankingDisclaimer` | (same as ranking) |

### Tooltips (`GUARDRAIL_TOOLTIPS`)

| Key | Text |
|-----|------|
| `compositeScore` | Score composto percentil (ROIC + EY + ROE + margens). Métrica relativa ao universo, não indicador absoluto de qualidade. |
| `topRank` | Posição no ranking quantitativo por fórmula (EY + ROC). Ordenação, não recomendação. |
| `factorAnalysis` | Fatores percentil relativos ao universo Core. Indicam posição relativa, não qualidade absoluta. |
| `dividendYield` | DY calculado via TTM CVM filings / market cap Yahoo. Dual-trail: exact (vendor) e free-source (CVM proxy). |
| `thesisBucket` | Classificação do Plan 2 (commodity affinity + dollar fragility). Baseada em rubrics, não em backtest. |

### Terminology fixes

| Before | After | Why |
|--------|-------|-----|
| "Top #1" | "Rank #1 (fórmula)" | Removes recommendation implication |
| "Ativos no Ranking" | "Ativos no Screening" | "Screening" is neutral, "ranking" implies ordered recommendation |
| "Top 10 holdings do ultimo ranking" | "Top 10 do último screening quantitativo" | Removes "holdings" (implies ownership) and "ranking" |

---

## 4. Appetite

**Level: XS** — 1 build scope

---

## 5. Boundaries / No-Gos

- Do NOT change computation logic
- Do NOT change API responses
- Do NOT add legal disclaimers (this is methodological, not legal)
- Do NOT make disclaimers dismissible (they are persistent context)
- Disclaimers are compact (1-2 lines, 11px) — informative, not intrusive

---

## 6. Validation Plan

| Check | Pass criteria |
|-------|---------------|
| V1 — Ranking | Disclaimer visible below header |
| V2 — Portfolio | Disclaimer visible, "screening" terminology |
| V3 — Backtest | Disclaimer visible in result area |
| V4 — Home | Disclaimer visible, "Rank #1 (fórmula)" not "Top #1" |
| V5 — Dashboard | Disclaimer visible |
| V6 — Asset detail | Composite Score has tooltip, Factor Analysis has tooltip |
| V7 — No over-claim | Zero instances of "recomendação", "melhor ação", "comprovado" in UI |
| V8 — Typecheck | Clean |

---

## 7. Close Summary

### Delivered

1. `MethodologicalDisclaimer.tsx` — 4 disclaimer components + tooltip map
2. Applied to 6 surfaces: ranking, portfolio, backtest, home, dashboard, asset detail
3. Terminology fixes: 3 label changes
4. Tooltips on Composite Score and Factor Analysis

### What this closes

The product now speaks the same language as the methodology:
- Rankings are described as formula orderings, not recommendations
- No strategy is presented as promoted or validated
- Backtest context includes PIT/cost/benchmark limitations
- Scores are described as relative percentiles, not absolute quality

### What this does NOT close

- Legal disclaimers (separate concern)
- Automated language validation (would need NLP/linting)
- Language in AI Council chat responses (separate surface)

---

## 8. Tech Lead Handoff

### What changed
- New: `src/components/MethodologicalDisclaimer.tsx`
- Modified: `/ranking`, `/portfolio`, `/dashboard`, `/backtest`, `/home`, `/assets/[ticker]`

### What did NOT change
- API responses
- Computation logic
- Strategy registry
- Backtest engine
