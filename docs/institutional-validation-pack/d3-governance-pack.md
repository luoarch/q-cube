# Governance Pack

## 1. Proxy vs Hard Data

| Field | Type | Source | Notes |
|-------|:----:|--------|-------|
| EBIT, revenue, margins | Hard | CVM DFP/ITR filings | Audited financial statements |
| ROIC, ROE, debt/EBITDA | Hard (derived) | Computed from statement_lines | Standard ratios |
| Price, volume | Hard | Yahoo Finance | Real-time market data |
| Market cap | Hard (when from Yahoo) | Yahoo Finance | `regularMarketCap` |
| Market cap | **Derived** (historical) | Close × CVM shares | For backfill periods |
| Earnings yield | Hard (derived) | EBIT / (market_cap + net_debt) | Depends on market data freshness |
| Quality score (refiner) | **Model output** | 4-block weighted composite | Score reliability tracked |
| Thesis bucket | **Model output** | Commodity/fragility scoring | Provenance: QUANTITATIVE/SECTOR_PROXY/AI_ASSISTED |
| Valuation label | **Proxy** | EY percentile within sector | Not intrinsic value |
| Implied value range | **Proxy** | EY normalization | Suppressed when > 300% upside |
| Implied yield | **Proxy** | EY + NPY (static, no growth) | Outlier flagged when > 40% |
| Decision status | **Classification** | Threshold-based rules | Not recommendation |

## 2. Data Validity Rules

| Condition | Result |
|-----------|--------|
| `market_cap = 0` or negative | `valuation_valid = false`, implied value = NULL |
| `market_cap < R$1` | Hard invalidation of all market-derived fields |
| Snapshot staleness > 7 days | Market data NULLed in compat view |
| Filing `publication_date > as_of` | PIT violation — filing excluded from query |

## 3. Suppression Rules

| Condition | What is suppressed | Displayed instead |
|-----------|-------------------|------------------|
| Implied upside > 300% | `impliedValueRange`, `impliedPrice`, `upside` | "Proxy valuation unavailable" + reason |
| Market cap invalid | All valuation-derived fields | "Market data invalid" |
| Implied yield > 40% | `outlier = true` | Warning: "Outlier — verificar EV/dados" |

Suppression ≠ rejection. The valuation *label* (CHEAP/FAIR/EXPENSIVE) is preserved for context when suppression occurs — only the numerical proxy is hidden.

## 4. Confidence Breakdown

### Composite score

```
confidence = max(0, (data_completeness × 0.6 + evidence_quality × 0.4) - penalties)
```

### Five boolean flags

| Flag | Trigger | Penalty |
|------|---------|:------:|
| `missingRefinerData` | No refinement_results for issuer | -0.15 |
| `missingThesisData` | No plan2_thesis_scores for issuer | (reduces evidence_quality) |
| `sectorFallbackUsed` | Sector has < 5 issuers for EY percentile | -0.10 |
| `driversCountPenalty` | Fewer than 3 drivers identified | -0.10 |
| `valuationMissingPenalty` | No earnings_yield or market data | -0.20 |

### Labels

| Label | Score range | Meaning |
|-------|:----------:|---------|
| HIGH | ≥ 0.70 | Full data, high evidence quality, no penalties |
| MEDIUM | 0.40–0.69 | Partial data or moderate penalties |
| LOW | < 0.40 | Significant gaps — system blocks decision |

## 5. When UI Must Not Show Numbers

1. **valuation_valid = false**: No implied price, no range, no upside percentage
2. **Suppressed by sanity guard**: Show "Proxy valuation unavailable" text, not blank or zero
3. **Yield outlier**: Show the number but with explicit warning badge — never as headline

## 6. Strategy Status Registry

| Strategy | Role | Promotion Status | OOS Sharpe | Evidence |
|----------|:----:|:----------------:|:----------:|---------|
| ctrl_original_20m | CONTROL | REJECTED | 0.09 | Walk-forward: worst OOS performer |
| ctrl_brazil_20m | CONTROL | REJECTED | 0.01 | Walk-forward: gates worsened OOS |
| hybrid_20q | FRONTRUNNER | BLOCKED | 1.20 | Walk-forward: 3/3 wins, blocked by sensitivity |

## 7. Language Guardrails

Every surface includes:
- "Ranking quantitativo baseado em EY + ROC. Ordenação por fórmula, não recomendação de investimento."
- "Classificação de pesquisa, não recomendação de investimento" (on decision card)
- "Proxy valuation" label (never "fair value")
- "Implied yield (sem crescimento)" (never "expected return")

Soft enforcement: warning modal before executing rejected/blocked strategies, requiring explicit acknowledgment.
