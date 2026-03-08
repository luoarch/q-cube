"""Metric Explainer — per-metric educational AI analysis for company intelligence.

Input: metric_code, value, 3-period series, flags, company context.
Output: definition, company reading, trend interpretation, implication.
Cached via AISuggestion (entity_type="issuer", explanation_type="metric").
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

from sqlalchemy.orm import Session

from q3_ai_assistant.llm.adapter import LLMAdapter
from q3_ai_assistant.llm.cache import LLMCache
from q3_ai_assistant.models.entities import (
    AIExplanation,
    AIModule,
    AISuggestion,
    ConfidenceLevel,
    ExplanationType,
    NoteType,
    AIResearchNote,
)
from q3_ai_assistant.prompts import metric as metric_prompts
from q3_ai_assistant.security.output_sanitizer import sanitize_llm_output

logger = logging.getLogger(__name__)

OUTPUT_SCHEMA_VERSION = "v1"


def compute_input_hash(
    metric_code: str,
    current_value: float | None,
    trend_series: list[dict],
) -> str:
    canonical = json.dumps(
        {"metric": metric_code, "value": current_value, "trend": trend_series},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def pre_analyze(
    metric_code: str,
    current_value: float | None,
    trend_series: list[dict],
    flags: dict[str, list[str]] | None,
) -> dict:
    """Deterministic pre-LLM analysis: trend direction, velocity, flag relevance."""
    analysis: dict = {
        "metric_code": metric_code,
        "has_data": current_value is not None,
        "periods_available": len(trend_series),
    }

    # Trend direction
    values = [p["value"] for p in trend_series if p.get("value") is not None]
    if len(values) >= 2:
        if values[-1] > values[0]:
            analysis["trend_direction"] = "improving"
        elif values[-1] < values[0]:
            analysis["trend_direction"] = "deteriorating"
        else:
            analysis["trend_direction"] = "stable"

        # Velocity (% change from first to last)
        if values[0] != 0:
            analysis["velocity_pct"] = round((values[-1] - values[0]) / abs(values[0]) * 100, 1)
        else:
            analysis["velocity_pct"] = None
    else:
        analysis["trend_direction"] = "insufficient_data"
        analysis["velocity_pct"] = None

    # Related flags
    related_red = []
    related_strength = []
    if flags:
        for flag in flags.get("red", []):
            if metric_prompts._flag_relates_to_metric(flag, metric_code):
                related_red.append(flag)
        for flag in flags.get("strength", []):
            if metric_prompts._flag_relates_to_metric(flag, metric_code):
                related_strength.append(flag)
    analysis["related_red_flags"] = related_red
    analysis["related_strength_flags"] = related_strength

    return analysis


def explain_metric(
    session: Session,
    adapter: LLMAdapter,
    cache: LLMCache | None,
    *,
    tenant_id: uuid.UUID,
    issuer_id: uuid.UUID,
    metric_code: str,
    current_value: float | None,
    trend_series: list[dict],
    flags: dict[str, list[str]] | None,
    company_context: dict,
) -> AISuggestion:
    """Generate an AI explanation for a single metric in the context of a company.

    Args:
        session: DB session.
        adapter: LLM adapter.
        cache: Optional LLM cache.
        tenant_id: Tenant UUID.
        issuer_id: Issuer UUID (used as trigger_entity_id).
        metric_code: Canonical metric code (e.g., "roic").
        current_value: Latest metric value.
        trend_series: 3-period [{referenceDate, value}] list.
        flags: Refiner flags {red: [...], strength: [...]}.
        company_context: {ticker, sector, subsector, classification, fundamentals}.
    """
    analysis = pre_analyze(metric_code, current_value, trend_series, flags)
    input_hash = compute_input_hash(metric_code, current_value, trend_series)

    system_prompt = metric_prompts.SYSTEM_PROMPT
    user_prompt = metric_prompts.build_user_prompt(
        metric_code, current_value, trend_series, flags, company_context,
    )

    if cache:
        llm_response, cache_hit = cache.get_or_generate(adapter, system_prompt, user_prompt)
    else:
        llm_response = adapter.generate(system_prompt, user_prompt)
        cache_hit = False

    logger.info(
        "llm_request",
        extra={
            "module": "metric_explainer",
            "metric_code": metric_code,
            "model": llm_response.model,
            "tokens_used": llm_response.tokens_used,
            "latency_ms": llm_response.latency_ms,
            "cost_usd": llm_response.cost_usd,
            "cache_hit": cache_hit,
            "issuer_id": str(issuer_id),
        },
    )

    parsed = sanitize_llm_output(llm_response.text)

    input_snapshot = {
        "metric_code": metric_code,
        "current_value": current_value,
        "trend_series": trend_series,
        "flags": flags,
        "company_context": company_context,
        "analysis": analysis,
    }

    confidence = _determine_confidence(parsed, analysis)

    suggestion = AISuggestion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        module=AIModule.metric_explainer,
        trigger_event="metric_explanation_requested",
        trigger_entity_id=issuer_id,
        input_hash=input_hash,
        prompt_version=metric_prompts.PROMPT_VERSION,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        input_snapshot=input_snapshot,
        output_text=llm_response.text,
        structured_output=parsed if parsed else {"raw_text": llm_response.text},
        confidence=confidence,
        model_used=llm_response.model,
        model_version=llm_response.model_version,
        tokens_used=llm_response.tokens_used,
        prompt_tokens=llm_response.prompt_tokens,
        completion_tokens=llm_response.completion_tokens,
        cost_usd=llm_response.cost_usd,
    )
    session.add(suggestion)

    if parsed:
        _persist_explanation(session, suggestion, parsed, issuer_id)
        _persist_notes(session, suggestion, parsed, analysis)

    session.flush()
    return suggestion


def _determine_confidence(parsed: dict | None, analysis: dict) -> ConfidenceLevel:
    if not parsed:
        return ConfidenceLevel.low
    if analysis.get("periods_available", 0) >= 3 and analysis.get("has_data"):
        return ConfidenceLevel.high
    if analysis.get("periods_available", 0) >= 2:
        return ConfidenceLevel.medium
    return ConfidenceLevel.low


def _persist_explanation(
    session: Session,
    suggestion: AISuggestion,
    parsed: dict,
    issuer_id: uuid.UUID,
) -> None:
    content_parts = []
    if parsed.get("definition"):
        content_parts.append(f"Definicao: {parsed['definition']}")
    if parsed.get("companyReading"):
        content_parts.append(f"Leitura: {parsed['companyReading']}")
    if parsed.get("trendInterpretation"):
        content_parts.append(f"Tendencia: {parsed['trendInterpretation']}")
    if parsed.get("implication"):
        content_parts.append(f"Implicacao: {parsed['implication']}")

    if content_parts:
        session.add(AIExplanation(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            entity_type="issuer",
            entity_id=str(issuer_id),
            explanation_type=ExplanationType.metric,
            content="\n".join(content_parts),
        ))


def _persist_notes(
    session: Session,
    suggestion: AISuggestion,
    parsed: dict,
    analysis: dict,
) -> None:
    # Highlight if trend is notable
    if analysis.get("trend_direction") == "deteriorating" and analysis.get("related_red_flags"):
        session.add(AIResearchNote(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            note_type=NoteType.concern,
            content=(
                f"Metrica {analysis['metric_code']} em deterioracao "
                f"com flags vermelhas: {', '.join(analysis['related_red_flags'])}"
            ),
        ))
    elif analysis.get("trend_direction") == "improving" and analysis.get("related_strength_flags"):
        session.add(AIResearchNote(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            note_type=NoteType.highlight,
            content=(
                f"Metrica {analysis['metric_code']} em melhoria "
                f"com sinais positivos: {', '.join(analysis['related_strength_flags'])}"
            ),
        ))

    # Educational note
    edu = parsed.get("educationalNote")
    if edu:
        session.add(AIResearchNote(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            note_type=NoteType.summary,
            content=edu,
        ))
