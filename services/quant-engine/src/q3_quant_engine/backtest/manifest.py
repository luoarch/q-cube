"""Research manifest for experiment reproducibility.

Every experiment must persist a manifest capturing all parameters,
data provenance, and code version so it can be reproduced exactly.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone

from q3_quant_engine.backtest.engine import BacktestConfig


@dataclass
class ResearchManifest:
    """Immutable record of a research experiment."""

    # Identity
    strategy: str
    variant: str  # e.g. "base", "no_quality", "top30"
    experiment_id: str = ""  # generated hash

    # Temporal
    start_date: str = ""
    end_date: str = ""
    split: str = ""  # "full" | "is" | "oos" | "walk_forward"

    # Universe
    universe_rules: dict = field(default_factory=dict)

    # Costs
    cost_model: dict = field(default_factory=dict)

    # Parameters
    parameters: dict = field(default_factory=dict)

    # Provenance
    commit_hash: str = ""
    formula_version: int = 1
    created_at: str = ""

    # Results summary
    n_trials: int = 1  # total variants tested in this family
    metrics_summary: dict = field(default_factory=dict)

    # Statistical
    statistical_metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def content_hash(self) -> str:
        """Deterministic hash of experiment parameters (excludes results)."""
        hashable = {
            "strategy": self.strategy,
            "variant": self.variant,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "split": self.split,
            "universe_rules": self.universe_rules,
            "cost_model": self.cost_model,
            "parameters": self.parameters,
            "formula_version": self.formula_version,
        }
        blob = json.dumps(hashable, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _get_git_hash() -> str:
    """Get current git commit hash, or 'unknown' if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def build_manifest(
    config: BacktestConfig,
    variant: str = "base",
    split: str = "full",
    n_trials: int = 1,
    metrics_summary: dict | None = None,
    statistical_metrics: dict | None = None,
) -> ResearchManifest:
    """Build a manifest from a backtest config and results."""
    manifest = ResearchManifest(
        strategy=config.strategy_type,
        variant=variant,
        start_date=str(config.start_date),
        end_date=str(config.end_date),
        split=split,
        universe_rules={
            "top_n": config.top_n,
            "equal_weight": config.equal_weight,
            "rebalance_freq": config.rebalance_freq,
            "execution_lag_days": config.execution_lag_days,
        },
        cost_model={
            "fixed_cost_per_trade": config.cost_model.fixed_cost_per_trade,
            "proportional_cost": config.cost_model.proportional_cost,
            "slippage_bps": config.cost_model.slippage_bps,
        },
        parameters={
            "strategy_type": config.strategy_type,
            "initial_capital": config.initial_capital,
            "benchmark": config.benchmark,
        },
        commit_hash=_get_git_hash(),
        formula_version=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        n_trials=n_trials,
        metrics_summary=metrics_summary or {},
        statistical_metrics=statistical_metrics or {},
    )
    manifest.experiment_id = manifest.content_hash()
    return manifest
