"""Post-ingestion smoke tests to catch data quality issues before publishing."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class SmokeTestResult:
    """Result of a single smoke test."""
    name: str
    passed: bool
    violations: list[str] = field(default_factory=list)


def run_smoke_tests(session: Session) -> list[SmokeTestResult]:
    """Run all smoke tests and return results."""
    tests = [
        _test_no_duplicate_statement_lines,
        _test_no_impossible_margins,
        _test_no_extreme_roic,
        _test_no_negative_revenue,
        _test_metrics_have_inputs,
    ]
    results = []
    for test_fn in tests:
        result = test_fn(session)
        results.append(result)
        status = "PASS" if result.passed else f"FAIL ({len(result.violations)} violations)"
        logger.info("Smoke test [%s]: %s", result.name, status)
        if not result.passed:
            for v in result.violations[:5]:  # Log first 5
                logger.warning("  - %s", v)
            if len(result.violations) > 5:
                logger.warning("  ... and %d more", len(result.violations) - 5)
    return results


def _test_no_duplicate_statement_lines(session: Session) -> SmokeTestResult:
    """No duplicate (filing_id, canonical_key, statement_type, scope, period_type, reference_date)."""
    rows = session.execute(text("""
        SELECT filing_id, canonical_key, statement_type, scope, period_type, reference_date, COUNT(*)
        FROM statement_lines
        WHERE canonical_key IS NOT NULL
        GROUP BY filing_id, canonical_key, statement_type, scope, period_type, reference_date
        HAVING COUNT(*) > 1
        LIMIT 20
    """)).fetchall()
    violations = [
        f"filing={r[0]} key={r[1]} stmt={r[2]} scope={r[3]} period={r[4]} ref={r[5]} count={r[6]}"
        for r in rows
    ]
    return SmokeTestResult(name="no_duplicate_statement_lines", passed=len(violations) == 0, violations=violations)


def _test_no_impossible_margins(session: Session) -> SmokeTestResult:
    """No net_margin or gross_margin > 1.0 (100%) or < -1.0 (-100%)."""
    rows = session.execute(text("""
        SELECT cm.issuer_id, i.legal_name, cm.metric_code, cm.value, cm.reference_date
        FROM computed_metrics cm
        JOIN issuers i ON i.id = cm.issuer_id
        WHERE cm.metric_code IN ('net_margin', 'gross_margin', 'ebit_margin')
          AND (cm.value > 1.0 OR cm.value < -1.0)
        ORDER BY ABS(cm.value) DESC
        LIMIT 20
    """)).fetchall()
    violations = [
        f"{r[1] or r[0]}: {r[2]}={r[3]:.2%} ref={r[4]}"
        for r in rows
    ]
    return SmokeTestResult(name="no_impossible_margins", passed=len(violations) == 0, violations=violations)


def _test_no_extreme_roic(session: Session) -> SmokeTestResult:
    """No ROIC > 500% (5.0) — likely data contamination."""
    rows = session.execute(text("""
        SELECT cm.issuer_id, i.legal_name, cm.value, cm.reference_date
        FROM computed_metrics cm
        JOIN issuers i ON i.id = cm.issuer_id
        WHERE cm.metric_code = 'roic' AND ABS(cm.value) > 5.0
        ORDER BY ABS(cm.value) DESC
        LIMIT 20
    """)).fetchall()
    violations = [
        f"{r[1] or r[0]}: ROIC={r[2]:.2%} ref={r[3]}"
        for r in rows
    ]
    return SmokeTestResult(name="no_extreme_roic", passed=len(violations) == 0, violations=violations)


def _test_no_negative_revenue(session: Session) -> SmokeTestResult:
    """Revenue should never be negative."""
    rows = session.execute(text("""
        SELECT f.issuer_id, i.legal_name, sl.normalized_value, sl.reference_date
        FROM statement_lines sl
        JOIN filings f ON f.id = sl.filing_id
        JOIN issuers i ON i.id = f.issuer_id
        WHERE sl.canonical_key = 'revenue' AND sl.normalized_value < 0
        LIMIT 20
    """)).fetchall()
    violations = [
        f"{r[1] or r[0]}: revenue={r[2]} ref={r[3]}"
        for r in rows
    ]
    return SmokeTestResult(name="no_negative_revenue", passed=len(violations) == 0, violations=violations)


def _test_metrics_have_inputs(session: Session) -> SmokeTestResult:
    """All computed_metrics should have non-null inputs_snapshot_json."""
    row = session.execute(text("""
        SELECT COUNT(*) FROM computed_metrics WHERE inputs_snapshot_json IS NULL
    """)).fetchone()
    count = row[0] if row else 0
    violations = [f"{count} metrics missing inputs_snapshot_json"] if count > 0 else []
    return SmokeTestResult(name="metrics_have_inputs", passed=count == 0, violations=violations)
