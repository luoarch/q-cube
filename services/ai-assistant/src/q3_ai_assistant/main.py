from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from q3_ai_assistant.config import settings
from q3_ai_assistant.db.session import SessionLocal
from q3_ai_assistant.models.entities import AISuggestion, ReviewStatus
from q3_ai_assistant.observability.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

# Initialize OpenTelemetry tracing
from q3_ai_assistant.observability.tracing import setup_tracing
setup_tracing()

app = FastAPI(title="Q3 AI Assistant", version="0.1.0")

# Instrument FastAPI with OTel
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
except Exception:
    logger.debug("FastAPI OTel instrumentation skipped")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    result: dict = {"service": "ai-assistant", "status": "ok", "enabled": settings.enabled}

    try:
        with SessionLocal() as session:
            total = session.execute(
                select(func.count(AISuggestion.id))
            ).scalar() or 0

            pending = session.execute(
                select(func.count(AISuggestion.id)).where(
                    AISuggestion.review_status == ReviewStatus.pending
                )
            ).scalar() or 0

            result["total_suggestions"] = total
            result["pending_review"] = pending
    except Exception:
        logger.exception("health check DB query failed")
        result["db"] = "error"

    return result


# ---------------------------------------------------------------------------
# Council endpoints (called by NestJS API proxy)
# ---------------------------------------------------------------------------


class CouncilRequest(BaseModel):
    mode: str  # solo | roundtable | debate | comparison
    ticker: str
    tickers: list[str] | None = None  # for comparison mode (2-3 tickers)
    agent_ids: list[str] | None = None
    tenant_id: str
    session_id: str | None = None  # chat session ID for budget tracking
    daily_cost_limit_usd: float | None = None  # per-tenant override


class CouncilResponse(BaseModel):
    session_id: str
    mode: str
    opinions: list[dict]
    scoreboard: dict
    conflict_matrix: list[dict]
    moderator_synthesis: dict
    debate_log: list[dict] | None = None
    comparison_matrix: dict | None = None
    disclaimer: str
    audit_trail: dict


def _build_packet_from_db(ticker: str) -> dict | None:
    """Build a minimal AssetAnalysisPacket from database data."""
    from q3_shared_models.entities import ComputedMetric, Issuer, Security

    with SessionLocal() as session:
        security = session.query(Security).filter_by(ticker=ticker).first()
        if not security:
            return None

        issuer = session.query(Issuer).filter_by(id=security.issuer_id).first()
        if not issuer:
            return None

        # Load latest computed metrics
        metrics = (
            session.query(ComputedMetric)
            .filter_by(issuer_id=issuer.id, period_type="annual")
            .order_by(ComputedMetric.reference_date.desc())
            .limit(30)
            .all()
        )

        fundamentals: dict[str, float | None] = {}
        trends: dict[str, list[dict]] = {}
        for m in metrics:
            code = m.metric_code
            val = float(m.value) if m.value is not None else None
            ref_date = str(m.reference_date)

            if code not in fundamentals:
                fundamentals[code] = val
            trends.setdefault(code, []).append({"reference_date": ref_date, "value": val})

        # Sort trends by date and limit to 3
        for code in trends:
            trends[code] = sorted(trends[code], key=lambda x: x["reference_date"])[-3:]

        return {
            "issuer_id": str(issuer.id),
            "ticker": ticker,
            "sector": issuer.sector or "",
            "subsector": issuer.subsector or "",
            "classification": "non_financial",
            "fundamentals": fundamentals,
            "trends": trends,
            "refiner_scores": None,
            "flags": None,
            "market_cap": None,
            "avg_daily_volume": None,
            "score_reliability": "medium",
        }


def _dict_to_packet(data: dict) -> "AssetAnalysisPacket":
    """Convert a raw dict from _build_packet_from_db to an AssetAnalysisPacket."""
    from q3_ai_assistant.council.packet import AssetAnalysisPacket, PeriodValue

    return AssetAnalysisPacket(
        issuer_id=data["issuer_id"],
        ticker=data["ticker"],
        sector=data["sector"],
        subsector=data["subsector"],
        classification=data["classification"],
        fundamentals=data["fundamentals"],
        trends={
            k: [PeriodValue(reference_date=pv["reference_date"], value=pv["value"]) for pv in v]
            for k, v in data["trends"].items()
        },
        refiner_scores=data["refiner_scores"],
        flags=data["flags"],
        market_cap=data["market_cap"],
        avg_daily_volume=data["avg_daily_volume"],
        score_reliability=data["score_reliability"],
    )


