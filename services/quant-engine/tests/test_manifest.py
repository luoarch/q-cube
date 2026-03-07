"""Research manifest reproducibility tests."""

from __future__ import annotations

import json
from datetime import date

from q3_quant_engine.backtest.costs import BRAZIL_REALISTIC
from q3_quant_engine.backtest.engine import BacktestConfig
from q3_quant_engine.backtest.manifest import ResearchManifest, build_manifest


def test_manifest_has_all_required_fields():
    """Manifest contains every field from the protocol."""
    config = BacktestConfig(
        strategy_type="magic_formula_brazil",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
    )
    manifest = build_manifest(config, variant="base", n_trials=5)
    d = manifest.to_dict()

    assert d["strategy"] == "magic_formula_brazil"
    assert d["variant"] == "base"
    assert d["start_date"] == "2020-01-01"
    assert d["end_date"] == "2024-12-31"
    assert d["split"] == "full"
    assert d["n_trials"] == 5
    assert "top_n" in d["universe_rules"]
    assert "proportional_cost" in d["cost_model"]
    assert d["commit_hash"]  # not empty
    assert d["experiment_id"]  # generated hash
    assert d["created_at"]  # timestamp


def test_manifest_deterministic_hash():
    """Same parameters → same content hash (reproducibility)."""
    config = BacktestConfig(
        strategy_type="magic_formula_original",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        top_n=20,
    )
    m1 = build_manifest(config, variant="v1")
    m2 = build_manifest(config, variant="v1")
    assert m1.experiment_id == m2.experiment_id


def test_manifest_different_variant_different_hash():
    """Different variant → different content hash."""
    config = BacktestConfig(
        strategy_type="magic_formula_original",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
    )
    m1 = build_manifest(config, variant="base")
    m2 = build_manifest(config, variant="no_quality")
    assert m1.experiment_id != m2.experiment_id


def test_manifest_serializes_to_json():
    """Manifest can be serialized to valid JSON."""
    config = BacktestConfig(
        strategy_type="magic_formula_hybrid",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
    )
    manifest = build_manifest(config)
    json_str = manifest.to_json()
    parsed = json.loads(json_str)
    assert parsed["strategy"] == "magic_formula_hybrid"


def test_manifest_preserves_cost_model():
    """Cost model parameters are fully captured in manifest."""
    config = BacktestConfig(
        strategy_type="magic_formula_brazil",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        cost_model=BRAZIL_REALISTIC,
    )
    manifest = build_manifest(config)
    assert manifest.cost_model["proportional_cost"] == 0.0005
    assert manifest.cost_model["slippage_bps"] == 10.0
