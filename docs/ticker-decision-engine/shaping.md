# Ticker Decision Engine

## Status: SHAPING COMPLETE — Awaiting Tech Lead approval

---

## 1. Problem

Q3 answers "which are the best assets?" (ranking) but not "should I act on this asset?" (decision). The system stops at an ordered list. There is no per-ticker structured output combining quality, valuation, drivers, risks, and a final deterministic call.

---

## 2. Appetite

**Level: M** — 3 build scopes

---

## 3. Solution

### Core concept

A **deterministic decision function** that takes the Top N ranked assets and produces a standardized per-ticker report with:

1. **Quality composite** — from existing refiner blocks
2. **Valuation classification** — cheap / fair / expensive (from EY percentile)
3. **Drivers** — 3-5 per ticker, derived from metrics + thesis
4. **Risks** — derived from refiner flags + fragility + leverage
5. **Fair value range** — implied from normalized EY
6. **Expected return** — total shareholder yield
7. **Confidence** — data completeness + evidence quality
8. **Final status** — APPROVED / BLOCKED / REJECTED

### What already exists (70% reuse)

| Component | Source | Reuse |
|-----------|--------|:-----:|
| Quality scores (4 blocks) | Refiner | Direct |
| Red/green flags | Refiner | Direct |
| Earnings yield | computed_metrics | Direct |
| Sector | issuers.sector (CVM) | Direct |
| Commodity affinity | Plan 2 thesis | Direct |
| Dollar fragility | Plan 2 thesis | Direct |
| Thesis bucket (A/B/C/D) | Plan 2 thesis | Direct |
| Debt/EBITDA, interest coverage | computed_metrics | Direct |
| Margins, ROIC, ROE | computed_metrics | Direct |
| DY, NBY, NPY | computed_metrics | Direct |
| Data completeness | Refiner | Direct |
| Market cap, price | market_snapshots | Direct |

### What needs to be COMPOSED (new logic, existing data)

| Component | Logic | Data source |
|-----------|-------|-------------|
| **Valuation percentile** | EY rank within sector + universe | computed_metrics.earnings_yield |
| **Valuation label** | Percentile → cheap/fair/expensive | EY percentile thresholds |
| **Fair value range** | Implied price from normalized EY | EY median × EV → equity → price |
| **Expected return** | EY + NPY (total shareholder yield) | computed_metrics |
| **Driver extraction** | Top contributors from quality + thesis | Refiner flags + Plan 2 dims |
| **Risk extraction** | Top risks from refiner + fragility | Refiner red flags + Plan 2 |
| **Confidence score** | Data completeness × evidence quality | Refiner completeness + thesis provenance |
| **Decision logic** | Threshold-based classification | All of the above |

---

## 4. Valuation Model (TL-approved approach)

### Earnings Yield Percentile

For each ticker `i` in the Top N:

```
ey_i = computed_metrics.earnings_yield (EBIT / EV)
ey_sector_median = median(EY for all CORE_ELIGIBLE in same sector)
ey_universe_median = median(EY for all CORE_ELIGIBLE)
ey_sector_pctl = percentile_rank(ey_i within sector)
ey_universe_pctl = percentile_rank(ey_i within universe)
```

### Valuation label

```
if ey_sector_pctl >= 70:  CHEAP
elif ey_sector_pctl >= 30: FAIR
else:                      EXPENSIVE
```

Why sector-relative: avoids comparing utilities (high EY) with tech (low EY).

### Fair value range

```
normalized_ey = ey_sector_median  (what "fair" looks like)
implied_ev = ebit / normalized_ey
implied_equity = implied_ev - net_debt
implied_price = implied_equity / shares_outstanding
fair_value_low = implied_price * 0.85  (15% margin of safety)
fair_value_high = implied_price * 1.15
```

### Expected return (total shareholder yield)

```
expected_return = earnings_yield + net_payout_yield
```

This is the **Greenblatt-compatible implied return**: how much the company earns per unit of enterprise value, plus how much it returns to shareholders. No projections needed.

---

## 5. Driver Identification Logic

For each ticker, select the **top 3-5 most significant** from:

### Metric-based drivers (from computed_metrics + statement_lines)

| Signal | Condition | Driver label |
|--------|-----------|-------------|
| Margin expansion | gross_margin or net_margin increased YoY | "Margem em expansão" |
| Margin compression | gross_margin or net_margin decreased YoY | "Margem em compressão" |
| ROIC improvement | ROIC increased YoY | "Retorno sobre capital crescente" |
| Leverage reduction | debt_to_ebitda decreased YoY | "Desalavancagem em curso" |
| Leverage increase | debt_to_ebitda increased YoY | "Alavancagem crescente" |
| Revenue growth | revenue increased >10% YoY | "Receita em crescimento" |
| Revenue decline | revenue decreased >10% YoY | "Receita em declínio" |
| Cash generation | cash_conversion > 1.0 | "Forte geração de caixa" |
| Dividend payer | dividend_yield > 0 | "Pagadora de dividendos (DY {x}%)" |
| Buyback | net_buyback_yield > 0.02 | "Recompra de ações relevante" |

