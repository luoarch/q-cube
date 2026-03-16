"""Rubric Suggester — AI-assisted USD fragility dimension scoring.

Suggests scores for fragility dimensions (usdDebtExposure, usdImportDependence)
based on available financial data and sector context. Suggestions are AI_ASSISTED
with LOW/MEDIUM confidence and require human review before activation.

Guard rails:
- Never assigns confidence HIGH
- Never overwrites existing RUBRIC_MANUAL scores
- Always includes evidence_ref and rationale
- Persists model_version and prompt_version for audit
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
    AIModule,
    AIResearchNote,
    AISuggestion,
    ConfidenceLevel,
    NoteType,
)
from q3_ai_assistant.prompts import rubric as rubric_prompts
from q3_ai_assistant.security.output_sanitizer import sanitize_llm_output

logger = logging.getLogger(__name__)

OUTPUT_SCHEMA_VERSION = "rubric-v1"

SUPPORTED_DIMENSIONS = {"usd_debt_exposure", "usd_import_dependence", "usd_revenue_offset"}


def compute_input_hash(issuer_data: dict) -> str:
    """SHA256 hash of canonical input for deduplication."""
    canonical = json.dumps(issuer_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _clamp_confidence(confidence_str: str) -> ConfidenceLevel:
    """AI_ASSISTED is capped at MEDIUM — never HIGH."""
    if confidence_str == "medium":
        return ConfidenceLevel.medium
    return ConfidenceLevel.low


def _validate_score(score: object) -> int:
    """Validate and clamp score to 0-100 range."""
    try:
        s = int(score)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 30  # conservative default
    return max(0, min(100, s))


def suggest_dimension(
    session: Session,
    adapter: LLMAdapter,
    cache: LLMCache | None,
    *,
    dimension_key: str,
    tenant_id: uuid.UUID,
    issuer_id: uuid.UUID,
    issuer_data: dict,
) -> AISuggestion:
    """Generate an AI suggestion for a fragility dimension score.

    Args:
        session: SQLAlchemy session.
        adapter: LLM adapter (cascade-resolved).
        cache: Optional LLM cache.
        dimension_key: Which dimension to score (e.g. "usd_debt_exposure").
        tenant_id: Tenant scope.
        issuer_id: The issuer being scored.
        issuer_data: Dict with ticker, company_name, sector, financials, computed_metrics.

    Returns:
        Persisted AISuggestion with structured_output containing the suggestion.
    """
    if dimension_key not in SUPPORTED_DIMENSIONS:
        raise ValueError(f"Unsupported dimension: {dimension_key}")

    input_hash = compute_input_hash(issuer_data)

    system_prompt = rubric_prompts.get_system_prompt(dimension_key)
    user_prompt = rubric_prompts.build_user_prompt(issuer_data, dimension_key)

    if cache:
        llm_response, cache_hit = cache.get_or_generate(adapter, system_prompt, user_prompt)
    else:
        llm_response = adapter.generate(system_prompt, user_prompt)
        cache_hit = False

    logger.info(
        "llm_request",
        extra={
            "module": "rubric_suggester",
            "dimension": dimension_key,
            "model": llm_response.model,
            "prompt_tokens": llm_response.prompt_tokens,
            "completion_tokens": llm_response.completion_tokens,
            "latency_ms": llm_response.latency_ms,
            "cost_usd": llm_response.cost_usd,
            "cache_hit": cache_hit,
            "issuer_id": str(issuer_id),
            "ticker": issuer_data.get("ticker", ""),
        },
    )

    parsed = sanitize_llm_output(llm_response.text)

    # Extract and validate fields from LLM output
    score = _validate_score(parsed.get("score", 30) if parsed else 30)
    confidence_str = (parsed.get("confidence", "low") if parsed else "low")
    confidence = _clamp_confidence(confidence_str)
    rationale = (parsed.get("rationale", "") if parsed else "") or "No rationale provided"
    evidence_ref = (parsed.get("evidence_ref", "") if parsed else "") or "sector heuristic"
    key_signals = parsed.get("key_signals", []) if parsed else []
    uncertainty_factors = parsed.get("uncertainty_factors", []) if parsed else []

    structured_output = {
        "dimension_key": dimension_key,
        "issuer_id": str(issuer_id),
        "ticker": issuer_data.get("ticker", ""),
        "suggested_score": score,
        "confidence": confidence.value,
        "rationale": rationale,
        "evidence_ref": evidence_ref,
        "key_signals": key_signals,
        "uncertainty_factors": uncertainty_factors,
        "source_type": "AI_ASSISTED",
        "prompt_version": rubric_prompts.PROMPT_VERSION,
    }

    suggestion = AISuggestion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        module=AIModule.rubric_suggester,
        trigger_event="rubric_suggestion_requested",
        trigger_entity_id=issuer_id,
        input_hash=input_hash,
        prompt_version=rubric_prompts.PROMPT_VERSION,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        input_snapshot=issuer_data,
        output_text=llm_response.text,
        structured_output=structured_output,
        confidence=confidence,
        model_used=llm_response.model,
        model_version=llm_response.model_version,
        tokens_used=llm_response.tokens_used,
        prompt_tokens=llm_response.prompt_tokens,
        completion_tokens=llm_response.completion_tokens,
        cost_usd=llm_response.cost_usd,
    )
    session.add(suggestion)

    # Persist rationale as research note
    if rationale:
        session.add(AIResearchNote(
            id=uuid.uuid4(),
            suggestion_id=suggestion.id,
            note_type=NoteType.recommendation,
            content=f"[{dimension_key}] {rationale}",
        ))

    session.flush()
    return suggestion


# Backward-compatible alias for F2.2.1 callers
def suggest_usd_debt_exposure(
    session: Session,
    adapter: LLMAdapter,
    cache: LLMCache | None,
    *,
    tenant_id: uuid.UUID,
    issuer_id: uuid.UUID,
    issuer_data: dict,
) -> AISuggestion:
    """Generate an AI suggestion for usdDebtExposure score."""
    return suggest_dimension(
        session, adapter, cache,
        dimension_key="usd_debt_exposure",
        tenant_id=tenant_id, issuer_id=issuer_id, issuer_data=issuer_data,
    )
