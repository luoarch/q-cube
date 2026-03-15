# Spec 01 — Universe & Eligibility

Responde perguntas: 1, 2, 3, 4, 15, 16, 17, 18, 19

---

## Decisao-mae: Qual e o universo do Plano 2?

### Universo = todos os ativos que passam no core screening

O universo do Plano 2 **NAO depende do refiner**.
O universo e: todos os ativos que passam nos filtros do `magic_formula_brazil`.

Justificativa:
- O refiner roda apenas no top 30 (hardcoded em `strategy.py:55`, `top_n=30`).
- Limitar Plano 2 ao top 30 destruiria o proposito (re-ranking tematico de universo mais amplo).
- Os filtros do core screening ja garantem investibilidade basica.
- Os computed_metrics existem para TODOS os issuers, nao apenas top 30.

### Core Screening (filtros existentes em ranking.py:269-276)

| Filtro | Threshold | Fonte |
|--------|-----------|-------|
| Setor excluido | "financeiro", "utilidade publica" | issuer.sector (CVM cadastro) |
| Min volume medio diario | R$ 1.000.000 | market_snapshots.avg_daily_volume |
| Min market cap | R$ 500.000.000 | market_snapshots.market_cap |
| EBIT positivo | > 0 | statement_lines.ebit |

Estimativa: ~80-150 empresas passam esses filtros no universo B3 atual.

---

## Definicao: "Aprovada no core"

**"Aprovada no core" = passou nos 4 filtros do core screening acima.**

NAO significa:
- estar no top 30
- ter refiner score
- ter adjusted rank
- ter quality badge

Esses sao refinamentos opcionais, nao gates de elegibilidade.

---

## Base Eligibility (gate de entrada no Plan 2)

### Regra

```
eligibleForPlan2 =
  passedCoreScreening                    // 4 filtros acima
  AND hasValidFinancials                 // tem statement_lines recentes
  AND interestCoverage >= 1.5            // pode servir divida
  AND debtToEbitda <= 6.0                // nao sobrecarregado
```

### Justificativa de cada criterio

| Criterio | Por que | Fonte | Disponivel? |
|----------|---------|-------|-------------|
| passedCoreScreening | Ja exclui financeiros, utilities, micro caps, EBIT negativo | ranking.py filters | Sim |
| hasValidFinancials | Evita empresa sem dados recentes | statement_lines.reference_date | Sim |
| interestCoverage >= 1.5 | Empresa que nao cobre juros nao deveria entrar em tese tematica | computed_metrics.interest_coverage | Sim, para todos |
| debtToEbitda <= 6.0 | Empresa excessivamente alavancada e risco sistemico, nao de tese | computed_metrics.debt_to_ebitda | Sim, para todos |

### Por que o refiner NAO entra na elegibilidade

1. Refiner so roda no top 30 — limitaria artificialmente o universo
2. Refiner e quality overlay, nao investibility gate
3. Os criterios de elegibilidade acima (interest_coverage, debt_to_ebitda) ja capturam o minimo de saude financeira
4. Se o refiner for expandido no futuro para mais ativos, a elegibilidade nao precisa mudar

### Assinatura canonica (SSOT — replicada em todos os docs)

```python
def check_base_eligibility(
    passed_core_screening: bool,
    has_valid_financials: bool,
    interest_coverage: float | None,
    debt_to_ebitda: float | None,
) -> BaseEligibility
```

```python
@dataclass
class BaseEligibility:
    eligible_for_plan2: bool
    failed_reasons: list[str]   # ex: ["interest_coverage_below_1.5", "missing_financials"]
    passed_core_screening: bool
    has_valid_financials: bool
    interest_coverage: float | None
    debt_to_ebitda: float | None
```

**Logica:**
```python
def check_base_eligibility(...) -> BaseEligibility:
    reasons = []
    if not passed_core_screening:
        reasons.append("failed_core_screening")
    if not has_valid_financials:
        reasons.append("missing_valid_financials")
    if interest_coverage is None or interest_coverage < ELIGIBILITY_MIN_INTEREST_COVERAGE:
        reasons.append("interest_coverage_below_1.5")
    if debt_to_ebitda is None or debt_to_ebitda > ELIGIBILITY_MAX_DEBT_TO_EBITDA:
        reasons.append("debt_to_ebitda_above_6.0")

    return BaseEligibility(
        eligible_for_plan2=len(reasons) == 0,
        failed_reasons=reasons,
        passed_core_screening=passed_core_screening,
        has_valid_financials=has_valid_financials,
        interest_coverage=interest_coverage,
        debt_to_ebitda=debt_to_ebitda,
    )
```

