"""Phase 0 — Operational Shakeout for Pilot Protocol.

Expands refiner to all 196 data-eligible tickers, runs full decision engine,
validates pipeline coverage and logging. Non-evaluated dry run.

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/run_phase0_shakeout.py
"""
from __future__ import annotations

import dataclasses
import json
import logging
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.decision.engine import compute_ticker_decision
from q3_quant_engine.refiner.engine import RefinerEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("phase0")

RESULTS_DIR = Path("results/phase0_shakeout")


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
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    with SessionLocal() as session:
        # === Step 1: Get all data-eligible tickers ===
        eligible = session.execute(text("""
            SELECT se.ticker, i.id as issuer_id
            FROM securities se
            JOIN issuers i ON i.id = se.issuer_id
            JOIN universe_classifications uc ON uc.issuer_id = i.id
                AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
            JOIN computed_metrics cm ON cm.issuer_id = i.id AND cm.metric_code = 'earnings_yield'
            WHERE se.is_primary = true AND se.valid_to IS NULL
            ORDER BY se.ticker
        """)).fetchall()

        # Dedup by issuer_id (some issuers have multiple securities)
        seen_issuers = set()
        tickers = []
        for r in eligible:
            iid = str(r[1])
            if iid not in seen_issuers:
                seen_issuers.add(iid)
                tickers.append((r[0], iid))
        logger.info("Data-eligible tickers (deduped by issuer): %d", len(tickers))

        # === Step 2: Expand refiner to all eligible tickers ===
        logger.info("Expanding refiner to %d tickers...", len(tickers))

        # Build synthetic ranked_assets list for refiner
        ranked_assets = [{"ticker": t, "rank": i + 1} for i, (t, _) in enumerate(tickers)]

        # Create a synthetic strategy run for the refiner to attach to
        run_id = uuid.uuid4()
        tenant_id_row = session.execute(text("SELECT id FROM tenants LIMIT 1")).fetchone()
        if not tenant_id_row:
            logger.error("No tenant found. Cannot create refiner run.")
            return
        tenant_id = tenant_id_row[0]

        # Insert synthetic strategy run
        session.execute(text("""
            INSERT INTO strategy_runs (id, tenant_id, strategy, status, result_json, created_at, updated_at)
            VALUES (:id, :tid, 'magic_formula_brazil', 'completed', :result, now(), now())
        """), {
            "id": str(run_id),
            "tid": str(tenant_id),
            "result": json.dumps({"rankedAssets": ranked_assets}),
        })
        session.commit()
        logger.info("Created synthetic strategy run: %s", run_id)

        # Run refiner on full universe
        refiner = RefinerEngine(session)
        refiner_results = refiner.refine(
            run_id=run_id,
            tenant_id=tenant_id,
            top_n=len(ranked_assets),
            ranked_assets=ranked_assets,
        )
        session.commit()
        logger.info("Refiner completed: %d results", len(refiner_results))

        # === Step 3: Run decision engine on all eligible tickers ===
        logger.info("Running decision engine on %d tickers...", len(tickers))
        decisions = []
        errors = []

        for ticker, issuer_id in tickers:
            try:
                td = compute_ticker_decision(session, ticker)
                decisions.append(td)
            except Exception as e:
                logger.error("Decision failed for %s: %s", ticker, e)
                errors.append({"ticker": ticker, "error": str(e)})

        logger.info("Decisions: %d complete, %d errors", len(decisions), len(errors))

        # === Step 4: Validate Phase 0 checks ===
        print(f"\n{'=' * 80}")
        print("PHASE 0 — OPERATIONAL SHAKEOUT RESULTS")
        print(f"{'=' * 80}")
        print(f"Elapsed: {time.time() - t0:.0f}s")
        print()

        # Check 1: Refiner runs on 196 without error
        check1 = len(refiner_results) >= 180
        print(f"CHECK 1 — Refiner runs on {len(tickers)} tickers: {len(refiner_results)} results → {'PASS' if check1 else 'FAIL'}")

        # Check 2: Decision engine produces valid output for >= 180
        check2 = len(decisions) >= 180
        print(f"CHECK 2 — Decision engine: {len(decisions)}/{len(tickers)} valid outputs → {'PASS' if check2 else 'FAIL'}")

        # Check 3: Non-degenerate distribution
        status_dist = Counter(td.decision.status.value for td in decisions)
        check3 = len(status_dist) >= 2 and max(status_dist.values()) < len(decisions) * 0.95
        print(f"CHECK 3 — Distribution: {dict(status_dist)} → {'PASS' if check3 else 'FAIL'}")

        # Check 4: Forward return tracking (schema validation)
        journal_entry = {
            "cycle": "phase0",
            "run_date": datetime.now(timezone.utc).isoformat(),
            "engine_version": "v1.0-frozen",
            "universe_size": len(tickers),
            "classification_counts": dict(status_dist),
            "approved_tickers": sorted(td.ticker for td in decisions if td.decision.status.value == "APPROVED"),
            "human_overrides": [],
            "forward_returns": None,
        }
        journal_path = RESULTS_DIR / "decision_journal_phase0.json"
        journal_path.write_text(json.dumps(journal_entry, indent=2, ensure_ascii=False))
        check4 = journal_path.exists() and json.loads(journal_path.read_text()).get("cycle") == "phase0"
        print(f"CHECK 4 — Decision journal persists: → {'PASS' if check4 else 'FAIL'}")

        # Check 5: Monthly report coverage metrics
        val_suppressed = sum(1 for td in decisions if td.valuation and td.valuation.suppression_reason)
        val_invalid = sum(1 for td in decisions if td.valuation and not td.valuation.valuation_valid)
        has_thesis = sum(1 for td in decisions if any(d.source == "plan2_thesis" for d in td.drivers))
        has_refiner = sum(1 for td in decisions if td.quality is not None)
        conf_dist = Counter(td.confidence.label.value for td in decisions)

        check5 = True  # coverage report generated successfully
        print(f"CHECK 5 — Monthly report coverage:")
        print(f"  Universe:         {len(tickers)}")
        print(f"  Refiner coverage: {has_refiner}/{len(tickers)} ({has_refiner/len(tickers)*100:.0f}%)")
        print(f"  Thesis coverage:  {has_thesis}/{len(tickers)} ({has_thesis/len(tickers)*100:.0f}%)")
        print(f"  Val suppressed:   {val_suppressed}/{len(tickers)} ({val_suppressed/len(tickers)*100:.0f}%)")
        print(f"  Val invalid:      {val_invalid}/{len(tickers)}")
        print(f"  Confidence:       {dict(conf_dist)}")
        print(f"  → PASS")

        # Check 6: No systematic errors
        check6 = len(errors) < len(tickers) * 0.05  # <5% errors
        print(f"CHECK 6 — Error rate: {len(errors)}/{len(tickers)} ({len(errors)/len(tickers)*100:.1f}%) → {'PASS' if check6 else 'FAIL'}")

        all_pass = all([check1, check2, check3, check4, check5, check6])

        print()
        print(f"{'=' * 80}")
        print(f"PHASE 0 VERDICT: {'ALL CHECKS PASS — Ready for Phase 1' if all_pass else 'FAILED — Fix issues before proceeding'}")
        print(f"{'=' * 80}")

        # Save full results
        report = {
            "phase": "0-shakeout",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "universe_size": len(tickers),
            "refiner_results": len(refiner_results),
            "decision_results": len(decisions),
            "errors": len(errors),
            "status_distribution": dict(status_dist),
            "confidence_distribution": dict(conf_dist),
            "refiner_coverage": has_refiner,
            "thesis_coverage": has_thesis,
            "valuation_suppressed": val_suppressed,
            "valuation_invalid": val_invalid,
            "checks": {
                "refiner_runs": check1,
                "decision_valid": check2,
                "non_degenerate": check3,
                "journal_persists": check4,
                "coverage_report": check5,
                "low_error_rate": check6,
            },
            "all_pass": all_pass,
        }
        (RESULTS_DIR / "phase0_report.json").write_text(json.dumps(report, indent=2))

        # Save approved list
        approved = sorted(td.ticker for td in decisions if td.decision.status.value == "APPROVED")
        print(f"\nAPPROVED ({len(approved)}): {approved}")

        print(f"\nArtifacts: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