### Thesis-based drivers (from Plan 2)

| Signal | Condition | Driver label |
|--------|-----------|-------------|
| Commodity exposure | bucket = A_DIRECT | "Exposição direta a commodities" |
| Indirect commodity | bucket = B_INDIRECT | "Benefício indireto de commodities" |
| USD hedge | usd_revenue_offset > 60 | "Receita dolarizada (hedge natural)" |

### Selection rule

1. Sort all applicable drivers by **magnitude of signal** (YoY change size, or score level)
2. Take top 5
3. If fewer than 3 apply, note "Poucos drivers identificados"

---

## 6. Risk Extraction Logic

### From refiner red flags (direct reuse)

The refiner already produces `flags_json` with structured red/green flags. Extract all red flags.

### From Plan 2 fragility

| Signal | Condition | Risk label |
|--------|-----------|-----------|
| Dollar fragile | bucket = D_FRAGILE | "Fragilidade cambial elevada" |
| High USD debt | usd_debt_exposure > 70 | "Dívida em USD significativa" |
| Import dependent | usd_import_dependence > 70 | "Dependência de insumos importados" |

### From computed metrics

| Signal | Condition | Risk label |
|--------|-----------|-----------|
| High leverage | debt_to_ebitda > 3.0 | "Alavancagem elevada ({x}x)" |
| Negative cash conversion | cash_conversion < 0 | "Geração de caixa negativa" |
| Low interest coverage | interest_coverage < 2.0 | "Cobertura de juros baixa ({x}x)" |
| No market data | market_cap is NULL | "Sem dados de mercado atualizados" |

### Critical risk flag

A risk is **critical** if any of:
- debt_to_ebitda > 5.0
- cash_conversion < -0.5
- interest_coverage < 1.0
- bucket = D_FRAGILE AND debt_to_ebitda > 3.0

Critical risks force REJECTED status.

---

## 7. Confidence Score

```
data_score = refiner.data_completeness (0-1)
evidence_score = thesis.evidence_quality mapped to 0-1:
  HIGH_EVIDENCE = 1.0
  MIXED_EVIDENCE = 0.6
  LOW_EVIDENCE = 0.3
  (no thesis data) = 0.5

confidence = (data_score * 0.6) + (evidence_score * 0.4)

if confidence >= 0.7:  HIGH
elif confidence >= 0.4: MEDIUM
else:                   LOW
```

---

## 8. Decision Logic

```
quality = refiner.refinement_score (0-1)
valuation = valuation_label (CHEAP / FAIR / EXPENSIVE)
has_critical_risk = any critical risk flag
confidence = confidence_level (HIGH / MEDIUM / LOW)

if has_critical_risk:
    status = REJECTED
    reason = "Risco crítico: {risk_label}"

elif quality < 0.3:
    status = REJECTED
    reason = "Qualidade abaixo do limiar (score={quality})"

elif valuation == "EXPENSIVE" and quality < 0.6:
    status = REJECTED
    reason = "Valuation desfavorável com qualidade insuficiente"

elif quality >= 0.5 and valuation in ("CHEAP", "FAIR") and confidence in ("HIGH", "MEDIUM"):
    status = APPROVED
    reason = "Qualidade adequada, valuation favorável, evidência suficiente"

else:
    status = BLOCKED
    reason = "Evidência insuficiente para decisão (confidence={confidence})"
```

---

## 9. Output Format (SSOT)