def _enrich_with_rag(packet: "AssetAnalysisPacket") -> None:
    """Populate packet.rag_context from the RAG embeddings store."""
    try:
        from q3_ai_assistant.rag.response_builder import enrich_packet_with_rag

        with SessionLocal() as session:
            context = enrich_packet_with_rag(session, packet.ticker)
            if context:
                packet.rag_context = context
                logger.info("RAG enriched packet for %s with %d chunks", packet.ticker, len(context))
    except Exception:
        logger.debug("RAG enrichment skipped for %s", packet.ticker, exc_info=True)


def _persist_council_audit(result: "CouncilResult", tenant_id: str) -> None:  # type: ignore[name-defined]
    """Persist council session, opinions, and audit trail to the database."""
    try:
        import uuid as _uuid
        from dataclasses import asdict

        from q3_shared_models.entities import CouncilOpinion, CouncilSession, CouncilSynthesis

        with SessionLocal() as session:
            cs = CouncilSession(
                id=_uuid.UUID(result.session_id),
                chat_session_id=None,
                tenant_id=_uuid.UUID(tenant_id),
                mode=result.mode.value if hasattr(result.mode, "value") else str(result.mode),
                asset_ids=result.asset_ids,
                agent_ids=[o.agent_id for o in result.opinions],
                status="completed",
                input_hash=result.audit_trail.input_hash,
                audit_trail_json=asdict(result.audit_trail),
            )
            session.add(cs)

            for o in result.opinions:
                session.add(CouncilOpinion(
                    id=_uuid.uuid4(),
                    council_session_id=cs.id,
                    agent_id=o.agent_id,
                    verdict=o.verdict.value if hasattr(o.verdict, "value") else str(o.verdict),
                    confidence=o.confidence,
                    opinion_json=asdict(o),
                    hard_rejects_json={"triggered": o.hard_rejects_triggered} if o.hard_rejects_triggered else None,
                    profile_version=o.profile_version,
                    prompt_version=o.prompt_version,
                    provider_used=o.provider_used,
                    model_used=o.model_used,
                    fallback_level=o.fallback_level,
                    tokens_used=o.tokens_used,
                    cost_usd=o.cost_usd,
                ))

            # Persist synthesis
            session.add(CouncilSynthesis(
                id=_uuid.uuid4(),
                council_session_id=cs.id,
                scoreboard_json=asdict(result.scoreboard),
                conflicts_json=[asdict(c) for c in result.conflict_matrix],
                synthesis_text=result.moderator_synthesis.overall_assessment,
            ))

            session.commit()
            logger.info("Persisted council audit for session %s", result.session_id)
    except Exception:
        logger.warning("Failed to persist council audit trail", exc_info=True)


def _create_cascade(pool_type: str = "specialist") -> object:
    """Create a CascadeRouter from settings."""
    from q3_ai_assistant.llm.cascade import CascadeRouter, ProviderEntry
    from q3_ai_assistant.llm.factory import create_adapter

    adapter = create_adapter(settings)
    entry = ProviderEntry(
        provider_name=settings.llm_provider,
        adapter=adapter,
        priority=0,
    )
    return CascadeRouter([entry])


