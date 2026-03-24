"""Driver identification — extract top signals per ticker."""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from q3_quant_engine.decision.types import Driver, DriverType

logger = logging.getLogger(__name__)


def extract_drivers(
    session: Session,
    issuer_id: str,
    refiner_flags: list[dict] | None,
    thesis_scores: dict | None,
    earnings_yield: float | None,
) -> list[Driver]:
    """Extract and rank top 5 drivers from metrics, thesis, and refiner."""
    candidates: list[Driver] = []

    # --- Metric-based drivers (historical) ---
    _add_metric_drivers(session, issuer_id, earnings_yield, candidates)

    # --- Thesis-based drivers (structural/cyclical) ---
    if thesis_scores:
        _add_thesis_drivers(thesis_scores, candidates)

    # --- Refiner strength flags (various types) ---
    if refiner_flags:
        for flag in refiner_flags:
            if flag.get("type") == "strength":
                candidates.append(Driver(
                    signal=flag.get("label", "Ponto forte identificado"),
                    source="refiner",
                    driver_type=DriverType.HISTORICAL,
                    magnitude="medium",
                ))

    # Rank by valuation_impact (if computed) then magnitude
    magnitude_order = {"high": 3, "medium": 2, "low": 1, "": 0}
    candidates.sort(
        key=lambda d: (d.valuation_impact or 0, magnitude_order.get(d.magnitude, 0)),
        reverse=True,
    )

    return candidates[:5]