```json
{
  "ticker": "VALE3",
  "name": "Vale S.A.",
  "sector": "Mineração",
  "generatedAt": "2026-03-23T15:00:00Z",

  "quality": {
    "score": 0.72,
    "label": "HIGH",
    "components": {
      "earningsQuality": 0.85,
      "safety": 0.65,
      "operatingConsistency": 0.70,
      "capitalDiscipline": 0.68
    }
  },

  "valuation": {
    "label": "CHEAP",
    "earningsYield": 0.142,
    "eyUniversePercentile": 82,
    "eySectorPercentile": 75,
    "eySectorMedian": 0.098,
    "impliedPrice": 78.50,
    "fairValueRange": [66.73, 90.28],
    "currentPrice": 62.30,
    "upside": 0.26
  },

  "expectedReturn": {
    "earningsYield": 0.142,
    "netPayoutYield": 0.085,
    "totalShareholderYield": 0.227,
    "label": "22.7% implied"
  },

  "drivers": [
    {"signal": "Exposição direta a commodities", "source": "plan2_thesis", "magnitude": "high"},
    {"signal": "Forte geração de caixa", "source": "computed_metrics", "value": 1.35},
    {"signal": "Receita dolarizada (hedge natural)", "source": "plan2_thesis", "magnitude": "high"},
    {"signal": "Retorno sobre capital crescente", "source": "computed_metrics", "value": "+3.2pp YoY"},
    {"signal": "Pagadora de dividendos (DY 8.5%)", "source": "computed_metrics", "value": 0.085}
  ],

  "risks": [
    {"signal": "Alavancagem elevada (2.1x)", "source": "computed_metrics", "critical": false},
    {"signal": "Dependência de ciclo de commodities", "source": "plan2_thesis", "critical": false}
  ],

  "confidence": {
    "score": 0.78,
    "label": "HIGH",
    "dataCompleteness": 0.90,
    "evidenceQuality": "HIGH_EVIDENCE"
  },

  "decision": {
    "status": "APPROVED",
    "reason": "Qualidade adequada, valuation favorável, evidência suficiente",
    "governanceNote": "Estratégia subjacente (ctrl_brazil_20m) é controle rejeitado. Decisão reflete dados fundamentalistas, não performance empírica da estratégia."
  },

  "provenance": {
    "rankingSource": "magic_formula_brazil",
    "refinerRunId": "abc-123",
    "thesisRunId": "def-456",
    "metricsReferenceDate": "2024-12-31",
    "snapshotDate": "2026-03-19",
    "universePolicy": "v1"
  }
}
```

---

## 10. Boundaries / No-Gos

- Do NOT implement DCF or WACC
- Do NOT use external data sources
- Do NOT require manual input
- Do NOT change ranking or refiner logic
- Do NOT override strategy governance (decision.governanceNote links to registry)
- Do NOT present decisions as investment advice (language guardrails apply)
- APPROVED/BLOCKED/REJECTED is a **research classification**, not investment recommendation

---

## 11. Rabbit Holes

### RH1 — Sector with <3 issuers
Some CVM sectors have very few CORE_ELIGIBLE issuers. Sector percentile becomes meaningless.
**Mitigation**: Fall back to universe percentile if sector has <5 issuers.

### RH2 — Missing market data
No market_cap → no EY → no valuation.
**Mitigation**: valuation = NULL, status = BLOCKED with reason "Sem dados de mercado".

### RH3 — Refiner not run
Refiner only runs for top ~30 per strategy run. Tickers outside that set have no quality scores.
**Mitigation**: If no refiner data, quality = NULL, status = BLOCKED.

### RH4 — Thesis not run
Plan 2 thesis may not cover all tickers.
**Mitigation**: Missing thesis → drivers/risks from metrics only, confidence reduced.

---

## 12. Build Scopes

### S1 — Decision function core

**Objective**: Python function `compute_ticker_decision(session, ticker) -> TickerDecision` that produces the full output for one ticker.

**Files**:
- New: `services/quant-engine/src/q3_quant_engine/decision/engine.py`
- New: `services/quant-engine/src/q3_quant_engine/decision/valuation.py`
- New: `services/quant-engine/src/q3_quant_engine/decision/drivers.py`
- New: `services/quant-engine/src/q3_quant_engine/decision/risks.py`
- New: `services/quant-engine/src/q3_quant_engine/decision/types.py`

**Done when**: Function produces complete JSON output for 1 ticker.

### S2 — Batch execution + validation

**Objective**: Run decision engine for Top 10 from latest ranking. Validate all outputs are complete and deterministic.

**Files**:
- New: `services/quant-engine/scripts/run_ticker_decisions.py`
- New: `services/quant-engine/tests/test_decision_engine.py`

**Validation**:

| Check | Pass criteria |
|-------|---------------|
| V1 — Completeness | 10/10 tickers produce full output |
| V2 — Determinism | Running twice produces identical output |
| V3 — No nulls in required fields | quality, valuation, drivers, risks, decision all present |
| V4 — Governance link | decision.governanceNote references strategy registry |
| V5 — Provenance | Every output has complete provenance block |
| V6 — Status distribution | At least 1 APPROVED, 1 BLOCKED or REJECTED (proves thresholds work) |

### S3 — API + UI exposure

**Objective**: NestJS endpoint + asset detail page integration.

**Files**:
- `apps/api/src/decision/` — controller, service, module
- `apps/web/app/(dashboard)/assets/[ticker]/page.tsx` — decision card
- `packages/shared-contracts/src/domains/decision.ts` — Zod schema

**Done when**: `/assets/VALE3` shows the Ticker Decision card with all sections.

---

## 13. Close Summary

_Not started._

---

## 14. Tech Lead Handoff

_Not started._
