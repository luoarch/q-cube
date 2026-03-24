"""Risk extraction — refiner flags + fragility + leverage + volatility."""
from __future__ import annotations

import logging
import math

from sqlalchemy import text
from sqlalchemy.orm import Session

from q3_quant_engine.decision.types import Risk

logger = logging.getLogger(__name__)

# Critical thresholds
CRITICAL_LEVERAGE = 5.0
CRITICAL_CASH_CONVERSION = -0.5
CRITICAL_INTEREST_COVERAGE = 1.0
HIGH_LEVERAGE = 3.0
LOW_INTEREST_COVERAGE = 2.0


def extract_risks(
    session: Session,
    issuer_id: str,
    ticker: str,
    refiner_flags: list[dict] | None,
    thesis_scores: dict | None,
) -> list[Risk]:
    """Extract all risks from refiner, thesis, metrics, and market data."""
    risks: list[Risk] = []

    # --- Refiner red flags ---
    if refiner_flags:
        for flag in refiner_flags:
            if flag.get("type") == "red_flag" or flag.get("severity") == "high":
                risks.append(Risk(
                    signal=flag.get("label", "Red flag identificado"),
                    source="refiner",
                    critical=flag.get("severity") == "critical",
                ))

    # --- Plan 2 fragility ---
    if thesis_scores:
        bucket = thesis_scores.get("bucket")
        if bucket == "D_FRAGILE":
            # Check if also leveraged → critical combo
            debt_ebitda = _get_metric(session, issuer_id, "debt_to_ebitda")
            critical = debt_ebitda is not None and debt_ebitda > HIGH_LEVERAGE
            risks.append(Risk(
                signal="Fragilidade cambial elevada" + (" + alavancagem" if critical else ""),
                source="plan2_thesis",
                critical=critical,
            ))

        usd_debt = thesis_scores.get("usd_debt_exposure_score", 0)
        if usd_debt and usd_debt > 70:
            risks.append(Risk(signal="Dívida em USD significativa", source="plan2_thesis"))

        usd_import = thesis_scores.get("usd_import_dependence_score", 0)
        if usd_import and usd_import > 70:
            risks.append(Risk(signal="Dependência de insumos importados", source="plan2_thesis"))

    # --- Computed metrics risks ---
    debt_ebitda = _get_metric(session, issuer_id, "debt_to_ebitda")
    if debt_ebitda is not None:
        if debt_ebitda > CRITICAL_LEVERAGE:
            risks.append(Risk(
                signal=f"Alavancagem crítica ({debt_ebitda:.1f}x)",
                source="computed_metrics", critical=True,
            ))
        elif debt_ebitda > HIGH_LEVERAGE:
            risks.append(Risk(
                signal=f"Alavancagem elevada ({debt_ebitda:.1f}x)",
                source="computed_metrics",
            ))

    cc = _get_metric(session, issuer_id, "cash_conversion")
    if cc is not None and cc < 0:
        risks.append(Risk(
            signal=f"Geração de caixa negativa ({cc:.2f}x)",
            source="computed_metrics",
            critical=cc < CRITICAL_CASH_CONVERSION,
        ))

    ic = _get_metric(session, issuer_id, "interest_coverage")
    if ic is not None and ic < LOW_INTEREST_COVERAGE:
        risks.append(Risk(
            signal=f"Cobertura de juros baixa ({ic:.1f}x)",
            source="computed_metrics",
            critical=ic < CRITICAL_INTEREST_COVERAGE,
        ))

    # --- Market data risk (volatility proxy from price history) ---
    vol = _compute_price_volatility(session, issuer_id)
    if vol is not None and vol > 0.50:  # annualized vol > 50%
        risks.append(Risk(
            signal=f"Volatilidade elevada ({vol*100:.0f}% anualizada)",
            source="market_snapshots",
            critical=vol > 0.80,
        ))

    # --- No market data ---
    has_market = session.execute(text("""
        SELECT 1 FROM market_snapshots ms
        JOIN securities se ON se.id = ms.security_id
        WHERE se.issuer_id = :iid AND se.is_primary = true AND se.valid_to IS NULL
        LIMIT 1
    """), {"iid": issuer_id}).fetchone()
    if not has_market:
        risks.append(Risk(
            signal="Sem dados de mercado atualizados",
            source="market_snapshots", critical=True,
        ))

    return risks


def _get_metric(session: Session, issuer_id: str, metric_code: str) -> float | None:
    val = session.execute(text("""
        SELECT value FROM computed_metrics
        WHERE issuer_id = :iid AND metric_code = :mc
        ORDER BY reference_date DESC LIMIT 1
    """), {"iid": issuer_id, "mc": metric_code}).scalar()
    return float(val) if val is not None else None


def _compute_price_volatility(session: Session, issuer_id: str) -> float | None:
    """Compute annualized price volatility from historical snapshots (last 12 months)."""
    prices = session.execute(text("""
        SELECT ms.price, ms.fetched_at
        FROM market_snapshots ms
        JOIN securities se ON se.id = ms.security_id
        WHERE se.issuer_id = :iid AND se.is_primary = true AND se.valid_to IS NULL
          AND ms.price IS NOT NULL AND ms.price > 0
        ORDER BY ms.fetched_at DESC
        LIMIT 13
    """), {"iid": issuer_id}).fetchall()

    if len(prices) < 4:
        return None

    # Monthly returns
    values = [float(r[0]) for r in reversed(prices)]
    returns = [(values[i] / values[i - 1]) - 1 for i in range(1, len(values)) if values[i - 1] > 0]

    if len(returns) < 3:
        return None

    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    monthly_vol = math.sqrt(variance)
    annualized = monthly_vol * math.sqrt(12)
    return annualized
