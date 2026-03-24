"""Decision Engine validation — FU-1 through FU-4.

FU-1: Separate evaluation (with refiner vs brute)
FU-2: Yield outlier audit with decomposition
FU-3: Confidence breakdown (already in types)
FU-4: Evidence pack for APPROVED names

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/validate_decisions.py
"""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

from sqlalchemy import text

from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.decision.engine import compute_ticker_decision

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("validate_decisions")

RESULTS_DIR = Path("results/decision_validation")


def _val(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _val(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_val(i) for i in obj]
    if isinstance(obj, tuple):
        return list(obj)
    if hasattr(obj, 'value') and not isinstance(obj, (str, int, float, bool)):
        return obj.value
    return obj


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session:
        # === FU-1: Separate universes ===
        print(f"\n{'=' * 80}")
        print("FU-1 — SEPARATE EVALUATION: REFINER vs BRUTE")
        print(f"{'=' * 80}\n")

        # Tickers WITH refiner data
        refiner_tickers = [r[0] for r in session.execute(text("""
            SELECT DISTINCT rr.ticker
            FROM refinement_results rr
            JOIN securities se ON se.ticker = rr.ticker AND se.is_primary = true AND se.valid_to IS NULL
            JOIN universe_classifications uc ON uc.issuer_id = se.issuer_id
                AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
            ORDER BY rr.ticker
        """)).fetchall()]

        # Top 10 from compat view (brute)
        brute_tickers = [r[0] for r in session.execute(text("""
            SELECT ticker FROM v_financial_statements_compat
            ORDER BY CASE WHEN ebit > 0 THEN 0 ELSE 1 END, COALESCE(earnings_yield, 0) DESC
            LIMIT 10
        """)).fetchall()]

        # Top 10 from refiner-covered only
        refiner_top = [r[0] for r in session.execute(text("""
            SELECT rr.ticker
            FROM refinement_results rr
            JOIN securities se ON se.ticker = rr.ticker AND se.is_primary = true AND se.valid_to IS NULL
            JOIN universe_classifications uc ON uc.issuer_id = se.issuer_id
                AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
            JOIN v_financial_statements_compat v ON v.ticker = rr.ticker
            WHERE v.ebit > 0
            ORDER BY COALESCE(v.earnings_yield, 0) DESC
            LIMIT 10
        """)).fetchall()]

        print(f"Refiner coverage: {len(refiner_tickers)} tickers")
        print(f"Brute Top 10: {brute_tickers}")
        print(f"Refiner Top 10: {refiner_top}")
        print()

        # Run decisions for both sets
        for label, tickers in [("BRUTE TOP 10", brute_tickers), ("REFINER TOP 10", refiner_top)]:
            print(f"--- {label} ---")
            counts = {"APPROVED": 0, "BLOCKED": 0, "REJECTED": 0}
            for ticker in tickers:
                td = compute_ticker_decision(session, ticker)
                s = td.decision.status.value
                counts[s] = counts.get(s, 0) + 1
                q = f"{td.quality.score:.2f}" if td.quality else "N/A"
                v = td.valuation.label.value if td.valuation and td.valuation.label else "N/A"
                iy = f"{td.implied_yield.total_yield:.1%}" if td.implied_yield and td.implied_yield.total_yield else "N/A"
                c = td.confidence.label.value
                outlier = " OUTLIER" if td.implied_yield and td.implied_yield.outlier else ""
                br = f" [{td.decision.block_reason.value}]" if td.decision.block_reason else ""
                print(f"  {ticker:8s} {s:10s}{br:16s} Q={q:5s} V={v:10s} IY={iy:8s}{outlier} C={c}")
            print(f"  Distribution: {counts}")
            print()

        # === FU-2: Yield outlier audit ===
        print(f"{'=' * 80}")
        print("FU-2 — IMPLIED YIELD OUTLIER AUDIT")
        print(f"{'=' * 80}\n")

        # Top 10 highest yields in the universe
        high_yield = session.execute(text("""
            SELECT v.ticker, v.ebit, v.net_debt, v.ebitda, v.market_cap,
                   cm_ey.value as ey, cm_npy.value as npy
            FROM v_financial_statements_compat v
            LEFT JOIN securities se ON se.ticker = v.ticker AND se.is_primary = true AND se.valid_to IS NULL
            LEFT JOIN issuers i ON i.id = se.issuer_id
            LEFT JOIN computed_metrics cm_ey ON cm_ey.issuer_id = i.id AND cm_ey.metric_code = 'earnings_yield'
            LEFT JOIN computed_metrics cm_npy ON cm_npy.issuer_id = i.id AND cm_npy.metric_code = 'net_payout_yield'
            WHERE cm_ey.value IS NOT NULL
            ORDER BY (COALESCE(cm_ey.value, 0) + COALESCE(cm_npy.value, 0)) DESC
            LIMIT 10
        """)).fetchall()

        print(f"{'Ticker':8s} {'EY':>8s} {'NPY':>8s} {'Total':>8s} {'EBIT':>14s} {'Net Debt':>14s} {'Mkt Cap':>14s} {'EV':>14s}")
        print("-" * 100)
        for r in high_yield:
            ticker = r[0]
            ebit = float(r[1]) if r[1] else 0
            nd = float(r[2]) if r[2] else 0
            mcap = float(r[4]) if r[4] else 0
            ey = float(r[5]) if r[5] else 0
            npy = float(r[6]) if r[6] else 0
            ev = mcap + nd
            total = ey + npy
            flag = " ← OUTLIER" if total > 0.40 else ""
            print(f"  {ticker:8s} {ey:7.1%} {npy:7.1%} {total:7.1%} {ebit:>13,.0f} {nd:>13,.0f} {mcap:>13,.0f} {ev:>13,.0f}{flag}")

        print()
        print("Outlier analysis:")
        for r in high_yield:
            ey = float(r[5]) if r[5] else 0
            npy = float(r[6]) if r[6] else 0
            total = ey + npy
            if total > 0.40:
                ticker = r[0]
                ebit = float(r[1]) if r[1] else 0
                mcap = float(r[4]) if r[4] else 0
                nd = float(r[2]) if r[2] else 0
                ev = mcap + nd
                reasons = []
                if ev < ebit * 3:
                    reasons.append(f"EV ({ev:,.0f}) < 3x EBIT ({ebit:,.0f}) → possível EV distorcido")
                if mcap < 100_000_000:
                    reasons.append(f"Micro cap (R$ {mcap:,.0f}) → liquidez/pricing questionável")
                if ey > 0.30:
                    reasons.append(f"EY {ey:.0%} extremamente alto")
                if not reasons:
                    reasons.append("Possível deep value legítimo, mas requer investigação")
                print(f"  {ticker}: {'; '.join(reasons)}")
        print()

        # === FU-4: Evidence pack for APPROVED ===
        print(f"{'=' * 80}")
        print("FU-4 — EVIDENCE PACK: APPROVED NAMES")
        print(f"{'=' * 80}\n")

        # Run for refiner top 10 and collect APPROVED
        approved = []
        all_decisions = []
        for ticker in refiner_top:
            td = compute_ticker_decision(session, ticker)
            all_decisions.append(td)
            if td.decision.status.value == "APPROVED":
                approved.append(td)

        if not approved:
            # Try brute top 10
            for ticker in brute_tickers:
                td = compute_ticker_decision(session, ticker)
                if td.decision.status.value == "APPROVED" and td not in approved:
                    approved.append(td)

        for td in approved:
            print(f"--- {td.ticker} ({td.name[:40]}) ---")
            print(f"  Status:     {td.decision.status.value}")
            print(f"  Reason:     {td.decision.reason}")
            print(f"  Quality:    {td.quality.score:.2f} ({td.quality.label})" if td.quality else "  Quality: N/A")
            if td.quality:
                print(f"    EarningsQ: {td.quality.earnings_quality}")
                print(f"    Safety:    {td.quality.safety}")
                print(f"    OpConsist: {td.quality.operating_consistency}")
                print(f"    CapDisc:   {td.quality.capital_discipline}")
            print(f"  Valuation:  {td.valuation.label.value if td.valuation and td.valuation.label else 'N/A'}")
            if td.valuation:
                print(f"    EY:             {td.valuation.earnings_yield:.1%}" if td.valuation.earnings_yield else "")
                print(f"    Sector pctl:    {td.valuation.ey_sector_percentile}")
                print(f"    Sector median:  {td.valuation.ey_sector_median:.1%}" if td.valuation.ey_sector_median else "")
                print(f"    Implied price:  R$ {td.valuation.implied_price:.2f}" if td.valuation.implied_price else "")
                print(f"    Implied range:  R$ {td.valuation.implied_value_range[0]:.2f} – {td.valuation.implied_value_range[1]:.2f}" if td.valuation.implied_value_range else "")
                print(f"    Current price:  R$ {td.valuation.current_price:.2f}" if td.valuation.current_price else "")
                print(f"    Upside:         {td.valuation.upside:.1%}" if td.valuation.upside else "")
            print(f"  Yield:      {td.implied_yield.total_yield:.1%}" if td.implied_yield and td.implied_yield.total_yield else "  Yield: N/A")
            if td.implied_yield and td.implied_yield.outlier:
                print(f"    ⚠ OUTLIER: {td.implied_yield.outlier_reason}")
            print(f"  Confidence: {td.confidence.score:.2f} ({td.confidence.label.value})")
            print(f"    Penalties: {td.confidence.penalties}")
            print(f"    Breakdown: refiner={not td.confidence.breakdown.missing_refiner_data} thesis={not td.confidence.breakdown.missing_thesis_data} sector_fb={td.confidence.breakdown.sector_fallback_used}")
            print(f"  Governance: {td.decision.governance_note[:80]}")
            print(f"  Drivers ({len(td.drivers)}):")
            for d in td.drivers:
                print(f"    [{d.driver_type.value:10s}] {d.signal}")
            print(f"  Risks ({len(td.risks)}):")
            for r in td.risks:
                crit = " ⚠ CRITICAL" if r.critical else ""
                print(f"    {r.signal}{crit}")

            # Nearest competitor that was BLOCKED/REJECTED
            nearby = [d for d in all_decisions if d.decision.status.value != "APPROVED"]
            if nearby:
                nearest = nearby[0]
                print(f"  Nearest non-approved: {nearest.ticker} ({nearest.decision.status.value}: {nearest.decision.reason[:60]})")
            print()

    # Save all artifacts
    (RESULTS_DIR / "validation_report.json").write_text(json.dumps({
        "fu1_brute_tickers": brute_tickers,
        "fu1_refiner_tickers": refiner_top,
        "fu2_outlier_count": sum(1 for r in high_yield if (float(r[5] or 0) + float(r[6] or 0)) > 0.40),
        "fu4_approved_count": len(approved),
        "fu4_approved_tickers": [td.ticker for td in approved],
    }, indent=2))

    print(f"Artifacts: {RESULTS_DIR}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
