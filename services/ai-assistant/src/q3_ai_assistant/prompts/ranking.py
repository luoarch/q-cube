from __future__ import annotations

import json

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """\
You are a quantitative investment analyst assistant for the Q3 platform.
You explain Magic Formula strategy rankings to human analysts.
Never recommend trades. All output is AI-generated and requires human review.

Your task: given a ranked list of assets with pre-computed analysis, produce a JSON explanation.

Output MUST be valid JSON with this exact schema:
{
  "summary": "2-4 sentence overview of the ranking",
  "sector_analysis": "analysis of sector distribution and concentration",
  "outlier_notes": ["note about any statistical outliers"],
  "position_explanations": [{"ticker": "XXXX3", "explanation": "why this asset ranks here"}]
}

Rules:
- Reference only tickers and data provided in the input
- Be factual and concise
- Highlight concentration risks if any sector > 30% of positions
- Note statistical outliers (earnings yield or ROC > 2 standard deviations from mean)
- Do not invent data or metrics not present in the input
- Do not include HTML tags in output
"""


def build_user_prompt(
    ranked_assets: list[dict],
    analysis: dict,
) -> str:
    parts: list[str] = []

    parts.append("## Ranked Assets (top positions)")
    parts.append(json.dumps(ranked_assets[:30], indent=2))

    if analysis.get("sector_distribution"):
        parts.append("\n## Sector Distribution")
        parts.append(json.dumps(analysis["sector_distribution"], indent=2))

    if analysis.get("concentration_alerts"):
        parts.append("\n## Concentration Alerts")
        for alert in analysis["concentration_alerts"]:
            parts.append(f"- {alert}")

    if analysis.get("outliers"):
        parts.append("\n## Statistical Outliers")
        parts.append(json.dumps(analysis["outliers"], indent=2))

    if analysis.get("top5"):
        parts.append("\n## Top 5 by Rank")
        parts.append(json.dumps(analysis["top5"], indent=2))

    if analysis.get("bottom5"):
        parts.append("\n## Bottom 5 by Rank")
        parts.append(json.dumps(analysis["bottom5"], indent=2))

    parts.append("\nProduce the JSON explanation now.")
    return "\n".join(parts)
