"""Backtest persistence tests."""

from __future__ import annotations

import json
import os
import tempfile

from q3_quant_engine.backtest.persistence import persist_backtest, _DateEncoder
from q3_quant_engine.backtest.engine import BacktestConfig, BacktestResult
from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC
from q3_quant_engine.backtest.manifest import ResearchManifest
from datetime import date


def _make_result() -> BacktestResult:
    config = BacktestConfig(
        strategy_type="magic_formula_brazil",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        cost_model=BRAZIL_REALISTIC,
    )
    return BacktestResult(
        config=config,
        equity_curve=[
            {"date": date(2024, 1, 1), "value": 1000000},
            {"date": date(2024, 4, 1), "value": 1050000},
            {"date": date(2024, 7, 1), "value": 1100000},
            {"date": date(2024, 10, 1), "value": 1080000},
        ],
        trades=[
            {"date": date(2024, 1, 2), "ticker": "WEGE3", "shares": 100, "price": 55.0, "cost": 8.25, "side": "buy"},
        ],
        holdings_history=[
            {"date": date(2024, 1, 1), "holdings": [{"ticker": "WEGE3", "weight": 0.05, "value": 50000}]},
        ],
        metrics={"sharpe": 1.5, "cagr": 0.12, "max_drawdown": 0.05},
        rebalance_dates=[date(2024, 1, 1), date(2024, 4, 1), date(2024, 7, 1), date(2024, 10, 1)],
    )


def _make_manifest() -> ResearchManifest:
    return ResearchManifest(
        strategy="magic_formula_brazil",
        variant="base",
        experiment_id="test_abc123",
        start_date="2024-01-01",
        end_date="2024-12-31",
        split="full",
        commit_hash="abc123",
        formula_version=1,
        created_at="2024-01-01T00:00:00Z",
        n_trials=1,
    )


def test_persist_creates_all_files():
    """Persistence creates all expected artifact files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _make_result()
        manifest = _make_manifest()
        out_dir = persist_backtest(result, manifest, output_dir=tmpdir)

        assert os.path.isdir(out_dir)
        expected_files = ["manifest.json", "metrics.json", "equity_curve.json",
                         "returns.json", "trades.json", "constituents.json"]
        for f in expected_files:
            assert os.path.exists(os.path.join(out_dir, f)), f"Missing {f}"


def test_persist_metrics_readable():
    """Persisted metrics can be read back as valid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _make_result()
        manifest = _make_manifest()
        out_dir = persist_backtest(result, manifest, output_dir=tmpdir)

        with open(os.path.join(out_dir, "metrics.json")) as f:
            metrics = json.load(f)
        assert metrics["sharpe"] == 1.5
        assert metrics["cagr"] == 0.12


def test_persist_returns_count():
    """Persisted returns have correct count (equity_curve - 1)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _make_result()
        manifest = _make_manifest()
        out_dir = persist_backtest(result, manifest, output_dir=tmpdir)

        with open(os.path.join(out_dir, "returns.json")) as f:
            returns = json.load(f)
        # 4 equity points -> 3 returns
        assert len(returns) == 3


def test_persist_manifest_has_experiment_id():
    """Persisted manifest contains the experiment ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _make_result()
        manifest = _make_manifest()
        out_dir = persist_backtest(result, manifest, output_dir=tmpdir)

        with open(os.path.join(out_dir, "manifest.json")) as f:
            m = json.load(f)
        assert m["experiment_id"] == "test_abc123"
