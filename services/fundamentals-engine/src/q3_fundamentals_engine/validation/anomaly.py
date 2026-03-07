from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects anomalous values in financial statement data and computed metrics."""

    def detect(
        self,
        issuer_id: uuid.UUID,
        values: dict[str, float | None],
        metrics: dict[str, float | None],
    ) -> list[dict[str, Any]]:
        """Run anomaly detection rules.

        Rules:
        - ROIC > 500% or < -500%
        - Negative equity
        - Revenue = 0 but EBIT != 0
        - YoY jumps > 10x (requires prior_values in values dict as "prior_<key>")

        Returns list of anomaly dicts with: rule, severity, description, details.
        """
        anomalies: list[dict[str, Any]] = []

        # --- ROIC bounds ---
        roic = metrics.get("roic")
        if roic is not None and abs(roic) > 5.0:
            anomalies.append({
                "rule": "roic_out_of_bounds",
                "severity": "high",
                "description": f"ROIC of {roic:.2%} is outside expected range (-500% to 500%)",
                "details": {"roic": roic, "threshold": 5.0},
            })

        # --- Negative equity ---
        total_equity = values.get("total_equity")
        if total_equity is not None and total_equity < 0:
            anomalies.append({
                "rule": "negative_equity",
                "severity": "medium",
                "description": f"Negative total equity: {total_equity:,.2f}",
                "details": {"total_equity": total_equity},
            })

        # --- Revenue zero but EBIT nonzero ---
        revenue = values.get("revenue")
        ebit = values.get("ebit")
        if revenue is not None and revenue == 0 and ebit is not None and ebit != 0:
            anomalies.append({
                "rule": "zero_revenue_nonzero_ebit",
                "severity": "high",
                "description": f"Revenue is zero but EBIT is {ebit:,.2f}",
                "details": {"revenue": revenue, "ebit": ebit},
            })

        # --- YoY jumps > 10x ---
        _YOY_KEYS = ["revenue", "ebit", "net_income", "total_assets"]
        for key in _YOY_KEYS:
            current = values.get(key)
            prior = values.get(f"prior_{key}")
            if current is not None and prior is not None and prior != 0:
                ratio = abs(current / prior)
                if ratio > 10.0:
                    anomalies.append({
                        "rule": "yoy_jump",
                        "severity": "medium",
                        "description": f"{key} changed {ratio:.1f}x YoY (prior={prior:,.2f}, current={current:,.2f})",
                        "details": {"key": key, "current": current, "prior": prior, "ratio": ratio},
                    })

        if anomalies:
            logger.warning(
                "Detected %d anomalies for issuer=%s: %s",
                len(anomalies),
                issuer_id,
                [a["rule"] for a in anomalies],
            )

        return anomalies
