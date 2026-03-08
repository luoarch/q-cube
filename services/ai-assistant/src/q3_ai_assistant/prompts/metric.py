"""Metric explainer prompts — per-metric educational analysis."""

from __future__ import annotations

import json

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """\
You are a financial analyst assistant for the Q3 platform.
Your job is to explain financial metrics in the context of a specific company.
You are educational, not advisory — never recommend buy or sell.

Given: a metric code, its current value, a 3-period time series, refiner flags,
and company context (sector, classification, other fundamentals).

Output MUST be valid JSON with this exact schema:
{
  "metricCode": "the metric being explained",
  "definition": "1-2 sentence definition of this metric",
  "companyReading": "what this value means for THIS specific company",
  "trendInterpretation": "analysis of the 3-period trend (improving/stable/deteriorating)",
  "implication": "what this trend implies for the company's fundamentals",
  "relatedFlags": ["any relevant red/strength flags"],
  "educationalNote": "brief educational context (e.g., sector benchmarks, what investors look for)"
}

Rules:
- Reference only data provided in the input
- Be factual and concise (each field: 1-3 sentences max)
- Adjust interpretation for company classification (banks vs non-financial)
- Do not recommend trades or investments
- Do not include HTML tags
- Use pt-BR language for all text fields
"""

# Metric definitions for deterministic pre-analysis
METRIC_DEFINITIONS: dict[str, str] = {
    "roic": "Retorno sobre capital investido — mede a eficiencia do capital empregado",
    "roe": "Retorno sobre patrimonio liquido — mede o lucro gerado sobre o capital dos acionistas",
    "earnings_yield": "Rendimento dos lucros (inverso do P/L) — mede o retorno implicito do preco",
    "gross_margin": "Margem bruta — percentual da receita retido apos custos diretos",
    "ebit_margin": "Margem EBIT — lucratividade operacional antes de juros e impostos",
    "net_margin": "Margem liquida — percentual da receita que se converte em lucro liquido",
    "cash_conversion": "Conversao de caixa — quanto do lucro se converte em caixa operacional",
    "debt_to_ebitda": "Divida/EBITDA — nivel de alavancagem em relacao a geracao de caixa",
    "ebitda": "EBITDA — geracao de caixa operacional antes de investimentos e financiamentos",
    "enterprise_value": "Valor da firma — valor de mercado + divida liquida",
    "net_debt": "Divida liquida — divida bruta menos caixa e equivalentes",
}


def build_user_prompt(
    metric_code: str,
    current_value: float | None,
    trend_series: list[dict],
    flags: dict[str, list[str]] | None,
    company_context: dict,
) -> str:
    """Build user prompt for a single metric explanation.

    Args:
        metric_code: Canonical metric code (e.g., "roic").
        current_value: Latest value (may be None).
        trend_series: List of {referenceDate, value} dicts (up to 3 periods).
        flags: {red: [...], strength: [...]} or None.
        company_context: {ticker, sector, subsector, classification, fundamentals}.
    """
    definition = METRIC_DEFINITIONS.get(metric_code, "Metrica financeira")

    parts = [
        f"## Metrica: {metric_code}",
        f"Definicao base: {definition}",
        f"\n## Valor atual: {current_value}",
        f"\n## Serie historica (3 periodos):",
        json.dumps(trend_series, indent=2),
    ]

    if flags:
        related_flags = []
        for flag in flags.get("red", []):
            if metric_code in flag.lower() or _flag_relates_to_metric(flag, metric_code):
                related_flags.append(f"[RED] {flag}")
        for flag in flags.get("strength", []):
            if metric_code in flag.lower() or _flag_relates_to_metric(flag, metric_code):
                related_flags.append(f"[STRENGTH] {flag}")
        if related_flags:
            parts.append(f"\n## Flags relacionadas:\n{json.dumps(related_flags)}")

    parts.append(f"\n## Contexto da empresa:\n{json.dumps(company_context, indent=2, default=str)}")
    parts.append("\nRetorne APENAS o JSON estruturado, sem texto adicional.")

    return "\n".join(parts)


# Map flags to related metrics
_FLAG_METRIC_MAP: dict[str, list[str]] = {
    "earnings_cfo_divergence": ["cash_conversion", "net_margin"],
    "ebit_deterioration": ["ebit_margin", "roic"],
    "margin_compression": ["gross_margin", "ebit_margin", "net_margin"],
    "leverage_rising": ["debt_to_ebitda", "net_debt"],
    "debt_ebitda_worsening": ["debt_to_ebitda"],
    "weak_interest_coverage": ["ebit_margin"],
    "ebit_growing": ["ebit_margin", "roic"],
    "margin_resilient": ["gross_margin", "ebit_margin", "net_margin"],
    "deleveraging": ["debt_to_ebitda", "net_debt"],
    "strong_cash_conversion": ["cash_conversion"],
}


def _flag_relates_to_metric(flag: str, metric_code: str) -> bool:
    related_metrics = _FLAG_METRIC_MAP.get(flag, [])
    return metric_code in related_metrics
