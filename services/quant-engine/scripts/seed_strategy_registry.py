"""Seed strategy_status_registry with empirical validation verdicts.

Usage:
    cd services/quant-engine
    source .venv/bin/activate
    python scripts/seed_strategy_registry.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from q3_quant_engine.db.session import SessionLocal
from q3_shared_models.entities import StrategyStatusRegistry

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("seed_registry")


def _fingerprint(config: dict) -> str:
    canonical = json.dumps({
        "strategy_type": config["strategy_type"],
        "top_n": config["top_n"],
        "rebalance_freq": config["rebalance_freq"],
        "cost_model_proportional": config["cost_model"]["proportional"],
        "cost_model_slippage": config["cost_model"]["slippage_bps"],
        "equal_weight": config["equal_weight"],
        "universe_policy_version": config.get("universe_policy_version", "v1"),
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


COST_BRAZIL_REALISTIC = {"fixed": 0.0, "proportional": 0.0005, "slippage_bps": 10.0}

ENTRIES = [
    {
        "strategy_key": "ctrl_original_20m",
        "strategy_type": "magic_formula_original",
        "role": "CONTROL",
        "promotion_status": "REJECTED",
        "config": {
            "strategy_type": "magic_formula_original",
            "top_n": 20,
            "rebalance_freq": "monthly",
            "execution_lag_days": 1,
            "equal_weight": True,
            "cost_model": COST_BRAZIL_REALISTIC,
            "initial_capital": 1_000_000,
            "benchmark": "^BVSP",
            "universe_policy_version": "v1",
        },
        "evidence_summary": (
            "Walk-forward v2: worst OOS performer across 3 annual splits (2022/2023/2024). "
            "Avg OOS Sharpe 0.09. Avg OOS CAGR 2.84%. Negative OOS in 2024 (Sharpe -0.76). "
            "Frozen as rejected control baseline."
        ),
        "experiment_ids": ["2ac6848485f05b20"],
        "is_sharpe_avg": 0.49,
        "oos_sharpe_avg": 0.09,
        "promotion_checks": {
            "pit_validated": {"result": "PASS", "observed": True, "threshold": True, "note": "publication_date PIT"},
            "oos_real": {"result": "FAIL", "observed": 0.09, "threshold": 0.3, "note": "avg OOS Sharpe below threshold"},
            "real_costs": {"result": "PASS", "observed": "BRAZIL_REALISTIC", "threshold": "any", "note": ""},
            "dsr_threshold": {"result": "FAIL", "observed": 0.0, "threshold": 0.5, "note": "DSR effectively zero"},
            "sensitivity_stable": {"result": "FAIL", "observed": "rejected_control", "threshold": "n/a", "note": "not evaluated as control"},
            "manifest_valid": {"result": "PASS", "observed": True, "threshold": True, "note": ""},
        },
    },
    {
        "strategy_key": "ctrl_brazil_20m",
        "strategy_type": "magic_formula_brazil",
        "role": "CONTROL",
        "promotion_status": "REJECTED",
        "config": {
            "strategy_type": "magic_formula_brazil",
            "top_n": 20,
            "rebalance_freq": "monthly",
            "execution_lag_days": 1,
            "equal_weight": True,
            "cost_model": COST_BRAZIL_REALISTIC,
            "initial_capital": 1_000_000,
            "benchmark": "^BVSP",
            "universe_policy_version": "v1",
        },
        "evidence_summary": (
            "Walk-forward v2: gates worsened OOS vs Original in all splits. "
            "Avg OOS Sharpe 0.01. Avg OOS CAGR 2.15%. Gates cost R$44K (counterfactual). "
            "Frozen as rejected control."
        ),
        "experiment_ids": ["2ac6848485f05b20"],
        "is_sharpe_avg": 0.53,
        "oos_sharpe_avg": 0.01,
        "promotion_checks": {
            "pit_validated": {"result": "PASS", "observed": True, "threshold": True, "note": ""},
            "oos_real": {"result": "FAIL", "observed": 0.01, "threshold": 0.3, "note": "avg OOS Sharpe near zero"},
            "real_costs": {"result": "PASS", "observed": "BRAZIL_REALISTIC", "threshold": "any", "note": ""},
            "dsr_threshold": {"result": "FAIL", "observed": 0.0003, "threshold": 0.5, "note": ""},
            "sensitivity_stable": {"result": "FAIL", "observed": "rejected_control", "threshold": "n/a", "note": ""},
            "manifest_valid": {"result": "PASS", "observed": True, "threshold": True, "note": ""},
        },
    },
    {
        "strategy_key": "hybrid_20q",
        "strategy_type": "magic_formula_hybrid",
        "role": "FRONTRUNNER",
        "promotion_status": "BLOCKED",
        "config": {
            "strategy_type": "magic_formula_hybrid",
            "top_n": 20,
            "rebalance_freq": "quarterly",
            "execution_lag_days": 1,
            "equal_weight": True,
            "cost_model": COST_BRAZIL_REALISTIC,
            "initial_capital": 1_000_000,
            "benchmark": "^BVSP",
            "universe_policy_version": "v1",
        },
        "evidence_summary": (
            "Walk-forward v2: 3/3 wins vs controls, 3/3 OOS Sharpe positive. "
            "Avg OOS Sharpe 1.20. Avg OOS CAGR 11.48%. Avg excess return +12.67% vs Ibovespa. "
            "Blocked by sensitivity: high OOS Sharpe dispersion (0.04 to 2.77 across splits). "
            "Research frontrunner — strongest candidate but not yet promotable."
        ),
        "experiment_ids": ["2ac6848485f05b20"],
        "is_sharpe_avg": 1.08,
        "oos_sharpe_avg": 1.20,
        "promotion_checks": {
            "pit_validated": {"result": "PASS", "observed": True, "threshold": True, "note": "publication_date PIT throughout"},
            "oos_real": {"result": "PASS", "observed": 1.2048, "threshold": 0.3, "note": "avg OOS Sharpe across 3 annual splits"},
            "real_costs": {"result": "PASS", "observed": "BRAZIL_REALISTIC", "threshold": "any", "note": "5bps + 10bps slippage"},
            "dsr_threshold": {"result": "PASS", "observed": 1.0, "threshold": 0.5, "note": "best split DSR (2023)"},
            "sensitivity_stable": {"result": "FAIL", "observed": "sharpe_range_0.04_to_2.77", "threshold": "dispersion_lt_100pct", "note": "high OOS Sharpe dispersion across splits"},
            "manifest_valid": {"result": "PASS", "observed": True, "threshold": True, "note": "experiment artifacts reproducible"},
        },
    },
]


def main():
    with SessionLocal() as session:
        for entry in ENTRIES:
            config = entry["config"]
            fp = _fingerprint(config)

            # Check if already exists
            existing = session.execute(
                text("SELECT id FROM strategy_status_registry WHERE strategy_fingerprint = :fp AND superseded_at IS NULL"),
                {"fp": fp},
            ).fetchone()

            if existing:
                logger.info("Already exists: %s (fingerprint=%s)", entry["strategy_key"], fp)
                continue

            row = StrategyStatusRegistry(
                id=uuid.uuid4(),
                strategy_key=entry["strategy_key"],
                strategy_fingerprint=fp,
                strategy_type=entry["strategy_type"],
                role=entry["role"],
                promotion_status=entry["promotion_status"],
                config_json=config,
                evidence_summary=entry["evidence_summary"],
                experiment_ids=entry["experiment_ids"],
                is_sharpe_avg=entry["is_sharpe_avg"],
                oos_sharpe_avg=entry["oos_sharpe_avg"],
                promotion_checks=entry["promotion_checks"],
                decided_by="TECH_LEAD_REVIEW",
            )
            session.add(row)
            logger.info("Seeded: %s  role=%s  promotion=%s  fingerprint=%s",
                        entry["strategy_key"], entry["role"], entry["promotion_status"], fp)

        session.commit()

        # Verify
        rows = session.execute(text("""
            SELECT strategy_key, role, promotion_status, strategy_fingerprint, oos_sharpe_avg
            FROM strategy_status_registry
            WHERE superseded_at IS NULL
            ORDER BY strategy_key
        """)).fetchall()

        print(f"\n{'=' * 70}")
        print("STRATEGY STATUS REGISTRY")
        print(f"{'=' * 70}")
        for key, role, status, fp, sharpe in rows:
            print(f"  {key:20s}  role={role:14s}  status={status:14s}  OOS Sharpe={float(sharpe) if sharpe else 0:.4f}  fp={fp}")
        print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
