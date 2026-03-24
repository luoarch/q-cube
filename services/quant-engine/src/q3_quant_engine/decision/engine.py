"""Ticker Decision Engine — orchestrator.

Composes quality, valuation, drivers, risks, confidence, and final decision
into a deterministic per-ticker output.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from q3_quant_engine.decision.confidence import compute_confidence
from q3_quant_engine.decision.drivers import extract_drivers
from q3_quant_engine.decision.risks import extract_risks
from q3_quant_engine.decision.types import (
    BlockReason,
    ConfidenceLabel,
    DecisionBlock,
    DecisionStatus,
    ImpliedYieldBlock,
    ProvenanceBlock,
    QualityBlock,
    TickerDecision,
    ValuationLabel,
)
from q3_quant_engine.decision.valuation import compute_valuation

logger = logging.getLogger(__name__)

# Dynamic yield threshold: sector-adjusted floor with absolute minimum
ABSOLUTE_MIN_YIELD = 0.08  # 8% hard floor
DEFAULT_YIELD_SPREAD = 0.04  # 4% spread over sector median EY


def compute_ticker_decision(
    session: Session,
    ticker: str,
) -> TickerDecision:
    """Produce a complete deterministic decision for one ticker."""

    # --- Resolve issuer ---
    issuer_row = session.execute(text("""
        SELECT i.id, i.legal_name, i.sector
        FROM issuers i
        JOIN securities se ON se.issuer_id = i.id
        WHERE se.ticker = :ticker AND se.is_primary = true AND se.valid_to IS NULL
        LIMIT 1
    """), {"ticker": ticker}).fetchone()

    if not issuer_row:
        return _empty_decision(ticker, "Issuer não encontrado")

    issuer_id, name, sector = str(issuer_row[0]), issuer_row[1] or ticker, issuer_row[2]

    # --- Quality (from refiner) ---
    quality = _load_quality(session, issuer_id)

    # --- Valuation ---
    valuation = compute_valuation(session, issuer_id, ticker, sector)

    # --- Thesis scores ---
    thesis_scores = _load_thesis(session, issuer_id)

    # --- Refiner flags ---
    refiner_flags = _load_refiner_flags(session, issuer_id)

    # --- Implied yield ---
    ey = valuation.earnings_yield
    npy = _get_metric(session, issuer_id, "net_payout_yield")
    implied_yield = _build_implied_yield(ey, npy, valuation)

    # --- Drivers ---
    drivers = extract_drivers(session, issuer_id, refiner_flags, thesis_scores, ey)

    # --- Risks (including volatility) ---
    risks = extract_risks(session, issuer_id, ticker, refiner_flags, thesis_scores)

    # --- Confidence ---
    data_completeness = _get_refiner_completeness(session, issuer_id)
    evidence_quality = _get_evidence_quality(session, issuer_id)
    confidence = compute_confidence(
        data_completeness=data_completeness,
        evidence_quality=evidence_quality,
        valuation=valuation if valuation.earnings_yield else None,
        driver_count=len(drivers),
        sector_fallback=valuation.sector_fallback,
        has_refiner=quality is not None,
    )

    # --- Decision ---
    yield_threshold = _dynamic_yield_threshold(valuation)
    decision = _make_decision(quality, valuation, implied_yield, risks, confidence, yield_threshold)

    # --- Provenance ---
    provenance = _build_provenance(session, issuer_id)

    return TickerDecision(
        ticker=ticker,
        name=name,
        sector=sector or "Desconhecido",
        generated_at=datetime.now(timezone.utc).isoformat(),
        quality=quality,
        valuation=valuation,
        implied_yield=implied_yield,
        drivers=drivers,
        risks=risks,
        confidence=confidence,
        decision=decision,
        provenance=provenance,
    )


def _dynamic_yield_threshold(valuation) -> float:
    """Sector-adjusted yield threshold. Max of absolute floor and sector-relative floor."""
    if valuation and valuation.ey_sector_median and valuation.ey_sector_median > 0:
        sector_floor = valuation.ey_sector_median * 0.5  # at least 50% of sector median
        return max(ABSOLUTE_MIN_YIELD, sector_floor + DEFAULT_YIELD_SPREAD)
    return ABSOLUTE_MIN_YIELD + DEFAULT_YIELD_SPREAD  # 12% default


def _make_decision(quality, valuation, implied_yield, risks, confidence, yield_threshold) -> DecisionBlock:
    has_critical = any(r.critical for r in risks)
    q_score = quality.score if quality else None
    v_label = valuation.label if valuation else None
    iy_total = implied_yield.total_yield if implied_yield else None
    conf_label = confidence.label

    # Step 1: Hard rejections
    if has_critical:
        critical_labels = [r.signal for r in risks if r.critical]
        return DecisionBlock(
            status=DecisionStatus.REJECTED,
            reason=f"Risco crítico: {critical_labels[0]}",
            governance_note=_governance_note(),
        )

    if q_score is not None and q_score < 0.3:
        return DecisionBlock(
            status=DecisionStatus.REJECTED,
            reason=f"Qualidade abaixo do limiar (score={q_score:.2f})",
            governance_note=_governance_note(),
        )

    if v_label == ValuationLabel.EXPENSIVE and (q_score is None or q_score < 0.6):
        return DecisionBlock(
            status=DecisionStatus.REJECTED,
            reason="Valuation desfavorável com qualidade insuficiente",
            governance_note=_governance_note(),
        )

    # Step 2: Yield gate (dynamic threshold)
    if iy_total is not None and iy_total < yield_threshold:
        return DecisionBlock(
            status=DecisionStatus.BLOCKED,
            block_reason=BlockReason.LOW_YIELD,
            reason=f"Implied yield ({iy_total:.1%}) abaixo do mínimo dinâmico ({yield_threshold:.1%})",
            governance_note=_governance_note(),
        )

    # Step 3: Confidence gate
    if conf_label == ConfidenceLabel.LOW:
        return DecisionBlock(
            status=DecisionStatus.BLOCKED,
            block_reason=BlockReason.LOW_CONFIDENCE,
            reason="Evidência insuficiente para decisão",
            governance_note=_governance_note(),
        )

    # Step 4: Data completeness
    if v_label is None or q_score is None:
        return DecisionBlock(
            status=DecisionStatus.BLOCKED,
            block_reason=BlockReason.DATA_MISSING,
            reason="Dados incompletos para decisão",
            governance_note=_governance_note(),
        )

    # Step 5: Approval
    if q_score >= 0.5 and v_label in (ValuationLabel.CHEAP, ValuationLabel.FAIR) and conf_label in (ConfidenceLabel.HIGH, ConfidenceLabel.MEDIUM):
        return DecisionBlock(
            status=DecisionStatus.APPROVED,
            reason="Qualidade adequada, valuation favorável, yield acima do mínimo",
            governance_note=_governance_note(),
        )

    # Step 6: Catch-all
    return DecisionBlock(
        status=DecisionStatus.BLOCKED,
        block_reason=BlockReason.MARGINAL,
        reason="Caso limítrofe — evidência insuficiente para aprovação",
        governance_note=_governance_note(),
    )


def _governance_note() -> str:
    return (
        "Estratégia subjacente (ctrl_brazil_20m) é controle rejeitado. "
        "Classificação reflete dados fundamentalistas, não performance empírica."
    )


def _build_implied_yield(ey, npy, valuation) -> ImpliedYieldBlock | None:
    if ey is None:
        return None
    npy_val = float(npy) if npy is not None else 0.0
    total = ey + npy_val
    threshold = _dynamic_yield_threshold(valuation)
    return ImpliedYieldBlock(
        earnings_yield=ey,
        net_payout_yield=npy_val,
        total_yield=round(total, 6),
        label=f"Implied yield {total:.1%} (EY + payout, sem crescimento)",
        meets_minimum=total >= threshold,
        minimum_threshold=round(threshold, 4),
    )


def _load_quality(session: Session, issuer_id: str) -> QualityBlock | None:
    row = session.execute(text("""
        SELECT refinement_score, earnings_quality_score, safety_score,
               operating_consistency_score, capital_discipline_score
        FROM refinement_results
        WHERE issuer_id = :iid
        ORDER BY created_at DESC LIMIT 1
    """), {"iid": issuer_id}).fetchone()
    if not row or row[0] is None:
        return None
    score = float(row[0])
    label = "HIGH" if score >= 0.7 else "MEDIUM" if score >= 0.4 else "LOW"
    return QualityBlock(
        score=score, label=label,
        earnings_quality=float(row[1]) if row[1] else None,
        safety=float(row[2]) if row[2] else None,
        operating_consistency=float(row[3]) if row[3] else None,
        capital_discipline=float(row[4]) if row[4] else None,
    )


def _load_thesis(session: Session, issuer_id: str) -> dict | None:
    row = session.execute(text("""
        SELECT bucket, final_commodity_affinity_score, final_dollar_fragility_score,
               usd_debt_exposure_score, usd_import_dependence_score, usd_revenue_offset_score
        FROM plan2_thesis_scores
        WHERE issuer_id = :iid
        ORDER BY created_at DESC LIMIT 1
    """), {"iid": issuer_id}).fetchone()
    if not row:
        return None
    return {
        "bucket": row[0],
        "commodity_affinity": float(row[1]) if row[1] else 0,
        "dollar_fragility": float(row[2]) if row[2] else 0,
        "usd_debt_exposure_score": float(row[3]) if row[3] else 0,
        "usd_import_dependence_score": float(row[4]) if row[4] else 0,
        "usd_revenue_offset_score": float(row[5]) if row[5] else 0,
    }


def _load_refiner_flags(session: Session, issuer_id: str) -> list[dict] | None:
    row = session.execute(text("""
        SELECT flags_json FROM refinement_results
        WHERE issuer_id = :iid ORDER BY created_at DESC LIMIT 1
    """), {"iid": issuer_id}).fetchone()
    if not row or not row[0]:
        return None
    flags = row[0]
    return flags if isinstance(flags, list) else []


def _get_metric(session: Session, issuer_id: str, metric_code: str):
    val = session.execute(text("""
        SELECT value FROM computed_metrics
        WHERE issuer_id = :iid AND metric_code = :mc
        ORDER BY reference_date DESC LIMIT 1
    """), {"iid": issuer_id, "mc": metric_code}).scalar()
    return float(val) if val is not None else None


def _get_refiner_completeness(session: Session, issuer_id: str) -> float | None:
    row = session.execute(text("""
        SELECT data_completeness_json FROM refinement_results
        WHERE issuer_id = :iid ORDER BY created_at DESC LIMIT 1
    """), {"iid": issuer_id}).fetchone()
    if not row or not row[0]:
        return None
    comp = row[0]
    return comp.get("completeness_ratio") if isinstance(comp, dict) else None


def _get_evidence_quality(session: Session, issuer_id: str) -> str | None:
    """Derive evidence quality from thesis feature_input_json provenance."""
    row = session.execute(text("""
        SELECT feature_input_json FROM plan2_thesis_scores
        WHERE issuer_id = :iid ORDER BY created_at DESC LIMIT 1
    """), {"iid": issuer_id}).fetchone()
    if not row or not row[0]:
        return None
    features = row[0]
    if isinstance(features, dict):
        # Check provenance: count quantitative vs default sources
        sources = [v.get("source_type") for v in features.values() if isinstance(v, dict)]
        quant_count = sum(1 for s in sources if s in ("QUANTITATIVE", "RUBRIC_MANUAL"))
        if quant_count > len(sources) * 0.5:
            return "HIGH_EVIDENCE"
        elif quant_count > 0:
            return "MIXED_EVIDENCE"
    return "LOW_EVIDENCE"


def _build_provenance(session: Session, issuer_id: str) -> ProvenanceBlock:
    ref_date = session.execute(text("""
        SELECT reference_date FROM computed_metrics
        WHERE issuer_id = :iid ORDER BY reference_date DESC LIMIT 1
    """), {"iid": issuer_id}).scalar()

    snap_date = session.execute(text("""
        SELECT ms.fetched_at FROM market_snapshots ms
        JOIN securities se ON se.id = ms.security_id
        WHERE se.issuer_id = :iid AND se.is_primary = true
        ORDER BY ms.fetched_at DESC LIMIT 1
    """), {"iid": issuer_id}).scalar()

    return ProvenanceBlock(
        ranking_source="magic_formula_brazil",
        metrics_reference_date=str(ref_date) if ref_date else "",
        snapshot_date=str(snap_date)[:10] if snap_date else "",
        universe_policy="v1",
    )


def _empty_decision(ticker: str, reason: str) -> TickerDecision:
    return TickerDecision(
        ticker=ticker, name=ticker, sector="Desconhecido",
        generated_at=datetime.now(timezone.utc).isoformat(),
        quality=None, valuation=None, implied_yield=None,
        drivers=[], risks=[],
        confidence=compute_confidence(None, None, None, 0, False, False),
        decision=DecisionBlock(
            status=DecisionStatus.REJECTED,
            block_reason=BlockReason.DATA_MISSING,
            reason=reason,
        ),
        provenance=ProvenanceBlock(),
    )
