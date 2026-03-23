# Ticker Decision Engine

## Status: SHAPING COMPLETE — Awaiting Tech Lead approval (v2)

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
2. **Valuation proxy** — cheap / fair / expensive (EY percentile, explicitly a proxy)
3. **Drivers** — 3-5 per ticker, classified by type (structural / cyclical / historical)
4. **Risks** — from refiner flags + fragility + leverage
5. **Implied value range** — from normalized EY (proxy, not DCF)
6. **Implied yield** — EY + NPY (static, no growth assumption)
7. **Confidence** — data completeness + evidence quality, with penalties
8. **Final status** — APPROVED / BLOCKED (with sub-reason) / REJECTED

### Epistemological clarity (proxy vs truth)

| Field | What it IS | What it is NOT |
|-------|-----------|---------------|
| `impliedValueRange` | EY normalization proxy | Fair value / DCF intrinsic value |
| `impliedYield` | Static yield (EY + payout) | Forward-looking expected return |
| `drivers` | Observed signals, classified by temporal nature | Causal predictions |
| `decision.status` | Research classification | Investment recommendation |

---

## 4. Valuation Proxy Model

### Earnings Yield Percentile

```
ey_i = computed_metrics.earnings_yield (EBIT / EV)
ey_sector_median = median(EY for CORE_ELIGIBLE in same sector)
ey_universe_median = median(EY for all CORE_ELIGIBLE)
ey_sector_pctl = percentile_rank(ey_i within sector)
ey_universe_pctl = percentile_rank(ey_i within universe)
```

Sector fallback: if sector has <5 issuers, use universe percentile only.

### Valuation label

```
if ey_sector_pctl >= 70:  CHEAP
elif ey_sector_pctl >= 30: FAIR
else:                      EXPENSIVE
```

### Implied value range (PROXY — not fair value)

```
valuationMethod = "earnings_yield_normalization_proxy"
normalized_ey = ey_sector_median
implied_ev = ebit / normalized_ey
implied_equity = implied_ev - net_debt
implied_price = implied_equity / shares_outstanding
implied_value_low = implied_price * 0.85
implied_value_high = implied_price * 1.15
```

This is a **sector-relative normalization proxy**, not an intrinsic valuation. It answers: "if this company's EY converged to sector median, what would the price be?"

### Implied yield (STATIC — no growth assumption)

```
implied_yield = earnings_yield + net_payout_yield
label = "Implied yield (EY + payout, sem crescimento)"
```

This is what the company currently earns + returns per unit of EV. No projections, no growth. Pure static snapshot.

---

## 5. Driver Identification Logic

### Driver types (FIX #3)

Every driver is classified:

| Type | Meaning | Example |
|------|---------|---------|
| `structural` | Persistent competitive/sector position | "Exposição direta a commodities" |
| `cyclical` | Sensitive to economic/market cycle | "Receita dolarizada (hedge natural)" |
| `historical` | Observed in past data, may not persist | "Margem em expansão (+3pp YoY)" |

### Metric-based drivers (historical by default)

| Signal | Condition | Label | Type |
|--------|-----------|-------|------|
| Margin expansion | gross_margin or net_margin ↑ YoY | "Margem em expansão" | historical |
| Margin compression | gross_margin or net_margin ↓ YoY | "Margem em compressão" | historical |
| ROIC improvement | ROIC ↑ YoY | "Retorno sobre capital crescente" | historical |
| Leverage reduction | debt_to_ebitda ↓ YoY | "Desalavancagem em curso" | historical |
| Revenue growth | revenue ↑ >10% YoY | "Receita em crescimento" | historical |
| Revenue decline | revenue ↓ >10% YoY | "Receita em declínio" | historical |
| Cash generation | cash_conversion > 1.0 | "Forte geração de caixa" | historical |
| Dividend payer | dividend_yield > 0 | "Pagadora de dividendos (DY {x}%)" | structural |
| Buyback | net_buyback_yield > 0.02 | "Recompra de ações relevante" | historical |

### Thesis-based drivers (structural/cyclical)

