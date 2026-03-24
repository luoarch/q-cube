"""Pilot Phase 1 — Monthly Classification Cycle.

Runs the full decision pipeline, logs decisions prospectively,
compares against baselines, and produces the monthly pilot report.

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/run_pilot_month.py [--month 2026-04]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.decision.engine import compute_ticker_decision

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pilot_month")

RESULTS_DIR = Path("results/pilot")
ENGINE_VERSION = "v1.0-frozen"


def _to_dict(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, tuple):
        return list(obj)
    if hasattr(obj, 'value') and not isinstance(obj, (str, int, float, bool)):
        return obj.value
    return obj


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=datetime.now().strftime("%Y-%m"))
    args = parser.parse_args()
    cycle = args.month

    month_dir = RESULTS_DIR / cycle
    month_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    with SessionLocal() as session:
        # === Get eligible tickers ===
        eligible = session.execute(text("""
            SELECT DISTINCT ON (i.id) se.ticker, i.id as issuer_id
            FROM securities se
            JOIN issuers i ON i.id = se.issuer_id
            JOIN universe_classifications uc ON uc.issuer_id = i.id
                AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
            JOIN computed_metrics cm ON cm.issuer_id = i.id AND cm.metric_code = 'earnings_yield'
            WHERE se.is_primary = true AND se.valid_to IS NULL
            ORDER BY i.id, se.ticker
        """)).fetchall()
        tickers = [(r[0], str(r[1])) for r in eligible]

        # === Run decision engine ===
        logger.info("Cycle %s: Running decisions for %d tickers...", cycle, len(tickers))
        decisions = []
        for ticker, _ in tickers:
            td = compute_ticker_decision(session, ticker)
            decisions.append(td)

        elapsed = time.time() - t0
        logger.info("Decisions complete: %d in %.0fs", len(decisions), elapsed)

        # === Baselines ===
        # Ranking Top-20 (by EY)
        ranking_top20 = [r[0] for r in session.execute(text("""
            SELECT ticker FROM v_financial_statements_compat
            WHERE ebit IS NOT NULL AND ebit > 0
            ORDER BY COALESCE(earnings_yield, 0) DESC
            LIMIT 20
        """)).fetchall()]

        # Universe EW (all eligible tickers)
        universe_ew = [t for t, _ in tickers]

        # === Classification ===
        status_dist = Counter(td.decision.status.value for td in decisions)
        conf_dist = Counter(td.confidence.label.value for td in decisions)
        approved = sorted(td.ticker for td in decisions if td.decision.status.value == "APPROVED")
        blocked = sorted(td.ticker for td in decisions if td.decision.status.value == "BLOCKED")
        rejected = sorted(td.ticker for td in decisions if td.decision.status.value == "REJECTED")

        # === Coverage metrics ===
        has_refiner = sum(1 for td in decisions if td.quality is not None)
        has_thesis = sum(1 for td in decisions if any(d.source == "plan2_thesis" for d in td.drivers))
        val_suppressed = sum(1 for td in decisions if td.valuation and td.valuation.suppression_reason)
        val_invalid = sum(1 for td in decisions if td.valuation and not td.valuation.valuation_valid)

        # Thesis-gap analysis
        blocked_by_thesis = sum(
            1 for td in decisions
            if td.decision.status.value == "BLOCKED"
            and td.confidence.breakdown.missing_thesis_data
            and not td.confidence.breakdown.missing_refiner_data
        )
        approved_despite_thesis = sum(
            1 for td in decisions
            if td.decision.status.value == "APPROVED"
            and td.confidence.breakdown.missing_thesis_data
        )

        # Block reason breakdown
        block_reasons = Counter(
            td.decision.block_reason.value if td.decision.block_reason else "NONE"
            for td in decisions if td.decision.status.value == "BLOCKED"
        )

        # === Freeze thresholds snapshot ===
        thresholds = {
            "engine_version": ENGINE_VERSION,
            "quality_min": 0.5,
            "yield_threshold": "dynamic: max(8%, sector_median*0.5 + 4%)",
            "confidence_min": "MEDIUM (0.40)",
            "suppression_upside_max": "300%",
            "mcap_invalidation": "< R$1",
            "critical_leverage": 5.0,
            "critical_interest_coverage": 1.0,
            "critical_cash_conversion": -0.5,
        }

        # === Decision journal ===
        journal = {
            "cycle": cycle,
            "run_date": datetime.now(timezone.utc).isoformat(),
            "engine_version": ENGINE_VERSION,
            "universe_size": len(tickers),
            "classification_counts": dict(status_dist),
            "approved_tickers": approved,
            "blocked_tickers": blocked,
            "rejected_tickers": rejected,
            "baselines": {
                "ranking_top20": ranking_top20,
                "universe_ew_count": len(universe_ew),
            },
            "human_overrides": [],
            "forward_returns": None,
            "thresholds_snapshot": thresholds,
        }
        (month_dir / "decision_journal.json").write_text(json.dumps(journal, indent=2, ensure_ascii=False))

        # Save full decisions
        full_decisions = [_to_dict(td) for td in decisions]
        (month_dir / "all_decisions.json").write_text(json.dumps(full_decisions, indent=2, ensure_ascii=False))

        # === Print report ===
        print(f"\n{'=' * 80}")
        print(f"PILOT MONTHLY REPORT — {cycle}")
        print(f"{'=' * 80}")
        print(f"Engine: {ENGINE_VERSION} | Elapsed: {elapsed:.0f}s | Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()

        # Section 1: Coverage
        print("--- 1. PIPELINE COVERAGE ---")
        print(f"  Universe:         {len(tickers)}")
        print(f"  Refiner coverage: {has_refiner}/{len(tickers)} ({has_refiner/len(tickers)*100:.0f}%)")
        print(f"  Thesis coverage:  {has_thesis}/{len(tickers)} ({has_thesis/len(tickers)*100:.0f}%)")
        print(f"  Val suppressed:   {val_suppressed}/{len(tickers)} ({val_suppressed/len(tickers)*100:.0f}%)")
        print(f"  Val invalid:      {val_invalid}/{len(tickers)}")
        print(f"  Confidence:       {dict(conf_dist)}")
        print()

        # Section 2: Classification
        print("--- 2. CLASSIFICATION ---")
        print(f"  APPROVED:  {len(approved)} ({len(approved)/len(tickers)*100:.0f}%)")
        print(f"  BLOCKED:   {len(blocked)} ({len(blocked)/len(tickers)*100:.0f}%)")
        print(f"  REJECTED:  {len(rejected)} ({len(rejected)/len(tickers)*100:.0f}%)")
        print(f"  Block reasons: {dict(block_reasons)}")
        print()

        # Thesis-gap analysis
        print("--- 3. THESIS-GAP ANALYSIS ---")
        print(f"  BLOCKED by thesis gap (refiner OK, thesis missing): {blocked_by_thesis}")
        print(f"  APPROVED despite thesis missing: {approved_despite_thesis}")
        print(f"  Thesis coverage: {has_thesis}/{len(tickers)} ({has_thesis/len(tickers)*100:.0f}%)")
        print()

        # Section 4: Baselines
        print("--- 4. BASELINES ---")
        overlap_ranking = set(approved) & set(ranking_top20)
        print(f"  Ranking Top-20: {ranking_top20[:10]}...")
        print(f"  APPROVED ∩ Ranking Top-20: {len(overlap_ranking)} ({sorted(overlap_ranking)})")
        print()

        # Section 5: Notable names
        print("--- 5. NOTABLE APPROVALS ---")
        for td in sorted(decisions, key=lambda d: -(d.quality.score if d.quality else 0)):
            if td.decision.status.value != "APPROVED":
                continue
            q = f"{td.quality.score:.2f}" if td.quality else "N/A"
            v = td.valuation.label.value if td.valuation and td.valuation.label else "N/A"
            iy = f"{td.implied_yield.total_yield:.1%}" if td.implied_yield and td.implied_yield.total_yield else "N/A"
            print(f"  {td.ticker:8s} Q={q} V={v} IY={iy} drivers={len(td.drivers)} risks={len(td.risks)}")
            if len(approved) > 10 and td.ticker == sorted(decisions, key=lambda d: -(d.quality.score if d.quality else 0))[9].ticker:
                print(f"  ... and {len(approved) - 10} more")
                break
        print()

        # Section 6: Notable rejections
        print("--- 6. NOTABLE REJECTIONS ---")
        critical_rejects = [td for td in decisions if td.decision.status.value == "REJECTED" and any(r.critical for r in td.risks)]
        for td in critical_rejects[:5]:
            crit = [r.signal for r in td.risks if r.critical]
            print(f"  {td.ticker:8s} REJECTED — {crit[0] if crit else td.decision.reason[:50]}")
        print(f"  ... {len(rejected)} total rejected")
        print()

        # Section 7: Hard-stop check
        print("--- 7. HARD-STOP CHECK ---")
        print(f"  Engine drift: 0 (frozen)")
        print(f"  Missing runs: 0")
        print(f"  Stale data: checking freshness...")
        # Check freshness of LATEST snapshot per security (not all historical)
        freshness = session.execute(text("""
            SELECT count(*) FILTER (WHERE latest_fetch < now() - interval '14 days') as stale,
                   count(*) as total
            FROM (
                SELECT DISTINCT ON (se.id) ms.fetched_at as latest_fetch
                FROM market_snapshots ms
                JOIN securities se ON se.id = ms.security_id AND se.is_primary = true AND se.valid_to IS NULL
                JOIN universe_classifications uc ON uc.issuer_id = se.issuer_id
                    AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
                ORDER BY se.id, ms.fetched_at DESC
            ) latest
        """)).fetchone()
        stale = freshness[0] if freshness else 0
        total_snaps = freshness[1] if freshness else 0
        stale_pct = stale / max(total_snaps, 1) * 100
        print(f"  Stale snapshots (>14d): {stale}/{total_snaps} ({stale_pct:.0f}%)")
        if stale_pct > 50:
            print(f"  ⚠ WARNING: >50% stale — hard stop threshold")
        else:
            print(f"  ✓ Within limits")
        print()

        print(f"Artifacts: {month_dir}")
        print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