@app.post("/council/analyze", response_model=CouncilResponse)
def council_analyze(req: CouncilRequest) -> CouncilResponse:
    """Run council analysis. Called by NestJS API as proxy."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="AI assistant is disabled")

    # Budget enforcement (per-tenant limit if provided)
    from q3_ai_assistant.security.cost_budget import CostBudget

    daily_limit = req.daily_cost_limit_usd or settings.cost_limit_usd_daily
    budget = CostBudget(daily_max_cost_usd=daily_limit)
    with SessionLocal() as db_session:
        if req.session_id:
            ok, reason = budget.can_proceed(db_session, req.session_id, req.tenant_id)
        else:
            daily_status = budget.check_daily_budget(db_session, req.tenant_id)
            ok = not daily_status.is_exceeded
            reason = "Daily cost limit reached. Try again tomorrow." if not ok else None
    if not ok:
        raise HTTPException(status_code=429, detail=reason)

    from q3_ai_assistant.council.orchestrator import CouncilOrchestrator
    from q3_ai_assistant.council.packet import AssetAnalysisPacket

    # Build packet from DB
    packet_data = _build_packet_from_db(req.ticker)
    if not packet_data:
        raise HTTPException(status_code=404, detail=f"Ticker {req.ticker} not found")

    # Convert to AssetAnalysisPacket
    packet = _dict_to_packet(packet_data)

    # Enrich with RAG context
    _enrich_with_rag(packet)

    # Create cascades
    specialist_cascade = _create_cascade("specialist")
    orchestrator_cascade = _create_cascade("orchestrator")
    orchestrator = CouncilOrchestrator(specialist_cascade, orchestrator_cascade)

    try:
        if req.mode == "solo":
            agent_id = (req.agent_ids or ["greenblatt"])[0]
            result = orchestrator.run_solo(agent_id, packet)
        elif req.mode == "roundtable":
            result = orchestrator.run_roundtable(packet)
        elif req.mode == "debate":
            agent_ids = req.agent_ids or ["greenblatt", "buffett"]
            result = orchestrator.run_debate(agent_ids, packet)
        elif req.mode == "comparison":
            comp_tickers = req.tickers or [req.ticker]
            if len(comp_tickers) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Comparison requires 2-3 tickers",
                )
            # Build packets for all tickers
            comp_packets: list[AssetAnalysisPacket] = [packet]
            for t in comp_tickers[1:]:
                pd = _build_packet_from_db(t)
                if not pd:
                    raise HTTPException(
                        status_code=404, detail=f"Ticker {t} not found",
                    )
                p = _dict_to_packet(pd)
                _enrich_with_rag(p)
                comp_packets.append(p)
            result = orchestrator.run_comparison(comp_tickers, comp_packets)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown mode: {req.mode}")
    except Exception as exc:
        logger.exception("Council analysis failed for %s", req.ticker)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Persist audit trail
    _persist_council_audit(result, req.tenant_id)

    # Serialize result
    from dataclasses import asdict

    result_dict = asdict(result)
    # Serialize comparison matrix if present
    comp_matrix = None
    if hasattr(result, "comparison_matrix") and result.comparison_matrix is not None:
        comp_matrix = asdict(result.comparison_matrix)

    return CouncilResponse(
        session_id=result_dict["session_id"],
        mode=result_dict["mode"].value if hasattr(result_dict["mode"], "value") else str(result_dict["mode"]),
        opinions=[_serialize_opinion(o) for o in result_dict["opinions"]],
        scoreboard=result_dict["scoreboard"],
        conflict_matrix=[asdict(c) if hasattr(c, "__dataclass_fields__") else c for c in result.conflict_matrix],
        moderator_synthesis=result_dict["moderator_synthesis"],
        debate_log=[asdict(d) if hasattr(d, "__dataclass_fields__") else d for d in (result.debate_log or [])],
        comparison_matrix=comp_matrix,
        disclaimer=result.disclaimer,
        audit_trail=result_dict["audit_trail"],
    )


# ---------------------------------------------------------------------------
# Free chat endpoint (tools + RAG + LLM synthesis)
# ---------------------------------------------------------------------------


class FreeChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None
    tenant_id: str
    session_id: str | None = None  # chat session ID for budget tracking
    daily_cost_limit_usd: float | None = None  # per-tenant override


class FreeChatResponse(BaseModel):
    response: str
    tools_used: list[str]
    provider_used: str
    model_used: str
    tokens_used: int
    cost_usd: float


@app.post("/chat/free", response_model=FreeChatResponse)
def chat_free(req: FreeChatRequest) -> FreeChatResponse:
    """Handle free-form chat with tools + RAG + LLM synthesis."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="AI assistant is disabled")

    # PII redaction — strip sensitive data before LLM processing
    from q3_ai_assistant.security.pii_detector import contains_pii, redact_pii

    if contains_pii(req.message):
        logger.info("pii_detected_and_redacted session=%s", req.session_id)
        req.message = redact_pii(req.message)

    # Budget enforcement (per-tenant limit if provided)
    from q3_ai_assistant.security.cost_budget import CostBudget

    daily_limit = req.daily_cost_limit_usd or settings.cost_limit_usd_daily
    budget = CostBudget(daily_max_cost_usd=daily_limit)
    with SessionLocal() as db_session:
        if req.session_id:
            ok, reason = budget.can_proceed(db_session, req.session_id, req.tenant_id)
        else:
            daily_status = budget.check_daily_budget(db_session, req.tenant_id)
            ok = not daily_status.is_exceeded
            reason = "Daily cost limit reached. Try again tomorrow." if not ok else None
    if not ok:
        raise HTTPException(status_code=429, detail=reason)

    from q3_ai_assistant.modules.free_chat import handle_free_chat

    cascade = _create_cascade("specialist")

    try:
        with SessionLocal() as session:
            result = handle_free_chat(
                session,
                req.message,
                cascade,
                history=req.history,
            )
    except Exception as exc:
        logger.exception("Free chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FreeChatResponse(
        response=result.response,
        tools_used=result.tools_used,
        provider_used=result.provider_used,
        model_used=result.model_used,
        tokens_used=result.tokens_used,
        cost_usd=result.cost_usd,
    )


