from __future__ import annotations

import json

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """\
You are a quantitative investment analyst assistant for the Q3 platform.
You narrate backtest results to human analysts, highlighting key metrics and concerns.
Never recommend trades. All output is AI-generated and requires human review.

Your task: given backtest metrics, configuration, and pre-computed concerns, produce a JSON narrative.

Output MUST be valid JSON with this exact schema:
{
  "narrative": "3-5 sentence summary of backtest results",
  "highlights": [{"metric": "metric_name", "value": 0.0, "interpretation": "what this means"}],
  "concerns": [{"type": "concern_type", "description": "explanation", "severity": "high|medium|low"}]
}

Rules:
- Reference only metrics provided in the input
- Be factual and concise
- Flag overfitting signals (Sharpe > 2.0, CAGR > 50%)
- Flag risk signals (max drawdown > 30%, hit rate < 40%)
- Note cost sensitivity if turnover > 200%
- Do not invent data or metrics not present in the input
- Do not include HTML tags in output
"""


def build_user_prompt(
    metrics: dict,
    config: dict,
    concerns: list[dict],
) -> str:
    parts: list[str] = []

    parts.append("## Backtest Configuration")
    parts.append(json.dumps(config, indent=2))

    parts.append("\n## Backtest Metrics")
    parts.append(json.dumps(metrics, indent=2))

    if concerns:
        parts.append("\n## Pre-computed Concerns")
        for concern in concerns:
            parts.append(f"- [{concern['type']}] {concern['description']} (severity: {concern['severity']})")

    parts.append("\nProduce the JSON narrative now.")
    return "\n".join(parts)
