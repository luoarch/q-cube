"""Backtest artifact persistence — save results for reproducibility.

Persists:
- Constituents per rebalance (which tickers were held)
- Portfolio returns series
- Trade log
- Metrics summary
- Research manifest

Reference: docs/research-validation-protocol.md, Section 12.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

from q3_quant_engine.backtest.engine import BacktestResult
from q3_quant_engine.backtest.manifest import ResearchManifest
from q3_quant_engine.backtest.metrics import compute_returns


RESULTS_DIR = os.getenv(
    "Q3_RESULTS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "results"),
)


class _DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def persist_backtest(
    result: BacktestResult,
    manifest: ResearchManifest,
    output_dir: str | None = None,
) -> str:
    """Persist all backtest artifacts to a directory.

    Creates a directory named by experiment_id containing:
    - manifest.json
    - metrics.json
    - equity_curve.json
    - returns.json
    - trades.json
    - constituents.json (holdings per rebalance)

    Returns the output directory path.
    """
    base_dir = output_dir or RESULTS_DIR
    experiment_dir = os.path.join(base_dir, manifest.experiment_id)
    os.makedirs(experiment_dir, exist_ok=True)

    # 1. Manifest
    _write_json(os.path.join(experiment_dir, "manifest.json"), manifest.to_dict())

    # 2. Metrics
    _write_json(os.path.join(experiment_dir, "metrics.json"), result.metrics)

    # 3. Equity curve
    _write_json(os.path.join(experiment_dir, "equity_curve.json"), result.equity_curve)

    # 4. Returns
    returns = compute_returns(result.equity_curve)
    returns_data = []
    for i, r in enumerate(returns):
        d = result.equity_curve[i + 1]["date"]
        returns_data.append({"date": d, "return": round(r, 8)})
    _write_json(os.path.join(experiment_dir, "returns.json"), returns_data)

    # 5. Trades
    _write_json(os.path.join(experiment_dir, "trades.json"), result.trades)

    # 6. Constituents per rebalance
    _write_json(os.path.join(experiment_dir, "constituents.json"), result.holdings_history)

    return experiment_dir


def _write_json(path: str, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, cls=_DateEncoder)