**Constantes (em config.py):**
- `ELIGIBILITY_MIN_INTEREST_COVERAGE = 1.5`
- `ELIGIBILITY_MAX_DEBT_TO_EBITDA = 6.0`

### O que mudou vs. proposta original

| Proposta original | Decisao final | Razao |
|-------------------|---------------|-------|
| `check_base_eligibility(refiner_result)` | `check_base_eligibility(passed_core_screening, has_valid_financials, interest_coverage, debt_to_ebitda)` | Refiner limitado a top 30 |
| safety_score >= threshold | interest_coverage >= 1.5 | Dado disponivel para todos |
| operating_consistency_score >= threshold | REMOVIDO da eligibility | Nao e gate de investibilidade |
| earnings_quality_score >= threshold | REMOVIDO da eligibility | Nao e gate de investibilidade |
| capital_discipline_score nao aparecia | Confirmado fora | Correto |
| baseCoreScore nao aparecia | Adicionado como `coreRankPercentile` (informativo, nao gate) | Util para thesis score |
| Sem failed_reasons | `BaseEligibility.failed_reasons: list[str]` | Auditabilidade: saber POR QUE foi rejeitado |

### Respostas diretas

**Q1: O universo do Plano 2 e o universo inteiro, o top N, ou o top 30 refinado?**
R: Todos os ativos que passam no core screening (~80-150 empresas). Nao top 30.

**Q2: "Aprovada no core" significa exatamente o que?**
R: Passou nos 4 filtros do magic_formula_brazil + interest_coverage >= 1.5 + debt_to_ebitda <= 6.0.

**Q3: Uma empresa fora do top 30 pode entrar no Thesis Rank?**
R: Sim. O Thesis Rank e independente do refiner.

**Q4: O Plano 2 e um re-ranking do top 30 ou um ranking separado de um universo maior?**
R: Ranking separado do universo completo que passou no core screening.

**Q15: Por que capital_discipline_score ficou fora?**
R: Porque a elegibilidade nao depende do refiner. Usa computed_metrics diretos.

**Q16: Por que baseCoreScore nao entra na elegibilidade?**
R: baseCoreScore (posicao no ranking core) nao e gate de investibilidade. Uma empresa rank #80 no core pode ser A_DIRECT na tese. baseCoreScore entra no thesis_rank_score (peso 0.15), nao na elegibilidade.

**Q17: Threshold absoluto e melhor que percentil/rank relativo?**
R: Sim, para elegibilidade. interest_coverage >= 1.5 tem significado economico absoluto ("empresa cobre seus juros"). Percentil mudaria com o universo e nao tem semantica fixa.

**Q18: Quais thresholds exatos e por que?**
R: interest_coverage >= 1.5 (padrao minimo de cobertura de juros, usado pelo refiner como threshold de safety flag). debt_to_ebitda <= 6.0 (acima disso, empresa esta em zona de estresse — refiner usa 5.0 como threshold de red flag, 6.0 da margem).

**Q19: Qual o comportamento se uma empresa for muito barata mas com operating consistency limitrofe?**
R: Entra no Plan 2 normalmente. Operating consistency nao e gate de elegibilidade. Se o refiner rodar nessa empresa (porque esta no top 30), os scores de quality aparecem como informacao adicional, mas nao bloqueiam.

---

## coreRankPercentile

Embora o core rank nao seja gate, ele e input para o thesis_rank_score:

```
coreRankPercentile = 1 - (core_combined_rank / total_ranked)
baseCoreScore = coreRankPercentile * 100  // 0-100
```

Exemplo: empresa rank #20 de 100 = percentil 80 = baseCoreScore 80.

Isso permite que o thesis_rank_score (peso 0.15 no baseCoreScore) ainda valorize empresas bem posicionadas no core, sem usa-lo como gate.