def _serialize_opinion(o: dict) -> dict:
    """Ensure opinion dict has serializable values."""
    if "verdict" in o and hasattr(o["verdict"], "value"):
        o["verdict"] = o["verdict"].value
    if "data_reliability" in o and hasattr(o["data_reliability"], "value"):
        o["data_reliability"] = o["data_reliability"].value
    if "mode" in o and hasattr(o["mode"], "value"):
        o["mode"] = o["mode"].value
    return o


# ---------------------------------------------------------------------------
# Budget status endpoint
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Rubric Suggestion (F2.2.1)
# ---------------------------------------------------------------------------


class RubricSuggestRequest(BaseModel):
    ticker: str
    tenant_id: str
    dimension_key: str = "usd_debt_exposure"


class RubricSuggestResponse(BaseModel):
    suggestion_id: str
    issuer_id: str
    ticker: str
    dimension_key: str
    suggested_score: int
    confidence: str
    rationale: str
    evidence_ref: str
    key_signals: list[str]
    uncertainty_factors: list[str]
    model_used: str
    prompt_version: str
    cost_usd: float


def _build_rubric_issuer_data(ticker: str) -> dict | None:
    """Assemble issuer financial data for rubric scoring prompt."""
    from q3_shared_models.entities import (
        ComputedMetric,
        Issuer,
        Security,
        StatementLine,
    )

    with SessionLocal() as session:
        security = session.query(Security).filter_by(ticker=ticker, is_primary=True).first()
        if not security:
            return None

        issuer = session.query(Issuer).filter_by(id=security.issuer_id).first()
        if not issuer:
            return None

        # Latest computed metrics
        metrics = (
            session.query(ComputedMetric)
            .filter_by(issuer_id=issuer.id)
            .order_by(ComputedMetric.reference_date.desc())
            .limit(20)
            .all()
        )

        computed: dict[str, float | None] = {}
        for m in metrics:
            code = m.metric_code if isinstance(m.metric_code, str) else m.metric_code.value
            if code not in computed:
                val = float(m.value) if m.value is not None else None
                computed[code] = val

        # Latest debt-related statement lines
        debt_keys = [
            "short_term_debt", "long_term_debt", "cash_and_equivalents",
            "financial_result", "total_assets", "shareholders_equity",
            "net_revenue", "ebit",
        ]
        latest_stmts = (
            session.query(StatementLine)
            .filter(
                StatementLine.issuer_id == issuer.id,
                StatementLine.canonical_key.in_(debt_keys),
                StatementLine.scope == "con",
            )
            .order_by(StatementLine.reference_date.desc())
            .limit(30)
            .all()
        )

        financials: dict[str, float | None] = {}
        for sl in latest_stmts:
            key = sl.canonical_key if isinstance(sl.canonical_key, str) else sl.canonical_key.value
            if key not in financials and sl.normalized_value is not None:
                financials[key] = float(sl.normalized_value)

        # Sector context heuristic
        sector = issuer.sector or ""
        sector_lower = sector.lower()
        context_parts: list[str] = []
        if any(kw in sector_lower for kw in ["petróleo", "gás", "mineração", "mineral", "extração"]):
            context_parts.append("Commodity exporter — typically has significant USD-denominated debt and revenue.")
        elif any(kw in sector_lower for kw in ["metalurgia", "siderurgia"]):
            context_parts.append("Steel/metals sector — may have USD debt from equipment/ore imports, some export revenue.")
        elif any(kw in sector_lower for kw in ["agricultura", "alimentos"]):
            context_parts.append("Agriculture/food — export-oriented may have USD revenue as offset; processing-focused may have import costs.")
        elif any(kw in sector_lower for kw in ["farmacêutico"]):
            context_parts.append("Pharma — imported APIs and ingredients are typically USD-priced. Debt may include USD bonds.")
        elif any(kw in sector_lower for kw in ["máquina", "equip", "veíc"]):
            context_parts.append("Machinery/equipment — may have USD component costs and export revenue.")
        elif any(kw in sector_lower for kw in ["energia", "elétrica"]):
            context_parts.append("Electricity — mostly BRL-denominated with regulated revenue. Some USD debt for infrastructure.")
        elif any(kw in sector_lower for kw in ["banco", "financ", "segur"]):
            context_parts.append("Financial sector — may have sophisticated USD hedging. Exposure varies by institution type.")
        elif any(kw in sector_lower for kw in ["construção", "imobil"]):
            context_parts.append("Construction/real estate — mostly domestic BRL operations. Low typical USD exposure.")
        elif any(kw in sector_lower for kw in ["educação"]):
            context_parts.append("Education — domestic BRL revenue. May have USD tech licensing/debt costs.")
        elif any(kw in sector_lower for kw in ["telecom"]):
            context_parts.append("Telecom — equipment imports may be USD. Revenue mostly BRL. Infrastructure debt may include USD.")

        return {
            "ticker": ticker,
            "company_name": issuer.trade_name or issuer.legal_name,
            "sector": issuer.sector or "",
            "subsector": issuer.subsector or "",
            "issuer_id": str(issuer.id),
            "financials": financials,
            "computed_metrics": computed,
            "sector_context": " ".join(context_parts) if context_parts else "",
        }


