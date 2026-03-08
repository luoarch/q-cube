from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityScore:
    completeness: float
    parseable: bool
    coherence: float
    groundedness: float
    overall: float


def evaluate_ranking_explanation(input_data: dict, output: dict) -> QualityScore:
    completeness = _check_fields(output, ["summary", "sector_analysis", "position_explanations"])
    coherence = _check_length(output.get("summary", ""), min_chars=50, max_chars=2000)
    groundedness = _check_tickers_mentioned(
        output.get("position_explanations", []),
        [a["ticker"] for a in input_data.get("ranked_assets", [])],
    )
    overall = 0.4 * completeness + 0.3 * coherence + 0.3 * groundedness
    return QualityScore(
        completeness=completeness,
        parseable=True,
        coherence=coherence,
        groundedness=groundedness,
        overall=round(overall, 3),
    )


def evaluate_backtest_narrative(input_data: dict, output: dict) -> QualityScore:
    completeness = _check_fields(output, ["narrative", "highlights", "concerns"])
    coherence = _check_length(output.get("narrative", ""), min_chars=50, max_chars=3000)

    metric_keys = set(input_data.get("metrics", {}).keys())
    highlights = output.get("highlights", [])
    if highlights and metric_keys:
        mentioned = sum(1 for h in highlights if h.get("metric") in metric_keys)
        groundedness = mentioned / len(highlights) if highlights else 0.0
    else:
        groundedness = 0.5 if completeness > 0 else 0.0

    overall = 0.4 * completeness + 0.3 * coherence + 0.3 * groundedness
    return QualityScore(
        completeness=completeness,
        parseable=True,
        coherence=coherence,
        groundedness=groundedness,
        overall=round(overall, 3),
    )


class RegressionDetector:
    def __init__(self, threshold: float = 0.1) -> None:
        self.threshold = threshold

    def check(self, recent_scores: list[float], baseline_mean: float) -> bool:
        if not recent_scores or baseline_mean <= 0:
            return False
        recent_mean = sum(recent_scores) / len(recent_scores)
        return (baseline_mean - recent_mean) / baseline_mean > self.threshold


def _check_fields(output: dict, required_fields: list[str]) -> float:
    if not output:
        return 0.0
    present = sum(1 for f in required_fields if output.get(f))
    return present / len(required_fields)


def _check_length(text: str, min_chars: int, max_chars: int) -> float:
    if not text:
        return 0.0
    length = len(text)
    if length < min_chars:
        return length / min_chars
    if length > max_chars:
        return max(0.5, 1.0 - (length - max_chars) / max_chars)
    return 1.0


def _check_tickers_mentioned(
    explanations: list[dict],
    input_tickers: list[str],
) -> float:
    if not explanations or not input_tickers:
        return 0.0
    ticker_set = set(input_tickers)
    mentioned = sum(1 for e in explanations if e.get("ticker") in ticker_set)
    return mentioned / len(explanations) if explanations else 0.0
