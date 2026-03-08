"""Data completeness assessment for refiner scoring."""

from __future__ import annotations

from q3_quant_engine.refiner.types import (
    SCORE_RELIABILITY_HIGH,
    SCORE_RELIABILITY_LOW,
    SCORE_RELIABILITY_MEDIUM,
    SCORE_RELIABILITY_UNAVAILABLE,
    DataCompleteness,
)

# Metrics expected per classification
NON_FINANCIAL_METRICS = [
    "revenue", "ebit", "net_income", "ebitda", "gross_profit",
    "cash_from_operations", "cash_from_investing",
    "net_debt", "current_assets", "current_liabilities",
    "total_assets", "equity", "short_term_debt",
    "gross_margin", "ebit_margin", "net_margin",
    "roic", "debt_to_ebitda", "cash_conversion",
]

BANK_METRICS = [
    "revenue", "net_income", "equity", "total_assets",
    "roe", "net_margin",
]

CRITICAL_NON_FINANCIAL = {"revenue", "ebit", "net_income", "cash_from_operations"}
CRITICAL_BANK = {"net_income", "equity", "total_assets"}


def assess_completeness(
    data: dict[str, list[float | None]],
    periods_available: int,
    classification: str,
) -> tuple[DataCompleteness, str]:
    if classification in ("bank", "insurer", "holding"):
        expected_keys = BANK_METRICS
        critical_keys = CRITICAL_BANK
    else:
        expected_keys = NON_FINANCIAL_METRICS
        critical_keys = CRITICAL_NON_FINANCIAL

    available = 0
    missing_critical: list[str] = []
    for key in expected_keys:
        values = data.get(key, [])
        if any(v is not None for v in values):
            available += 1

    for key in critical_keys:
        values = data.get(key, [])
        if not any(v is not None for v in values):
            missing_critical.append(key)

    expected = len(expected_keys)
    ratio = available / expected if expected > 0 else 0.0

    completeness = DataCompleteness(
        periods_available=periods_available,
        metrics_available=available,
        metrics_expected=expected,
        completeness_ratio=round(ratio, 4),
        missing_critical=missing_critical,
        proxy_used=[],
    )

    if periods_available == 0:
        reliability = SCORE_RELIABILITY_UNAVAILABLE
    elif periods_available == 1 or ratio < 0.6 or missing_critical:
        reliability = SCORE_RELIABILITY_LOW
    elif periods_available == 2 or ratio < 0.85:
        reliability = SCORE_RELIABILITY_MEDIUM
    else:
        reliability = SCORE_RELIABILITY_HIGH

    return completeness, reliability
