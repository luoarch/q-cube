"""Quality evaluation framework for council agents.

Evaluates agent output quality across multiple dimensions:
- Completeness: are all required output fields present?
- Groundedness: are factual claims backed by packet data?
- Consistency: does verdict align with reasons?
- Contradiction-free: do reasons_for and reasons_against conflict?
- Regulatory compliance: no banned phrases
- Framework adherence: does the agent cite its school's core metrics?
- Confidence calibration: is confidence sensible for the scenario?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

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
    "current_ratio", "equity_ratio", "equity",
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

# Per-agent core metrics — agents should reference at least some of these
AGENT_CORE_METRICS: dict[str, set[str]] = {
    "barsi": {"earnings_yield", "net_income", "cash_from_operations", "cash_from_investing", "net_margin", "debt_to_ebitda"},
    "graham": {"earnings_yield", "debt_to_ebitda", "net_debt", "gross_margin", "net_margin", "roic"},
    "greenblatt": {"earnings_yield", "roic", "ebit", "ebit_margin", "enterprise_value"},
    "buffett": {"roe", "gross_margin", "ebit_margin", "net_margin", "cash_from_operations", "roic", "cash_conversion"},
}


@dataclass
class QualityScore:
    """Quality evaluation result for an agent opinion."""
    completeness: float  # 0-1
    groundedness: float  # 0-1
    consistency: float   # 0-1
    contradiction_free: float  # 0-1
    regulatory_compliance: float  # 0-1
    framework_adherence: float  # 0-1
    confidence_calibration: float  # 0-1
    overall: float       # weighted average
    issues: list[str] = field(default_factory=list)


@dataclass
class ConfidenceExpectation:
    """Expected confidence range for a benchmark scenario."""
    min_confidence: int
    max_confidence: int
    description: str = ""


def evaluate_opinion(
    opinion: dict,
    packet_metrics: set[str] | None = None,
    confidence_expectation: ConfidenceExpectation | None = None,
) -> QualityScore:
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

    # 4b. Hard reject consistency — if hardRejectsTriggered is non-empty, verdict must be avoid
    hard_rejects = opinion.get("hardRejectsTriggered", [])
    if hard_rejects and verdict != "avoid":
        contradiction_free *= 0.0
        issues.append(
            f"Hard rejects triggered ({hard_rejects}) but verdict is '{verdict}' (should be 'avoid')"
        )

    # 5. Regulatory compliance — no banned phrases
    full_text = " ".join(str(v) for v in opinion.values() if isinstance(v, str))
    full_text_lower = full_text.lower()
    found_banned = [p for p in BANNED_PHRASES if p in full_text_lower]
    if found_banned:
        regulatory = 0.0
        issues.append(f"Banned phrases found: {', '.join(found_banned)}")
    else:
        regulatory = 1.0

    # 6. Framework adherence — agent should reference its core metrics
    agent_id = opinion.get("agentId", "")
    core_metrics = AGENT_CORE_METRICS.get(agent_id, set())
    if core_metrics and key_metrics:
        core_used = sum(1 for m in key_metrics if m in core_metrics)
        framework_adherence = min(1.0, core_used / max(2, len(core_metrics) * 0.4))
        if core_used == 0:
            issues.append(f"Agent '{agent_id}' used no core metrics from its school")
    elif not core_metrics:
        # Moderator or unknown agent — skip
        framework_adherence = 1.0
    else:
        framework_adherence = 0.0
        issues.append(f"Agent '{agent_id}' references no metrics at all")

    # 7. Confidence calibration — if expectation provided, check range
    confidence = opinion.get("confidence", 50)
    if confidence_expectation is not None:
        if confidence_expectation.min_confidence <= confidence <= confidence_expectation.max_confidence:
            confidence_calibration = 1.0
        else:
            # Proportional penalty for distance from expected range
            if confidence < confidence_expectation.min_confidence:
                distance = confidence_expectation.min_confidence - confidence
            else:
                distance = confidence - confidence_expectation.max_confidence
            confidence_calibration = max(0.0, 1.0 - distance / 50)
            issues.append(
                f"Confidence {confidence} outside expected range "
                f"[{confidence_expectation.min_confidence}-{confidence_expectation.max_confidence}]"
                f" ({confidence_expectation.description})"
            )
    else:
        # Basic sanity: insufficient_data should have low confidence
        if verdict == "insufficient_data" and confidence > 30:
            confidence_calibration = 0.5
            issues.append(f"Confidence {confidence} too high for insufficient_data verdict")
        elif verdict == "avoid" and hard_rejects and confidence < 50:
            confidence_calibration = 0.8  # mild issue: hard reject + low confidence is odd
        else:
            confidence_calibration = 1.0

    # Weighted overall
    overall = (
        0.15 * completeness
        + 0.20 * groundedness
        + 0.15 * consistency
        + 0.10 * contradiction_free
        + 0.15 * regulatory
        + 0.15 * framework_adherence
        + 0.10 * confidence_calibration
    )

    return QualityScore(
        completeness=completeness,
        groundedness=groundedness,
        consistency=consistency,
        contradiction_free=contradiction_free,
        regulatory_compliance=regulatory,
        framework_adherence=framework_adherence,
        confidence_calibration=confidence_calibration,
        overall=overall,
        issues=issues,
    )


def evaluate_council_result(result: dict) -> dict:
    """Evaluate quality of an entire council result (all opinions)."""
    opinions = result.get("opinions", [])
    if not opinions:
        return {"overall": 0.0, "issues": ["No opinions in council result"], "per_agent": {}}

    scores = [evaluate_opinion(op) for op in opinions]
    avg_overall = sum(s.overall for s in scores) / len(scores)
    all_issues: list[str] = []
    for i, s in enumerate(scores):
        agent = opinions[i].get("agentId", f"agent_{i}")
        for issue in s.issues:
            all_issues.append(f"[{agent}] {issue}")

    # Check disclaimer presence
    if not result.get("disclaimer"):
        all_issues.append("Missing disclaimer")
        avg_overall *= 0.8

    # Cross-agent factual consistency: all agents should cite similar metric values
    # (structural check — actual value consistency requires the packet)
    metric_citations: dict[str, set[str]] = {}
    for op in opinions:
        for m in op.get("keyMetricsUsed", []):
            metric_citations.setdefault(m, set()).add(op.get("agentId", "unknown"))
    # If a metric is cited by only 1 of 4+ agents, flag it as potentially inconsistent
    if len(opinions) >= 4:
        for metric, agents in metric_citations.items():
            if len(agents) == 1 and metric in VALID_METRICS:
                # Not an issue per se, just informational
                pass

    return {
        "overall": avg_overall,
        "per_agent": {
            opinions[i].get("agentId", f"agent_{i}"): {
                "completeness": s.completeness,
                "groundedness": s.groundedness,
                "consistency": s.consistency,
                "contradiction_free": s.contradiction_free,
                "regulatory_compliance": s.regulatory_compliance,
                "framework_adherence": s.framework_adherence,
                "confidence_calibration": s.confidence_calibration,
                "overall": s.overall,
            }
            for i, s in enumerate(scores)
        },
        "issues": all_issues,
    }


def evaluate_cross_agent_consistency(opinions: list[dict]) -> dict:
    """Check for cross-agent factual contradictions.

    Two agents citing the same metric should not make contradictory factual claims.
    Returns a consistency report with any detected issues.
    """
    issues: list[str] = []

    # All agents should agree on whether there are hard rejects or not
    verdicts = [(op.get("agentId", "?"), op.get("verdict", "?")) for op in opinions]
    hard_reject_agents = [
        op.get("agentId", "?")
        for op in opinions
        if op.get("hardRejectsTriggered")
    ]

    # If any agent triggered a hard reject and gave "avoid",
    # but another agent says "buy" without mentioning the risk, that's a concern
    buy_agents = [aid for aid, v in verdicts if v == "buy"]
    if hard_reject_agents and buy_agents:
        # Check if buy agents acknowledge risks in reasonsAgainst
        for op in opinions:
            if op.get("verdict") == "buy" and not op.get("reasonsAgainst"):
                issues.append(
                    f"{op.get('agentId')} says 'buy' with no reasonsAgainst, "
                    f"while {hard_reject_agents} triggered hard rejects"
                )

    # Verdict diversity check — for strong consensus cases, expect agreement
    unique_verdicts = {v for _, v in verdicts}
    verdict_agreement = 1.0 - (len(unique_verdicts) - 1) / max(len(opinions), 1)

    return {
        "verdict_agreement": verdict_agreement,
        "unique_verdicts": list(unique_verdicts),
        "issues": issues,
    }
