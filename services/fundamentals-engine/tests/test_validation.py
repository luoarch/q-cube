"""Tests for validation / reconciliation."""

from __future__ import annotations

from q3_fundamentals_engine.validation.accounting import AccountingValidator
from q3_fundamentals_engine.validation.anomaly import AnomalyDetector


def test_accounting_validator_balanced() -> None:
    validator = AccountingValidator()
    values = {
        "total_assets": 1_000_000.0,
        "total_liabilities": 600_000.0,
        "total_equity": 400_000.0,
        "revenue": 500_000.0,
        "cost_of_goods_sold": -200_000.0,
        "gross_profit": 700_000.0,
    }
    result = validator.validate(values)
    assert result["assets_eq_liabilities_plus_equity"]["passed"] is True
    assert result["gross_profit_eq_revenue_minus_cogs"]["passed"] is True


def test_accounting_validator_imbalanced() -> None:
    validator = AccountingValidator()
    values = {
        "total_assets": 1_000_000.0,
        "total_liabilities": 600_000.0,
        "total_equity": 300_000.0,  # off by 100K
    }
    result = validator.validate(values)
    assert result["assets_eq_liabilities_plus_equity"]["passed"] is False


def test_anomaly_detector_extreme_roic() -> None:
    detector = AnomalyDetector()
    import uuid
    anomalies = detector.detect(
        uuid.uuid4(),
        values={},
        metrics={"roic": 600.0},  # > 500%
    )
    assert any(a["rule"] == "roic_out_of_bounds" for a in anomalies)


def test_anomaly_detector_negative_equity() -> None:
    detector = AnomalyDetector()
    import uuid
    anomalies = detector.detect(
        uuid.uuid4(),
        values={"total_equity": -100_000.0},
        metrics={},
    )
    assert any(a["rule"] == "negative_equity" for a in anomalies)