def _add_metric_drivers(
    session: Session,
    issuer_id: str,
    earnings_yield: float | None,
    candidates: list[Driver],
) -> None:
    """Add metric-based drivers from YoY changes in statement_lines + computed_metrics."""
    # Get latest 2 annual periods of key metrics for YoY comparison
    periods = session.execute(text("""
        SELECT DISTINCT f.reference_date
        FROM filings f
        WHERE f.issuer_id = :iid AND f.status = 'completed'
          AND f.filing_type = 'DFP'
        ORDER BY f.reference_date DESC
        LIMIT 2
    """), {"iid": issuer_id}).fetchall()

    if len(periods) < 2:
        return

    latest_ref = periods[0][0]
    prev_ref = periods[1][0]

    # Compare key statement_lines
    for key, label_up, label_down in [
        ("revenue", "Receita em crescimento", "Receita em declínio"),
        ("gross_profit", "Lucro bruto crescente", "Lucro bruto em queda"),
        ("ebit", "EBIT em expansão", "EBIT em contração"),
    ]:
        vals = session.execute(text("""
            SELECT sl.reference_date, sl.normalized_value
            FROM statement_lines sl
            JOIN filings f ON f.id = sl.filing_id
            WHERE f.issuer_id = :iid AND f.status = 'completed'
              AND sl.canonical_key = :key
              AND sl.reference_date IN (:d1, :d2)
            ORDER BY sl.reference_date DESC
        """), {"iid": issuer_id, "key": key, "d1": latest_ref, "d2": prev_ref}).fetchall()

        if len(vals) == 2 and vals[0][1] and vals[1][1]:
            current = float(vals[0][1])
            previous = float(vals[1][1])
            if previous != 0:
                change = (current - previous) / abs(previous)
                if abs(change) > 0.10:  # >10% change
                    is_positive = change > 0
                    # Estimate valuation impact: revenue/EBIT growth directly affects EY
                    impact = abs(change) * (earnings_yield or 0.10)  # proxy: growth * EY
                    candidates.append(Driver(
                        signal=f"{label_up if is_positive else label_down} ({change:+.0%} YoY)",
                        source="statement_lines",
                        driver_type=DriverType.HISTORICAL,
                        magnitude="high" if abs(change) > 0.25 else "medium",
                        value=f"{change:+.1%}",
                        valuation_impact=round(impact * 10000, 0),  # bps
                    ))

    # Compare computed metrics (margins, leverage)
    for metric, label_up, label_down, threshold in [
        ("gross_margin", "Margem bruta em expansão", "Margem bruta em compressão", 0.02),
        ("net_margin", "Margem líquida em expansão", "Margem líquida em compressão", 0.02),
        ("roic", "ROIC crescente", "ROIC em queda", 0.02),
        ("debt_to_ebitda", "Desalavancagem em curso", "Alavancagem crescente", 0.3),
    ]:
        vals = session.execute(text("""
            SELECT reference_date, value
            FROM computed_metrics
            WHERE issuer_id = :iid AND metric_code = :mc
            ORDER BY reference_date DESC LIMIT 2
        """), {"iid": issuer_id, "mc": metric}).fetchall()

        if len(vals) == 2 and vals[0][1] is not None and vals[1][1] is not None:
            current = float(vals[0][1])
            previous = float(vals[1][1])
            diff = current - previous

            if metric == "debt_to_ebitda":
                # Inverse: decrease is positive
                if abs(diff) > threshold:
                    is_positive = diff < 0
                    candidates.append(Driver(
                        signal=f"{label_up if is_positive else label_down} ({diff:+.1f}x)",
                        source="computed_metrics",
                        driver_type=DriverType.HISTORICAL,
                        magnitude="medium",
                        value=f"{diff:+.2f}x",
                        valuation_impact=round(abs(diff) * 500, 0),  # leverage impact in bps
                    ))
            elif abs(diff) > threshold:
                is_positive = diff > 0
                candidates.append(Driver(
                    signal=f"{label_up if is_positive else label_down} ({diff:+.1%})",
                    source="computed_metrics",
                    driver_type=DriverType.HISTORICAL,
                    magnitude="medium",
                    value=f"{diff:+.1%}",
                    valuation_impact=round(abs(diff) * 5000, 0),  # margin bps
                ))

    # Cash generation
    cc = session.execute(text("""
        SELECT value FROM computed_metrics
        WHERE issuer_id = :iid AND metric_code = 'cash_conversion'
        ORDER BY reference_date DESC LIMIT 1
    """), {"iid": issuer_id}).scalar()
    if cc is not None and float(cc) > 1.0:
        candidates.append(Driver(
            signal=f"Forte geração de caixa ({float(cc):.2f}x)",
            source="computed_metrics",
            driver_type=DriverType.HISTORICAL,
            magnitude="medium",
            value=float(cc),
        ))

    # Dividend payer
    dy = session.execute(text("""
        SELECT value FROM computed_metrics
        WHERE issuer_id = :iid AND metric_code = 'dividend_yield'
        ORDER BY reference_date DESC LIMIT 1
    """), {"iid": issuer_id}).scalar()
    if dy is not None and float(dy) > 0.01:
        candidates.append(Driver(
            signal=f"Dividendos consistentes (DY {float(dy)*100:.1f}%)",
            source="computed_metrics",
            driver_type=DriverType.STRUCTURAL,
            magnitude="medium",
            value=float(dy),
            valuation_impact=round(float(dy) * 10000, 0),  # full DY in bps
        ))


def _add_thesis_drivers(thesis_scores: dict, candidates: list[Driver]) -> None:
    """Add drivers from Plan 2 thesis dimensions."""
    bucket = thesis_scores.get("bucket")
    if bucket == "A_DIRECT":
        candidates.append(Driver(
            signal="Exposição direta a commodities",
            source="plan2_thesis",
            driver_type=DriverType.STRUCTURAL,
            magnitude="high",
            valuation_impact=500,
        ))
    elif bucket == "B_INDIRECT":
        candidates.append(Driver(
            signal="Benefício indireto de commodities",
            source="plan2_thesis",
            driver_type=DriverType.CYCLICAL,
            magnitude="medium",
            valuation_impact=250,
        ))

    usd_rev = thesis_scores.get("usd_revenue_offset_score", 0)
    if usd_rev and usd_rev > 60:
        candidates.append(Driver(
            signal="Receita dolarizada (hedge natural)",
            source="plan2_thesis",
            driver_type=DriverType.STRUCTURAL,
            magnitude="high",
            valuation_impact=400,
        ))
