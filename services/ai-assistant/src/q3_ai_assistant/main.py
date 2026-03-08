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

app = FastAPI(title="Q3 AI Assistant", version="0.1.0")


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

    from q3_ai_assistant.council.orchestrator import CouncilOrchestrator
    from q3_ai_assistant.council.packet import AssetAnalysisPacket, PeriodValue

    # Build packet from DB
    packet_data = _build_packet_from_db(req.ticker)
    if not packet_data:
        raise HTTPException(status_code=404, detail=f"Ticker {req.ticker} not found")

    # Convert to AssetAnalysisPacket
    packet = AssetAnalysisPacket(
        issuer_id=packet_data["issuer_id"],
        ticker=packet_data["ticker"],
        sector=packet_data["sector"],
        subsector=packet_data["subsector"],
        classification=packet_data["classification"],
        fundamentals=packet_data["fundamentals"],
        trends={
            k: [PeriodValue(reference_date=pv["reference_date"], value=pv["value"]) for pv in v]
            for k, v in packet_data["trends"].items()
        },
        refiner_scores=packet_data["refiner_scores"],
        flags=packet_data["flags"],
        market_cap=packet_data["market_cap"],
        avg_daily_volume=packet_data["avg_daily_volume"],
        score_reliability=packet_data["score_reliability"],
    )

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
                comp_packets.append(AssetAnalysisPacket(
                    issuer_id=pd["issuer_id"],
                    ticker=pd["ticker"],
                    sector=pd["sector"],
                    subsector=pd["subsector"],
                    classification=pd["classification"],
                    fundamentals=pd["fundamentals"],
                    trends={
                        k: [PeriodValue(reference_date=pv["reference_date"], value=pv["value"]) for pv in v]
                        for k, v in pd["trends"].items()
                    },
                    refiner_scores=pd["refiner_scores"],
                    flags=pd["flags"],
                    market_cap=pd["market_cap"],
                    avg_daily_volume=pd["avg_daily_volume"],
                    score_reliability=pd["score_reliability"],
                ))
            result = orchestrator.run_comparison(comp_tickers, comp_packets)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown mode: {req.mode}")
    except Exception as exc:
        logger.exception("Council analysis failed for %s", req.ticker)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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


def _serialize_opinion(o: dict) -> dict:
    """Ensure opinion dict has serializable values."""
    if "verdict" in o and hasattr(o["verdict"], "value"):
        o["verdict"] = o["verdict"].value
    if "data_reliability" in o and hasattr(o["data_reliability"], "value"):
        o["data_reliability"] = o["data_reliability"].value
    if "mode" in o and hasattr(o["mode"], "value"):
        o["mode"] = o["mode"].value
    return o
