from __future__ import annotations

import hashlib
import json
import logging
import uuid

from sqlalchemy.orm import Session

from q3_ai_assistant.evaluation.evaluator import QualityScore, evaluate_backtest_narrative
from q3_ai_assistant.llm.adapter import LLMAdapter
from q3_ai_assistant.llm.cache import LLMCache
from q3_ai_assistant.models.entities import (
    AIModule,
    AIResearchNote,
    AISuggestion,
    ConfidenceLevel,
    NoteType,
)
from q3_ai_assistant.prompts import backtest as backtest_prompts
from q3_ai_assistant.security.input_guard import validate_backtest_input
from q3_ai_assistant.security.output_sanitizer import sanitize_llm_output

logger = logging.getLogger(__name__)

OUTPUT_SCHEMA_VERSION = "v1"


def detect_concerns(metrics: dict) -> list[dict]:
    """Deterministic pre-LLM concern detection based on metric thresholds."""
    concerns: list[dict] = []

    sharpe = metrics.get("sharpe") or metrics.get("sharpe_ratio")
    if sharpe is not None and sharpe > 2.0:
        concerns.append({
            "type": "overfitting",
            "description": f"Sharpe ratio of {sharpe:.2f} is unusually high (> 2.0), may indicate overfitting",
            "severity": "high",
        })

    max_dd = metrics.get("max_drawdown")
    if max_dd is not None and abs(max_dd) > 0.30:
        concerns.append({
            "type": "drawdown_risk",
            "description": f"Maximum drawdown of {max_dd:.1%} exceeds -30% threshold",
            "severity": "high",
        })

    hit_rate = metrics.get("hit_rate")
    if hit_rate is not None and hit_rate < 0.40:
        concerns.append({
            "type": "low_hit_rate",
            "description": f"Hit rate of {hit_rate:.1%} is below 40% threshold",
            "severity": "medium",
        })

    turnover = metrics.get("turnover") or metrics.get("annual_turnover")
    if turnover is not None and turnover > 2.0:
        concerns.append({
            "type": "cost_sensitivity",
            "description": f"Annual turnover of {turnover:.0%} exceeds 200%, strategy is cost-sensitive",
            "severity": "medium",
        })

    cagr = metrics.get("cagr")
    if cagr is not None and cagr > 0.50:
        concerns.append({
            "type": "data_quality",
            "description": f"CAGR of {cagr:.1%} exceeds 50%, verify data quality and survivorship bias",
            "severity": "high",
        })

    return concerns


def compute_input_hash(metrics: dict, config: dict) -> str:
    canonical = json.dumps({"metrics": metrics, "config": config}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def narrate_backtest(
    session: Session,
    adapter: LLMAdapter,
    cache: LLMCache | None,
    *,
    tenant_id: uuid.UUID,
    backtest_run_id: uuid.UUID,
    metrics: dict,
    config: dict,
) -> AISuggestion:
    safe_metrics, safe_config = validate_backtest_input(metrics, config)
    concerns = detect_concerns(safe_metrics)
    input_hash = compute_input_hash(safe_metrics, safe_config)

    system_prompt = backtest_prompts.SYSTEM_PROMPT
    user_prompt = backtest_prompts.build_user_prompt(safe_metrics, safe_config, concerns)

    if cache:
        llm_response, cache_hit = cache.get_or_generate(adapter, system_prompt, user_prompt)
    else:
        llm_response = adapter.generate(system_prompt, user_prompt)
        cache_hit = False

    logger.info(
        "llm_request",
        extra={
            "module": "backtest_narrator",
            "model": llm_response.model,
            "prompt_tokens": llm_response.prompt_tokens,
            "completion_tokens": llm_response.completion_tokens,
            "latency_ms": llm_response.latency_ms,
            "cost_usd": llm_response.cost_usd,
            "cache_hit": cache_hit,
            "trigger_entity_id": str(backtest_run_id),
        },
    )

    parsed = sanitize_llm_output(llm_response.text)

    input_snapshot = {"metrics": safe_metrics, "config": safe_config, "concerns": concerns}

    quality = _evaluate(input_snapshot, parsed)
    confidence = _determine_confidence(parsed, quality)

    suggestion = AISuggestion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        module=AIModule.backtest_narrator,
        trigger_event="backtest_run_completed",
        trigger_entity_id=backtest_run_id,
        input_hash=input_hash,
        prompt_version=backtest_prompts.PROMPT_VERSION,
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
        _persist_research_notes(session, suggestion, parsed, concerns)

    session.flush()
    return suggestion


def _evaluate(input_snapshot: dict, parsed: dict | None) -> QualityScore:
    if not parsed:
        return QualityScore(completeness=0.0, parseable=False, coherence=0.0, groundedness=0.0, overall=0.0)
    return evaluate_backtest_narrative(input_snapshot, parsed)


def _determine_confidence(parsed: dict | None, quality: QualityScore) -> ConfidenceLevel:
    if not parsed:
        return ConfidenceLevel.low
    if quality.overall >= 0.7:
        return ConfidenceLevel.high
    if quality.overall >= 0.4:
        return ConfidenceLevel.medium
    return ConfidenceLevel.low


def _persist_research_notes(
    session: Session,
    suggestion: AISuggestion,
    parsed: dict,
    concerns: list[dict],
) -> None:
    narrative = parsed.get("narrative", "")
    if narrative:
        session.add(AIResearchNote(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            note_type=NoteType.summary,
            content=narrative,
        ))

    for highlight in parsed.get("highlights", []):
        interp = highlight.get("interpretation", "")
        metric = highlight.get("metric", "")
        if interp:
            session.add(AIResearchNote(
                id=uuid.uuid4(),
                suggestion_id=suggestion.id,
                note_type=NoteType.highlight,
                content=f"{metric}: {interp}",
            ))

    for concern in concerns:
        session.add(AIResearchNote(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            note_type=NoteType.concern,
            content=f"[{concern['severity'].upper()}] {concern['description']}",
        ))
