"""Quality evaluation framework for council agents.

Evaluates agent output quality across multiple dimensions:
- Consistency: does the agent follow its declared philosophy?
- Groundedness: are factual claims backed by packet data?
- Completeness: are all required output fields present?
- Contradiction: do reasons_for and reasons_against conflict?
- Framework adherence: does the agent apply its school's criteria?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

REQUIRED_OPINION_FIELDS = [
    "agentId",
    "verdict",
    "confidence",
    "thesis",
    "reasonsFor",
    "reasonsAgainst",
    "keyMetricsUsed",
    "hardRejectsTriggered",
    "unknowns",
    "whatWouldChangeMyMind",
]

# Known metrics that agents can reference
VALID_METRICS = {
    "earnings_yield", "roic", "roe", "gross_margin", "ebit_margin",
    "net_margin", "debt_to_ebitda", "cash_conversion", "net_debt",
    "enterprise_value", "ebitda", "revenue", "net_income", "ebit",
    "cash_from_operations", "cash_from_investing", "cash_from_financing",
    "current_ratio", "equity_ratio",
    # Refiner scores
    "earnings_quality_score", "safety_score",
    "operating_consistency_score", "capital_discipline_score",
    "refinement_score",
}

BANNED_PHRASES = [
    "compre agora",
    "venda imediatamente",
    "garante lucro",
    "retorno garantido",
    "sem risco",
    "oportunidade unica",
    "buy now",
    "guaranteed return",
    "risk-free",
]


@dataclass
class QualityScore:
    """Quality evaluation result for an agent opinion."""
    completeness: float  # 0-1
    groundedness: float  # 0-1
    consistency: float   # 0-1
    contradiction_free: float  # 0-1
    regulatory_compliance: float  # 0-1
    overall: float       # weighted average
    issues: list[str]


def evaluate_opinion(opinion: dict, packet_metrics: set[str] | None = None) -> QualityScore:
    """Evaluate quality of an agent opinion."""
    issues: list[str] = []

    # 1. Completeness
    present = sum(1 for f in REQUIRED_OPINION_FIELDS if opinion.get(f) is not None)
    completeness = present / len(REQUIRED_OPINION_FIELDS)
    if completeness < 1.0:
        missing = [f for f in REQUIRED_OPINION_FIELDS if opinion.get(f) is None]
        issues.append(f"Missing fields: {', '.join(missing)}")

    # 2. Groundedness — keyMetricsUsed should reference known metrics
    key_metrics = opinion.get("keyMetricsUsed", [])
    if key_metrics and packet_metrics is not None:
        valid_refs = sum(1 for m in key_metrics if m in packet_metrics)
        groundedness = valid_refs / len(key_metrics) if key_metrics else 1.0
        invalid = [m for m in key_metrics if m not in packet_metrics]
        if invalid:
            issues.append(f"Metrics not in packet: {', '.join(invalid)}")
    elif key_metrics:
        known_refs = sum(1 for m in key_metrics if m in VALID_METRICS)
        groundedness = known_refs / len(key_metrics) if key_metrics else 1.0
    else:
        groundedness = 0.5  # No metrics referenced
        issues.append("No key metrics referenced")

    # 3. Consistency — thesis should be non-empty and align with verdict
    thesis = opinion.get("thesis", "")
    verdict = opinion.get("verdict", "")
    if len(thesis) < 20:
        consistency = 0.5
        issues.append("Thesis too short (< 20 chars)")
    else:
        consistency = 1.0

    if verdict == "avoid" and not opinion.get("reasonsAgainst"):
        consistency *= 0.5
        issues.append("Verdict is 'avoid' but no reasonsAgainst provided")

    if verdict == "buy" and not opinion.get("reasonsFor"):
        consistency *= 0.5
        issues.append("Verdict is 'buy' but no reasonsFor provided")

    # 4. Contradiction check
    reasons_for = set(opinion.get("reasonsFor", []))
    reasons_against = set(opinion.get("reasonsAgainst", []))
    overlap = reasons_for & reasons_against
    if overlap:
        contradiction_free = 0.0
        issues.append(f"Contradicting reasons: {overlap}")
    else:
        contradiction_free = 1.0

    # 5. Regulatory compliance — no banned phrases
    full_text = " ".join(str(v) for v in opinion.values() if isinstance(v, str))
    full_text_lower = full_text.lower()
    found_banned = [p for p in BANNED_PHRASES if p in full_text_lower]
    if found_banned:
        regulatory = 0.0
        issues.append(f"Banned phrases found: {', '.join(found_banned)}")
    else:
        regulatory = 1.0

    # Weighted overall
    overall = (
        0.20 * completeness
        + 0.25 * groundedness
        + 0.20 * consistency
        + 0.15 * contradiction_free
        + 0.20 * regulatory
    )

    return QualityScore(
        completeness=completeness,
        groundedness=groundedness,
        consistency=consistency,
        contradiction_free=contradiction_free,
        regulatory_compliance=regulatory,
        overall=overall,
        issues=issues,
    )


def evaluate_council_result(result: dict) -> dict:
    """Evaluate quality of an entire council result (all opinions)."""
    opinions = result.get("opinions", [])
    if not opinions:
        return {"overall": 0.0, "issues": ["No opinions in council result"]}

    scores = [evaluate_opinion(op) for op in opinions]
    avg_overall = sum(s.overall for s in scores) / len(scores)
    all_issues = []
    for i, s in enumerate(scores):
        agent = opinions[i].get("agentId", f"agent_{i}")
        for issue in s.issues:
            all_issues.append(f"[{agent}] {issue}")

    # Check disclaimer presence
    if not result.get("disclaimer"):
        all_issues.append("Missing disclaimer")
        avg_overall *= 0.8

    return {
        "overall": avg_overall,
        "per_agent": {
            opinions[i].get("agentId", f"agent_{i}"): {
                "completeness": s.completeness,
                "groundedness": s.groundedness,
                "consistency": s.consistency,
                "contradiction_free": s.contradiction_free,
                "regulatory_compliance": s.regulatory_compliance,
                "overall": s.overall,
            }
            for i, s in enumerate(scores)
        },
        "issues": all_issues,
    }
