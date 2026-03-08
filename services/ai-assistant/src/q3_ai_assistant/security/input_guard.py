from __future__ import annotations

import math
import re

MAX_RANKED_ASSETS = 200
MAX_INPUT_CHARS = 50_000
MAX_TICKER_LENGTH = 12

_INJECTION_RE = re.compile(
    r"(ignore|disregard|forget|override)\s+(previous|all|above|prior|system)\s+(instructions|prompts|rules)",
    re.IGNORECASE,
)


def validate_ranking_input(ranked_assets: list[dict]) -> list[dict]:
    if len(ranked_assets) > MAX_RANKED_ASSETS:
        ranked_assets = ranked_assets[:MAX_RANKED_ASSETS]

    sanitized: list[dict] = []
    for asset in ranked_assets:
        sanitized.append({
            "rank": _safe_int(asset.get("rank")),
            "ticker": _sanitize_ticker(asset.get("ticker", "")),
            "name": _sanitize_text(asset.get("name", ""), max_len=100),
            "sector": _sanitize_text(asset.get("sector", ""), max_len=50),
            "earningsYield": _safe_float(asset.get("earningsYield")),
            "returnOnCapital": _safe_float(asset.get("returnOnCapital")),
        })
    return sanitized


def validate_backtest_input(metrics: dict, config: dict) -> tuple[dict, dict]:
    safe_metrics: dict = {}
    for key, value in metrics.items():
        k = _sanitize_text(str(key), max_len=50)
        safe_metrics[k] = _safe_float(value) if isinstance(value, (int, float)) else _sanitize_text(str(value), max_len=200)

    safe_config: dict = {}
    for key, value in config.items():
        k = _sanitize_text(str(key), max_len=50)
        if isinstance(value, (int, float)):
            safe_config[k] = _safe_float(value) if isinstance(value, float) else _safe_int(value)
        elif isinstance(value, bool):
            safe_config[k] = value
        else:
            safe_config[k] = _sanitize_text(str(value), max_len=200)

    return safe_metrics, safe_config


def check_total_prompt_size(system_prompt: str, user_prompt: str) -> bool:
    return (len(system_prompt) + len(user_prompt)) <= MAX_INPUT_CHARS


def _sanitize_ticker(ticker: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9^]", "", ticker.upper()[:MAX_TICKER_LENGTH])
    return cleaned or "UNKNOWN"


def _sanitize_text(text: str, max_len: int = 200) -> str:
    text = text[:max_len]
    text = _INJECTION_RE.sub("", text)
    return text.strip()


def _safe_float(value: object) -> float:
    try:
        f = float(value)  # type: ignore[arg-type]
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