@app.post("/rubric/suggest", response_model=RubricSuggestResponse)
def suggest_rubric(req: RubricSuggestRequest) -> RubricSuggestResponse:
    """Generate an AI suggestion for a rubric dimension score."""
    import uuid as _uuid

    from q3_ai_assistant.llm.pools import build_specialist_pool
    from q3_ai_assistant.modules.rubric_suggester import SUPPORTED_DIMENSIONS, suggest_dimension

    if req.dimension_key not in SUPPORTED_DIMENSIONS:
        supported = ", ".join(sorted(SUPPORTED_DIMENSIONS))
        raise HTTPException(status_code=400, detail=f"Dimension '{req.dimension_key}' not supported. Supported: {supported}")

    issuer_data = _build_rubric_issuer_data(req.ticker.upper())
    if not issuer_data:
        raise HTTPException(status_code=404, detail=f"Ticker '{req.ticker}' not found.")

    router = build_specialist_pool(settings)

    with SessionLocal() as db_session:
        suggestion = suggest_dimension(
            db_session,
            router,
            cache=None,
            dimension_key=req.dimension_key,
            tenant_id=_uuid.UUID(req.tenant_id),
            issuer_id=_uuid.UUID(issuer_data["issuer_id"]),
            issuer_data=issuer_data,
        )
        db_session.commit()

        out = suggestion.structured_output or {}
        return RubricSuggestResponse(
            suggestion_id=str(suggestion.id),
            issuer_id=issuer_data["issuer_id"],
            ticker=req.ticker.upper(),
            dimension_key=req.dimension_key,
            suggested_score=out.get("suggested_score", 30),
            confidence=out.get("confidence", "low"),
            rationale=out.get("rationale", ""),
            evidence_ref=out.get("evidence_ref", ""),
            key_signals=out.get("key_signals", []),
            uncertainty_factors=out.get("uncertainty_factors", []),
            model_used=suggestion.model_used or "",
            prompt_version=suggestion.prompt_version or "",
            cost_usd=float(suggestion.cost_usd or 0),
        )


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class BudgetStatusRequest(BaseModel):
    tenant_id: str
    session_id: str | None = None


class BudgetStatusResponse(BaseModel):
    daily_total_cost_usd: float
    daily_limit_usd: float
    daily_remaining_usd: float
    daily_exceeded: bool
    daily_near_limit: bool
    session_total_cost_usd: float | None = None
    session_limit_usd: float | None = None
    session_exceeded: bool | None = None


@app.post("/budget/status", response_model=BudgetStatusResponse)
def budget_status(req: BudgetStatusRequest) -> BudgetStatusResponse:
    """Check budget status for a tenant (and optionally a session)."""
    from q3_ai_assistant.security.cost_budget import CostBudget

    budget = CostBudget(daily_max_cost_usd=settings.cost_limit_usd_daily)

    with SessionLocal() as db_session:
        daily = budget.check_daily_budget(db_session, req.tenant_id)
        result = BudgetStatusResponse(
            daily_total_cost_usd=daily.total_cost_usd,
            daily_limit_usd=daily.limit_cost_usd,
            daily_remaining_usd=daily.cost_remaining,
            daily_exceeded=daily.is_exceeded,
            daily_near_limit=daily.is_near_limit,
        )

        if req.session_id:
            session_status = budget.check_session_budget(db_session, req.session_id)
            result.session_total_cost_usd = session_status.total_cost_usd
            result.session_limit_usd = session_status.limit_cost_usd
            result.session_exceeded = session_status.is_exceeded

    return result