| Signal | Condition | Label | Type |
|--------|-----------|-------|------|
| Commodity exposure | bucket = A_DIRECT | "Exposição direta a commodities" | structural |
| Indirect commodity | bucket = B_INDIRECT | "Benefício indireto de commodities" | cyclical |
| USD hedge | usd_revenue_offset > 60 | "Receita dolarizada (hedge natural)" | structural |

### Selection: top 5 by magnitude, minimum 3

---

## 6. Risk Extraction Logic

### From refiner red flags (direct reuse)

### From Plan 2 fragility

| Signal | Condition | Label | Critical? |
|--------|-----------|-------|:---------:|
| Dollar fragile | bucket = D_FRAGILE | "Fragilidade cambial elevada" | If + debt_to_ebitda > 3 |
| High USD debt | usd_debt_exposure > 70 | "Dívida em USD significativa" | No |
| Import dependent | usd_import_dependence > 70 | "Dependência de insumos importados" | No |

### From computed metrics

| Signal | Condition | Label | Critical? |
|--------|-----------|-------|:---------:|
| High leverage | debt_to_ebitda > 3.0 | "Alavancagem elevada ({x}x)" | If > 5.0 |
| Negative cash | cash_conversion < 0 | "Geração de caixa negativa" | If < -0.5 |
| Low coverage | interest_coverage < 2.0 | "Cobertura de juros baixa" | If < 1.0 |
| No market data | market_cap is NULL | "Sem dados de mercado" | Yes (blocks valuation) |

---

## 7. Confidence Score (with penalties — FIX #5)

```
base_data = refiner.data_completeness (0-1)
base_evidence = thesis.evidence_quality → 0-1 map

penalties = 0
if valuation is NULL:       penalties += 0.20
if len(drivers) < 3:        penalties += 0.10
if sector_fallback_used:    penalties += 0.10
if refiner_data is NULL:    penalties += 0.15

confidence = max(0, (base_data * 0.6 + base_evidence * 0.4) - penalties)

if confidence >= 0.7:  HIGH
elif confidence >= 0.4: MEDIUM
else:                   LOW
```

---

## 8. Decision Logic (with yield threshold — FIX #4)

```python
MIN_YIELD_THRESHOLD = 0.12  # 12% minimum implied yield

quality = refiner.refinement_score (0-1)
valuation = valuation_label
implied_yield = earnings_yield + net_payout_yield
has_critical_risk = any critical risk flag
confidence = confidence_level

# Step 1: Hard rejections
if has_critical_risk:
    status = REJECTED
    reason = "Risco crítico: {risk_label}"

elif quality < 0.3:
    status = REJECTED
    reason = "Qualidade abaixo do limiar"

elif valuation == "EXPENSIVE" and quality < 0.6:
    status = REJECTED
    reason = "Valuation desfavorável com qualidade insuficiente"

# Step 2: Yield gate
elif implied_yield is not None and implied_yield < MIN_YIELD_THRESHOLD:
    status = BLOCKED
    blockReason = "LOW_YIELD"
    reason = f"Implied yield ({implied_yield:.1%}) abaixo do mínimo ({MIN_YIELD_THRESHOLD:.0%})"

# Step 3: Confidence gate
elif confidence == "LOW":
    status = BLOCKED
    blockReason = "LOW_CONFIDENCE"
    reason = "Evidência insuficiente para decisão"

# Step 4: Data completeness gate
elif valuation is None or quality is None:
    status = BLOCKED
    blockReason = "DATA_MISSING"
    reason = "Dados incompletos para decisão"

# Step 5: Approval
elif quality >= 0.5 and valuation in ("CHEAP", "FAIR") and confidence in ("HIGH", "MEDIUM"):
    status = APPROVED
    reason = "Qualidade adequada, valuation favorável, yield acima do mínimo"

# Step 6: Catch-all
else:
    status = BLOCKED
    blockReason = "MARGINAL"
    reason = "Caso limítrofe — evidência insuficiente para aprovação"
```

### BLOCKED sub-reasons (FIX #6)

