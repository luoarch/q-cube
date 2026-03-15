"""Run Plan 2 pipeline against real data and produce Validation Report v1.

Usage:
    source .venv/bin/activate
    python scripts/run_plan2_validation.py
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from dataclasses import asdict
from datetime import date

from sqlalchemy import select, text

from q3_quant_engine.db.session import SessionLocal, engine
from q3_shared_models.entities import Issuer, Security

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("plan2_validation")


def _build_universe(session):
    """Build issuer universe from the latest completed strategy run."""
    # Get latest completed strategy run
    row = session.execute(
        text("SELECT id, result_json FROM strategy_runs WHERE status = 'completed' ORDER BY created_at DESC LIMIT 1")
    ).fetchone()
    if not row:
        logger.error("No completed strategy run found")
        sys.exit(1)

    strategy_run_id = row[0]
    ranked_assets = row[1]["rankedAssets"]
    total_ranked = len(ranked_assets)
    logger.info("Strategy run %s: %d ranked assets", strategy_run_id, total_ranked)

    # Build ticker -> rank mapping
    ticker_rank = {a["ticker"]: a["rank"] for a in ranked_assets}
    tickers = list(ticker_rank.keys())

    # Load issuers by ticker (via securities table)
    securities = session.execute(
        select(Security).where(Security.ticker.in_(tickers))
    ).scalars().all()

    # Deduplicate: one issuer per ticker
    ticker_to_issuer_id: dict[str, uuid.UUID] = {}
    for sec in securities:
        if sec.ticker not in ticker_to_issuer_id:
            ticker_to_issuer_id[sec.ticker] = sec.issuer_id

    issuer_ids = list(set(ticker_to_issuer_id.values()))
    issuers = session.execute(
        select(Issuer).where(Issuer.id.in_(issuer_ids))
    ).scalars().all()
    issuer_map = {i.id: i for i in issuers}

    # Build universe: (Issuer, core_rank_percentile, has_valid_financials)
    # Also build ticker map for later resolution
    universe = []
    issuer_id_to_ticker: dict[str, str] = {}
    for ticker, rank in ticker_rank.items():
        issuer_id = ticker_to_issuer_id.get(ticker)
        if issuer_id is None:
            continue
        issuer = issuer_map.get(issuer_id)
        if issuer is None:
            continue

        # core_rank_percentile: top rank = high percentile
        core_rank_pct = round((1.0 - (rank - 1) / total_ranked) * 100, 2)
        # All ranked assets passed core screening, assume valid financials
        universe.append((issuer, core_rank_pct, True))
        issuer_id_to_ticker[str(issuer_id)] = ticker

    logger.info("Universe built: %d issuers (from %d tickers)", len(universe), len(tickers))
    return strategy_run_id, universe, issuer_id_to_ticker


def _run_pipeline(session, strategy_run_id, universe):
    """Execute the plan2 pipeline."""
    from q3_quant_engine.thesis.pipeline import run_plan2_pipeline

    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    plan2_run = run_plan2_pipeline(
        session=session,
        strategy_run_id=strategy_run_id,
        tenant_id=tenant_id,
        issuer_universe=universe,
        as_of_date=date.today(),
    )
    session.commit()
    logger.info(
        "Plan2 run %s completed: eligible=%d ineligible=%d",
        plan2_run.id, plan2_run.total_eligible, plan2_run.total_ineligible,
    )
    return plan2_run


def _build_issuer_ticker_map(session):
    """Build issuer_id -> primary ticker map from securities table."""
    rows = session.execute(
        select(Security.issuer_id, Security.ticker)
        .where(Security.is_primary == True)
    ).all()
    return {str(r[0]): r[1] for r in rows}


def _build_issuer_sector_map(session):
    """Build issuer_id -> sector map, using strategy run result_json as fallback.

    The issuers table currently has sector='None' for all rows.
    The strategy run result_json has sector from CVM classification.
    """
    # Fallback: use strategy run ranked assets (which have sector from CVM)
    row = session.execute(
        text("SELECT result_json FROM strategy_runs WHERE status = 'completed' ORDER BY created_at DESC LIMIT 1")
    ).fetchone()
    if not row:
        return {}

    ticker_to_sector = {a["ticker"]: a.get("sector") for a in row[0]["rankedAssets"]}

    # Map ticker -> issuer_id
    secs = session.execute(
        select(Security.issuer_id, Security.ticker).where(Security.is_primary == True)
    ).all()
    ticker_to_issuer = {r[1]: str(r[0]) for r in secs}

    sector_map = {}
    for ticker, sector in ticker_to_sector.items():
        issuer_id = ticker_to_issuer.get(ticker)
        if issuer_id and sector and sector != "None":
            sector_map[issuer_id] = sector

    return sector_map


def _load_snapshots(session, plan2_run_id, ticker_map=None, sector_map=None):
    """Reconstruct Plan2RankingSnapshots from persisted data."""
    from q3_shared_models.entities import Plan2ThesisScore
    from q3_quant_engine.thesis.types import (
        BaseEligibility,
        FragilityVector,
        OpportunityVector,
        Plan2RankingSnapshot,
        ScoreProvenance,
        ThesisBucket,
    )
    if ticker_map is None:
        ticker_map = {}
    if sector_map is None:
        sector_map = {}

    scores = session.execute(
        select(Plan2ThesisScore)
        .where(Plan2ThesisScore.plan2_run_id == plan2_run_id)
    ).scalars().all()

    snapshots = []
    for s in scores:
        # Reconstruct eligibility
        elig_data = s.eligibility_json
        eligibility = BaseEligibility(
            eligible_for_plan2=elig_data.get("eligible_for_plan2", False),
            failed_reasons=elig_data.get("failed_reasons", []),
            passed_core_screening=elig_data.get("passed_core_screening", False),
            has_valid_financials=elig_data.get("has_valid_financials", False),
            interest_coverage=elig_data.get("interest_coverage"),
            debt_to_ebitda=elig_data.get("debt_to_ebitda"),
        )

        # Reconstruct provenance from feature_input_json
        provenance: dict[str, ScoreProvenance] = {}
        fi_json = s.feature_input_json or {}
        prov_raw = fi_json.get("provenance", {})
        for dim, pdata in prov_raw.items():
            provenance[dim] = ScoreProvenance(
                source_type=pdata.get("source_type", "DEFAULT"),
                source_version=pdata.get("source_version", "unknown"),
                assessed_at=pdata.get("assessed_at", ""),
                assessed_by=pdata.get("assessed_by"),
                confidence=pdata.get("confidence", "low"),
                evidence_ref=pdata.get("evidence_ref"),
            )

        # Get ticker — prefer ticker_map (B3 ticker), fallback to stored data
        input_data = fi_json.get("input", fi_json.get("draft", {}))
        issuer_id_str = str(s.issuer_id)
        ticker = ticker_map.get(issuer_id_str) or input_data.get("ticker", issuer_id_str[:8])

        # Reconstruct vectors
        opp = None
        frag = None
        bucket = None

        if s.eligible and s.final_commodity_affinity_score is not None:
            opp = OpportunityVector(
                direct_commodity_exposure_score=float(s.direct_commodity_exposure_score or 0),
                indirect_commodity_exposure_score=float(s.indirect_commodity_exposure_score or 0),
                export_fx_leverage_score=float(s.export_fx_leverage_score or 0),
                final_commodity_affinity_score=float(s.final_commodity_affinity_score or 0),
            )
            frag = FragilityVector(
                refinancing_stress_score=float(s.refinancing_stress_score or 0),
                usd_debt_exposure_score=float(s.usd_debt_exposure_score or 0),
                usd_import_dependence_score=float(s.usd_import_dependence_score or 0),
                usd_revenue_offset_score=float(s.usd_revenue_offset_score or 0),
                final_dollar_fragility_score=float(s.final_dollar_fragility_score or 0),
            )
            if s.bucket:
                bucket = ThesisBucket(s.bucket)

        snap = Plan2RankingSnapshot(
            issuer_id=issuer_id_str,
            ticker=ticker,
            company_name=input_data.get("company_name", ""),
            sector=sector_map.get(issuer_id_str) or input_data.get("sector"),
            eligible=s.eligible,
            eligibility=eligibility,
            opportunity_vector=opp,
            fragility_vector=frag,
            bucket=bucket,
            thesis_rank_score=float(s.thesis_rank_score) if s.thesis_rank_score is not None else None,
            thesis_rank=s.thesis_rank,
            base_core_score=float(input_data.get("core_rank_percentile", 0)),
            provenance=provenance,
        )
        snapshots.append(snap)

    # Sort by thesis_rank
    snapshots.sort(key=lambda x: x.thesis_rank if x.thesis_rank is not None else 9999)
    return snapshots


def _load_feature_inputs(session, plan2_run_id, ticker_map=None):
    """Load Plan2FeatureInput records for sensitivity analysis."""
    from q3_shared_models.entities import Plan2ThesisScore
    from q3_quant_engine.thesis.types import Plan2FeatureInput

    if ticker_map is None:
        ticker_map = {}

    scores = session.execute(
        select(Plan2ThesisScore)
        .where(Plan2ThesisScore.plan2_run_id == plan2_run_id, Plan2ThesisScore.eligible == True)
    ).scalars().all()

    inputs = []
    for s in scores:
        fi = s.feature_input_json or {}
        inp_data = fi.get("input", {})
        if not inp_data:
            continue

        issuer_id_str = str(s.issuer_id)
        inputs.append(Plan2FeatureInput(
            issuer_id=inp_data.get("issuer_id", issuer_id_str),
            ticker=ticker_map.get(issuer_id_str) or inp_data.get("ticker", ""),
            passed_core_screening=inp_data.get("passed_core_screening", True),
            has_valid_financials=inp_data.get("has_valid_financials", True),
            interest_coverage=inp_data.get("interest_coverage"),
            debt_to_ebitda=inp_data.get("debt_to_ebitda"),
            core_rank_percentile=float(inp_data.get("core_rank_percentile", 50)),
            direct_commodity_exposure_score=float(inp_data.get("direct_commodity_exposure_score", 10)),
            indirect_commodity_exposure_score=float(inp_data.get("indirect_commodity_exposure_score", 10)),
            export_fx_leverage_score=float(inp_data.get("export_fx_leverage_score", 6)),
            refinancing_stress_score=float(inp_data.get("refinancing_stress_score", 30)),
            usd_debt_exposure_score=float(inp_data.get("usd_debt_exposure_score", 30)),
            usd_import_dependence_score=float(inp_data.get("usd_import_dependence_score", 20)),
            usd_revenue_offset_score=float(inp_data.get("usd_revenue_offset_score", 10)),
            provenance={}  # not needed for sensitivity
        ))

    return inputs


def _run_validation(snapshots, feature_inputs, plan2_run):
    """Run all 5 validation blocks and return report dict."""
    from q3_quant_engine.thesis.validation.face_validity import check_face_validity, GOLDEN_SET
    from q3_quant_engine.thesis.validation.distribution import check_distribution_sanity
    from q3_quant_engine.thesis.validation.sensitivity import run_sensitivity_analysis
    from q3_quant_engine.thesis.validation.evidence_sanity import check_evidence_sanity

    report = {
        "plan2_run_id": str(plan2_run.id),
        "as_of_date": plan2_run.as_of_date.isoformat(),
        "pipeline_version": plan2_run.pipeline_version,
        "thesis_config_version": plan2_run.thesis_config_version,
        "total_eligible": plan2_run.total_eligible,
        "total_ineligible": plan2_run.total_ineligible,
        "bucket_distribution": plan2_run.bucket_distribution_json,
    }

    # === 1. BUCKET DISTRIBUTION ===
    eligible = [s for s in snapshots if s.eligible]
    report["bucket_breakdown"] = {}
    for s in eligible:
        b = s.bucket.value if s.bucket else "None"
        report["bucket_breakdown"][b] = report["bucket_breakdown"].get(b, 0) + 1

    # === 2. TOP 10 / TOP 20 ===
    ranked = [s for s in eligible if s.thesis_rank is not None]
    ranked.sort(key=lambda x: x.thesis_rank)

    top10 = []
    for s in ranked[:10]:
        top10.append({
            "rank": s.thesis_rank,
            "ticker": s.ticker,
            "bucket": s.bucket.value if s.bucket else None,
            "thesis_rank_score": round(s.thesis_rank_score, 2) if s.thesis_rank_score else None,
            "sector": s.sector,
        })
    report["top_10"] = top10

    top20 = []
    for s in ranked[:20]:
        top20.append({
            "rank": s.thesis_rank,
            "ticker": s.ticker,
            "bucket": s.bucket.value if s.bucket else None,
            "thesis_rank_score": round(s.thesis_rank_score, 2) if s.thesis_rank_score else None,
        })
    report["top_20"] = top20

    # === 3. EVIDENCE SANITY ===
    ev_top10 = check_evidence_sanity(snapshots, top_n=10)
    ev_top20 = check_evidence_sanity(snapshots, top_n=20)
    report["evidence_sanity"] = {
        "top_10": {
            "high": ev_top10.high_evidence_count,
            "mixed": ev_top10.mixed_evidence_count,
            "low": ev_top10.low_evidence_count,
            "low_pct": ev_top10.low_evidence_pct,
            "is_acceptable": ev_top10.is_acceptable,
        },
        "top_20": {
            "high": ev_top20.high_evidence_count,
            "mixed": ev_top20.mixed_evidence_count,
            "low": ev_top20.low_evidence_count,
            "low_pct": ev_top20.low_evidence_pct,
            "is_acceptable": ev_top20.is_acceptable,
        },
        "details_top10": ev_top10.details,
    }

    # === 4. DISTRIBUTION SANITY ===
    dist_alerts = check_distribution_sanity(snapshots)
    report["distribution_alerts"] = [
        {"severity": a.severity, "code": a.code, "message": a.message}
        for a in dist_alerts
    ]

    # === 5. FACE VALIDITY ===
    face = check_face_validity(snapshots)
    report["face_validity"] = {
        "total_cases": face.total_cases,
        "matched": face.matched,
        "mismatched": face.mismatched,
        "missing": face.missing,
        "pass_rate": face.pass_rate,
        "details": face.details,
    }

    # === 6. SENSITIVITY ANALYSIS ===
    if feature_inputs:
        sensitivity = run_sensitivity_analysis(feature_inputs, snapshots)
        report["sensitivity"] = [
            {
                "label": r.perturbation_label,
                "bucket_changes": r.bucket_changes,
                "bucket_change_pct": r.bucket_change_pct,
                "top10_changes": r.top10_changes,
                "top20_changes": r.top20_changes,
                "total_eligible": r.total_eligible,
            }
            for r in sensitivity
        ]

    # === 7. D_FRAGILE ANALYSIS ===
    fragile = [s for s in eligible if s.bucket and s.bucket.value == "D_FRAGILE"]
    report["d_fragile_analysis"] = {
        "count": len(fragile),
        "issuers": [
            {
                "ticker": s.ticker,
                "fragility_score": round(s.fragility_vector.final_dollar_fragility_score, 2) if s.fragility_vector else None,
                "sector": s.sector,
            }
            for s in fragile
        ],
        "diagnosis": (
            "Zero D_FRAGILE issuers. This is a known MVP limitation: "
            "with all-default scores (usd_debt=30, usd_import=20, refinancing=30), "
            "max fragility is ~34, far below the 75 threshold. "
            "D_FRAGILE requires real data or rubric-filled scores to activate."
            if len(fragile) == 0
            else f"{len(fragile)} D_FRAGILE issuers found."
        ),
    }

    # === 8. SUSPECT CASES ===
    suspects = []
    # Companies in commodity sectors that ended up C_NEUTRAL
    commodity_keywords = ["mineracao", "siderurgia", "petroleo", "celulose", "papel", "metalurgia"]
    for s in eligible:
        if s.bucket and s.bucket.value == "C_NEUTRAL" and s.sector:
            sector_lower = s.sector.lower()
            if any(kw in sector_lower for kw in commodity_keywords):
                suspects.append({
                    "ticker": s.ticker,
                    "sector": s.sector,
                    "bucket": "C_NEUTRAL",
                    "reason": "Commodity-sector company classified as NEUTRAL (likely needs sector proxy or rubric)",
                })
    # Banks/financials in A_DIRECT or B_INDIRECT
    finance_keywords = ["banco", "financeira", "seguro", "credito"]
    for s in eligible:
        if s.bucket and s.bucket.value in ("A_DIRECT", "B_INDIRECT") and s.sector:
            sector_lower = s.sector.lower()
            if any(kw in sector_lower for kw in finance_keywords):
                suspects.append({
                    "ticker": s.ticker,
                    "sector": s.sector,
                    "bucket": s.bucket.value,
                    "reason": "Financial company in commodity bucket (unexpected)",
                })
    report["suspect_cases"] = suspects

    return report


def _print_report(report):
    """Print formatted validation report."""
    print("\n" + "=" * 80)
    print("  PLAN 2 VALIDATION REPORT v1")
    print("=" * 80)

    print(f"\nRun ID:          {report['plan2_run_id']}")
    print(f"As-of date:      {report['as_of_date']}")
    print(f"Pipeline:        {report['pipeline_version']}")
    print(f"Config:          {report['thesis_config_version']}")
    print(f"Eligible:        {report['total_eligible']}")
    print(f"Ineligible:      {report['total_ineligible']}")

    # Bucket distribution
    print(f"\n--- BUCKET DISTRIBUTION ---")
    for bucket, count in sorted(report["bucket_breakdown"].items()):
        pct = count / report["total_eligible"] * 100 if report["total_eligible"] > 0 else 0
        print(f"  {bucket:12s}  {count:3d}  ({pct:5.1f}%)")

    # Top 10
    print(f"\n--- TOP 10 ---")
    print(f"  {'Rank':>4s}  {'Ticker':<8s}  {'Bucket':<12s}  {'Score':>7s}  Sector")
    for t in report["top_10"]:
        print(f"  {t['rank']:4d}  {t['ticker']:<8s}  {t['bucket'] or '-':<12s}  {t['thesis_rank_score'] or 0:7.2f}  {(t.get('sector') or '')[:50]}")

    # Top 20
    print(f"\n--- TOP 20 ---")
    print(f"  {'Rank':>4s}  {'Ticker':<8s}  {'Bucket':<12s}  {'Score':>7s}")
    for t in report["top_20"]:
        print(f"  {t['rank']:4d}  {t['ticker']:<8s}  {t['bucket'] or '-':<12s}  {t['thesis_rank_score'] or 0:7.2f}")

    # Evidence sanity
    ev = report["evidence_sanity"]
    print(f"\n--- EVIDENCE SANITY ---")
    print(f"  Top-10: HIGH={ev['top_10']['high']} MIXED={ev['top_10']['mixed']} LOW={ev['top_10']['low']} | LOW%={ev['top_10']['low_pct']:.0%} | acceptable={ev['top_10']['is_acceptable']}")
    print(f"  Top-20: HIGH={ev['top_20']['high']} MIXED={ev['top_20']['mixed']} LOW={ev['top_20']['low']} | LOW%={ev['top_20']['low_pct']:.0%} | acceptable={ev['top_20']['is_acceptable']}")

    print(f"\n  Top-10 detail:")
    for d in ev.get("details_top10", []):
        print(f"    #{d['thesis_rank']:>2s} {d['ticker']:<8s} {d['bucket']:<12s} evidence={d['evidence_quality']:<15s} quant={d['quantitative_pct']:>4s} default={d['default_pct']:>4s}")

    # Distribution alerts
    alerts = report["distribution_alerts"]
    print(f"\n--- DISTRIBUTION ALERTS ({len(alerts)}) ---")
    if not alerts:
        print("  (none)")
    for a in alerts:
        print(f"  [{a['severity']}] {a['code']}: {a['message']}")

    # Face validity
    fv = report["face_validity"]
    print(f"\n--- FACE VALIDITY ---")
    print(f"  Pass rate: {fv['pass_rate']:.0%} ({fv['matched']}/{fv['total_cases']} matched, {fv['mismatched']} mismatched, {fv['missing']} missing)")
    for d in fv["details"]:
        status_icon = {"MATCH": "+", "MISMATCH": "X", "MISSING": "?", "INELIGIBLE": "-"}.get(d["status"], " ")
        print(f"  [{status_icon}] {d['ticker']:<8s}  expected={d['expected_bucket']:<12s}  actual={d['actual_bucket']:<12s}  {d['status']}")

    # Sensitivity
    if "sensitivity" in report:
        print(f"\n--- SENSITIVITY ANALYSIS ---")
        print(f"  {'Scenario':<35s} {'BktChg':>6s} {'Chg%':>6s} {'T10':>4s} {'T20':>4s}")
        for s in report["sensitivity"]:
            print(f"  {s['label']:<35s} {s['bucket_changes']:6d} {s['bucket_change_pct']:5.1f}% {s['top10_changes']:4d} {s['top20_changes']:4d}")

    # D_FRAGILE
    df = report["d_fragile_analysis"]
    print(f"\n--- D_FRAGILE ANALYSIS ---")
    print(f"  Count: {df['count']}")
    print(f"  Diagnosis: {df['diagnosis']}")
    if df["issuers"]:
        for i in df["issuers"]:
            print(f"    {i['ticker']:<8s} fragility={i['fragility_score']}  sector={i['sector']}")

    # Suspect cases
    suspects = report["suspect_cases"]
    print(f"\n--- SUSPECT CASES ({len(suspects)}) ---")
    if not suspects:
        print("  (none)")
    for s in suspects:
        print(f"  {s['ticker']:<8s} bucket={s['bucket']:<12s} sector={s['sector'][:40]}")
        print(f"    reason: {s['reason']}")

    print("\n" + "=" * 80)
    print("  END OF REPORT")
    print("=" * 80)


def main():
    session = SessionLocal()
    try:
        # Check if a plan2_run already exists
        from q3_shared_models.entities import Plan2Run
        existing = session.execute(
            select(Plan2Run).order_by(Plan2Run.created_at.desc()).limit(1)
        ).scalar_one_or_none()

        # Build lookup maps from DB
        ticker_map = _build_issuer_ticker_map(session)
        sector_map = _build_issuer_sector_map(session)

        force_rerun = "--rerun" in sys.argv
        if existing and existing.status == "completed" and not force_rerun:
            logger.info("Using existing plan2 run %s (eligible=%d). Use --rerun to force new run.", existing.id, existing.total_eligible)
            plan2_run = existing
        else:
            # 1. Build universe
            logger.info("Building issuer universe from latest strategy run...")
            strategy_run_id, universe, _extra_tickers = _build_universe(session)

            # 2. Run pipeline
            logger.info("Running Plan 2 pipeline...")
            plan2_run = _run_pipeline(session, strategy_run_id, universe)

        # 3. Load snapshots back from DB
        logger.info("Loading snapshots from DB...")
        snapshots = _load_snapshots(session, plan2_run.id, ticker_map, sector_map)

        # 4. Load feature inputs for sensitivity
        logger.info("Loading feature inputs for sensitivity analysis...")
        feature_inputs = _load_feature_inputs(session, plan2_run.id, ticker_map)

        # 5. Run validation
        logger.info("Running validation blocks...")
        report = _run_validation(snapshots, feature_inputs, plan2_run)

        # 6. Print report
        _print_report(report)

        # 7. Save JSON
        report_path = "validation_report_v1.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("JSON report saved to %s", report_path)

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
