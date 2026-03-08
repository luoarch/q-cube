from __future__ import annotations

import hashlib
import json
import logging
import uuid
from statistics import mean, stdev

from sqlalchemy.orm import Session

from q3_ai_assistant.evaluation.evaluator import QualityScore, evaluate_ranking_explanation
from q3_ai_assistant.llm.adapter import LLMAdapter, LLMResponse
from q3_ai_assistant.llm.cache import LLMCache
from q3_ai_assistant.models.entities import (
    AIExplanation,
    AIModule,
    AIResearchNote,
    AISuggestion,
    ConfidenceLevel,
    ExplanationType,
    NoteType,
)
from q3_ai_assistant.prompts import ranking as ranking_prompts
from q3_ai_assistant.security.input_guard import validate_ranking_input
from q3_ai_assistant.security.output_sanitizer import sanitize_llm_output

logger = logging.getLogger(__name__)

OUTPUT_SCHEMA_VERSION = "v1"
CONCENTRATION_THRESHOLD = 0.30


def pre_analyze(ranked_assets: list[dict]) -> dict:
    """Deterministic pre-LLM analysis: sector distribution, outliers, top/bottom."""
    analysis: dict = {}

    sector_counts: dict[str, int] = {}
    for asset in ranked_assets:
        sector = asset.get("sector") or "Unknown"
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    total = len(ranked_assets) or 1
    analysis["sector_distribution"] = {
        s: {"count": c, "pct": round(c / total, 3)} for s, c in sorted(sector_counts.items())
    }

    analysis["concentration_alerts"] = [
        f"{sector}: {info['pct']:.0%} of positions ({info['count']}/{total})"
        for sector, info in analysis["sector_distribution"].items()
        if info["pct"] > CONCENTRATION_THRESHOLD
    ]

    ey_values = [a["earningsYield"] for a in ranked_assets if a.get("earningsYield")]
    roc_values = [a["returnOnCapital"] for a in ranked_assets if a.get("returnOnCapital")]

    outliers: list[dict] = []
    if len(ey_values) >= 3:
        ey_mean, ey_std = mean(ey_values), stdev(ey_values)
        for a in ranked_assets:
            ey = a.get("earningsYield", 0)
            if ey_std > 0 and abs(ey - ey_mean) > 2 * ey_std:
                outliers.append({"ticker": a["ticker"], "metric": "earningsYield", "value": ey, "z_score": round((ey - ey_mean) / ey_std, 2)})

    if len(roc_values) >= 3:
        roc_mean, roc_std = mean(roc_values), stdev(roc_values)
        for a in ranked_assets:
            roc = a.get("returnOnCapital", 0)
            if roc_std > 0 and abs(roc - roc_mean) > 2 * roc_std:
                outliers.append({"ticker": a["ticker"], "metric": "returnOnCapital", "value": roc, "z_score": round((roc - roc_mean) / roc_std, 2)})

    analysis["outliers"] = outliers

    sorted_assets = sorted(ranked_assets, key=lambda a: a.get("rank", 0))
    analysis["top5"] = sorted_assets[:5]
    analysis["bottom5"] = sorted_assets[-5:] if len(sorted_assets) > 5 else []

    return analysis


def compute_input_hash(ranked_assets: list[dict]) -> str:
    canonical = json.dumps(ranked_assets, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def explain_ranking(
    session: Session,
    adapter: LLMAdapter,
    cache: LLMCache | None,
    *,
    tenant_id: uuid.UUID,
    strategy_run_id: uuid.UUID,
    ranked_assets: list[dict],
) -> AISuggestion:
    sanitized = validate_ranking_input(ranked_assets)
    analysis = pre_analyze(sanitized)
    input_hash = compute_input_hash(sanitized)

    system_prompt = ranking_prompts.SYSTEM_PROMPT
    user_prompt = ranking_prompts.build_user_prompt(sanitized, analysis)

    if cache:
        llm_response, cache_hit = cache.get_or_generate(adapter, system_prompt, user_prompt)
    else:
        llm_response = adapter.generate(system_prompt, user_prompt)
        cache_hit = False

    logger.info(
        "llm_request",
        extra={
            "module": "ranking_explainer",
            "model": llm_response.model,
            "prompt_tokens": llm_response.prompt_tokens,
            "completion_tokens": llm_response.completion_tokens,
            "latency_ms": llm_response.latency_ms,
            "cost_usd": llm_response.cost_usd,
            "cache_hit": cache_hit,
            "trigger_entity_id": str(strategy_run_id),
        },
    )

    parsed = sanitize_llm_output(llm_response.text)

    input_snapshot = {"ranked_assets": sanitized, "analysis": analysis}

    quality = _evaluate(input_snapshot, parsed)
    confidence = _determine_confidence(parsed, quality)

    suggestion = AISuggestion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        module=AIModule.ranking_explainer,
        trigger_event="strategy_run_completed",
        trigger_entity_id=strategy_run_id,
        input_hash=input_hash,
        prompt_version=ranking_prompts.PROMPT_VERSION,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        input_snapshot=input_snapshot,
        output_text=llm_response.text,
        structured_output={**(parsed or {}), "quality_score": quality.overall} if parsed else {"raw_text": llm_response.text, "quality_score": quality.overall},
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
        _persist_explanations(session, suggestion, parsed)
        _persist_research_notes(session, suggestion, parsed, analysis)

    session.flush()
    return suggestion


def _evaluate(input_snapshot: dict, parsed: dict | None) -> QualityScore:
    if not parsed:
        return QualityScore(completeness=0.0, parseable=False, coherence=0.0, groundedness=0.0, overall=0.0)
    return evaluate_ranking_explanation(input_snapshot, parsed)


def _determine_confidence(parsed: dict | None, quality: QualityScore) -> ConfidenceLevel:
    if not parsed:
        return ConfidenceLevel.low
    if quality.overall >= 0.7:
        return ConfidenceLevel.high
    if quality.overall >= 0.4:
        return ConfidenceLevel.medium
    return ConfidenceLevel.low


def _persist_explanations(session: Session, suggestion: AISuggestion, parsed: dict) -> None:
    for pos in parsed.get("position_explanations", []):
        ticker = pos.get("ticker", "")
        explanation = pos.get("explanation", "")
        if ticker and explanation:
            session.add(AIExplanation(
                id=uuid.uuid4(),
                suggestion_id=suggestion.id,
                entity_type="security",
                entity_id=ticker,
                explanation_type=ExplanationType.position,
                content=explanation,
            ))

    for note in parsed.get("outlier_notes", []):
        if note:
            session.add(AIExplanation(
                id=uuid.uuid4(),
                suggestion_id=suggestion.id,
                entity_type="ranking",
                entity_id=str(suggestion.trigger_entity_id),
                explanation_type=ExplanationType.outlier,
                content=note,
            ))


def _persist_research_notes(session: Session, suggestion: AISuggestion, parsed: dict, analysis: dict) -> None:
    summary = parsed.get("summary", "")
    if summary:
        session.add(AIResearchNote(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            note_type=NoteType.summary,
            content=summary,
        ))

    if analysis.get("concentration_alerts"):
        session.add(AIResearchNote(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            note_type=NoteType.concern,
            content="Sector concentration detected: " + "; ".join(analysis["concentration_alerts"]),
        ))