| blockReason | Meaning |
|-------------|---------|
| `LOW_YIELD` | Implied yield below 12% threshold |
| `LOW_CONFIDENCE` | Confidence score < 0.4 |
| `DATA_MISSING` | Valuation or quality data unavailable |
| `MARGINAL` | Doesn't clearly meet approval criteria |

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
    "valuationMethod": "earnings_yield_normalization_proxy",
    "earningsYield": 0.142,
    "eyUniversePercentile": 82,
    "eySectorPercentile": 75,
    "eySectorMedian": 0.098,
    "sectorIssuersCount": 12,
    "sectorFallback": false,
    "impliedPrice": 78.50,
    "impliedValueRange": [66.73, 90.28],
    "currentPrice": 62.30,
    "upside": 0.26
  },

  "impliedYield": {
    "earningsYield": 0.142,
    "netPayoutYield": 0.085,
    "totalYield": 0.227,
    "label": "Implied yield 22.7% (EY + payout, sem crescimento)",
    "meetsMinimum": true,
    "minimumThreshold": 0.12
  },

  "drivers": [
    {"signal": "Exposição direta a commodities", "source": "plan2_thesis", "driverType": "structural", "magnitude": "high"},
    {"signal": "Forte geração de caixa (1.35x)", "source": "computed_metrics", "driverType": "historical", "value": 1.35},
    {"signal": "Receita dolarizada (hedge natural)", "source": "plan2_thesis", "driverType": "structural", "magnitude": "high"},
    {"signal": "ROIC crescente (+3.2pp YoY)", "source": "computed_metrics", "driverType": "historical", "value": "+3.2pp"},
    {"signal": "Dividendos consistentes (DY 8.5%)", "source": "computed_metrics", "driverType": "structural", "value": 0.085}
  ],

  "risks": [
    {"signal": "Alavancagem elevada (2.1x)", "source": "computed_metrics", "critical": false},
    {"signal": "Dependência de ciclo de commodities", "source": "plan2_thesis", "critical": false}
  ],

  "confidence": {
    "score": 0.78,
    "label": "HIGH",
    "dataCompleteness": 0.90,
    "evidenceQuality": "HIGH_EVIDENCE",
    "penalties": []
  },

  "decision": {
    "status": "APPROVED",
    "blockReason": null,
    "reason": "Qualidade adequada, valuation favorável, yield acima do mínimo",
    "governanceNote": "Estratégia subjacente (ctrl_brazil_20m) é controle rejeitado. Classificação reflete dados fundamentalistas, não performance empírica da estratégia."
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
- Do NOT override strategy governance
- Do NOT present as investment advice
- `impliedValueRange` is PROXY — never call it "fair value"
- `impliedYield` is STATIC — never call it "expected return"
- APPROVED/BLOCKED/REJECTED is a **research classification**

---

## 11. Rabbit Holes

| ID | Risk | Mitigation |
|----|------|------------|
| RH1 | Sector <5 issuers → percentile meaningless | Fall back to universe percentile, +0.10 confidence penalty |
| RH2 | Missing market data → no EY → no valuation | valuation=NULL, status=BLOCKED(DATA_MISSING) |
| RH3 | Refiner not run → no quality scores | quality=NULL, status=BLOCKED(DATA_MISSING) |
| RH4 | Thesis not run → no thesis drivers | Metrics-only drivers, confidence reduced |

---

## 12. Build Scopes

### S1 — Decision function core

`compute_ticker_decision(session, ticker) -> TickerDecision`

New files in `services/quant-engine/src/q3_quant_engine/decision/`:
- `types.py` — dataclasses
- `valuation.py` — EY percentile, implied value
- `drivers.py` — driver extraction + classification
- `risks.py` — risk extraction + critical flag
- `confidence.py` — score with penalties
- `engine.py` — orchestrator + decision logic

### S2 — Batch + validation

Script + tests for Top 10. Determinism, completeness, governance link.

### S3 — API + UI

NestJS endpoint + Zod schema + asset detail card.

---

## 13. Close Summary

_Not started._

---

## 14. Tech Lead Handoff

_Not started._
