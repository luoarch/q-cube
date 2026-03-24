"""Run Ticker Decision Engine for Top N from latest ranking.

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/run_ticker_decisions.py
"""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

from sqlalchemy import text

from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.decision.engine import compute_ticker_decision
from q3_quant_engine.decision.types import TickerDecision

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ticker_decisions")

TOP_N = 10
RESULTS_DIR = Path("results/ticker_decisions")


def _to_dict(td: TickerDecision) -> dict:
    """Convert dataclass tree to JSON-serializable dict."""
    def _conv(obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {k: _conv(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list):
            return [_conv(i) for i in obj]
        if isinstance(obj, tuple):
            return list(obj)
        if hasattr(obj, 'value'):  # Enum
            return obj.value
        return obj
    return _conv(td)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session:
        # Get Top N tickers from compat view ranking
        rows = session.execute(text("""
            SELECT ticker FROM v_financial_statements_compat
            ORDER BY
                CASE WHEN ebit IS NOT NULL AND ebit > 0 THEN 0 ELSE 1 END,
                COALESCE(earnings_yield, 0) DESC
            LIMIT :n
        """), {"n": TOP_N}).fetchall()

        tickers = [r[0] for r in rows]
        logger.info("Top %d tickers: %s", TOP_N, tickers)

        decisions: list[dict] = []
        for ticker in tickers:
            logger.info("Computing decision for %s...", ticker)
            td = compute_ticker_decision(session, ticker)
            d = _to_dict(td)
            decisions.append(d)

            status = td.decision.status.value if hasattr(td.decision.status, 'value') else str(td.decision.status)
            quality = f"{td.quality.score:.2f}" if td.quality else "N/A"
            val = td.valuation.label.value if td.valuation and td.valuation.label and hasattr(td.valuation.label, 'value') else str(td.valuation.label) if td.valuation and td.valuation.label else "N/A"
            iy = f"{td.implied_yield.total_yield:.1%}" if td.implied_yield and td.implied_yield.total_yield else "N/A"
            conf = td.confidence.label.value if hasattr(td.confidence.label, 'value') else str(td.confidence.label)
            logger.info("  %s: status=%s quality=%s valuation=%s yield=%s confidence=%s",
                        ticker, status, quality, val, iy, conf)

    # Save
    (RESULTS_DIR / "decisions.json").write_text(json.dumps(decisions, indent=2, ensure_ascii=False))

    # Determinism check: run again and compare
    logger.info("Running determinism check...")
    with SessionLocal() as session:
        second_run = []
        for ticker in tickers:
            td = compute_ticker_decision(session, ticker)
            second_run.append(_to_dict(td))

    # Compare (excluding generated_at which has timestamps)
    deterministic = True
    for i, (d1, d2) in enumerate(zip(decisions, second_run)):
        d1_clean = {k: v for k, v in d1.items() if k != "generated_at"}
        d2_clean = {k: v for k, v in d2.items() if k != "generated_at"}
        if json.dumps(d1_clean, sort_keys=True) != json.dumps(d2_clean, sort_keys=True):
            logger.warning("DETERMINISM FAIL for %s", tickers[i])
            deterministic = False

    # Report
    print(f"\n{'=' * 80}")
    print("TICKER DECISION ENGINE — TOP 10 RESULTS")
    print(f"{'=' * 80}")
    print()

    status_counts = {"APPROVED": 0, "BLOCKED": 0, "REJECTED": 0}
    for d in decisions:
        s = d["decision"]["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

        ticker = d["ticker"]
        quality = f"{d['quality']['score']:.2f}" if d.get("quality") else "N/A"
        val_label = d["valuation"]["label"] if d.get("valuation") and d["valuation"].get("label") else "N/A"
        iy = f"{d['implied_yield']['total_yield']:.1%}" if d.get("implied_yield") and d["implied_yield"].get("total_yield") else "N/A"
        conf = d["confidence"]["label"]
        reason = d["decision"]["reason"][:60]
        drivers_count = len(d.get("drivers", []))
        risks_count = len(d.get("risks", []))

        print(f"  {ticker:8s}  {s:10s}  Q={quality:5s}  V={val_label:10s}  IY={iy:8s}  C={conf:6s}  D={drivers_count}  R={risks_count}")
        print(f"           {reason}")
        if d["decision"].get("block_reason"):
            print(f"           block: {d['decision']['block_reason']}")
        print()

    print(f"{'=' * 80}")
    print(f"Distribution: {status_counts}")
    print(f"Deterministic: {'YES' if deterministic else 'NO'}")
    print(f"Artifacts: {RESULTS_DIR}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
