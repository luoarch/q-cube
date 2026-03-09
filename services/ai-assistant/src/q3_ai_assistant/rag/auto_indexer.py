"""Automatic RAG indexing pipeline.

Indexes structured data from the Q3 platform into the embeddings table
for semantic retrieval by the free chat and council modules.

Indexed entity types:
- refiner_result: Refinement scores, flags, and trend data per issuer
- council_opinion: Agent opinions from council sessions
- strategy_run: Strategy run results and ranking summaries
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from q3_ai_assistant.config import settings
from q3_ai_assistant.rag.embedder import Embedder
from q3_ai_assistant.rag.indexer import Indexer

logger = logging.getLogger(__name__)


def _build_refiner_sections(row: dict) -> list[tuple[str, str]]:
    """Build indexable text sections from a refinement result row."""
    ticker = row.get("ticker", "?")
    sections: list[tuple[str, str]] = []

    # Scores summary
    scores = [
        f"Earnings Quality: {row.get('earnings_quality_score', 'N/A')}",
        f"Safety: {row.get('safety_score', 'N/A')}",
        f"Operating Consistency: {row.get('operating_consistency_score', 'N/A')}",
        f"Capital Discipline: {row.get('capital_discipline_score', 'N/A')}",
        f"Refinement Score: {row.get('refinement_score', 'N/A')}",
        f"Adjusted Rank: {row.get('adjusted_rank', 'N/A')}",
        f"Base Rank: {row.get('base_rank', 'N/A')}",
        f"Reliability: {row.get('score_reliability', 'N/A')}",
        f"Classification: {row.get('issuer_classification', 'N/A')}",
    ]
    sections.append((f"{ticker} Refiner Scores", "\n".join(scores)))

    # Flags
    flags = row.get("flags_json", {})
    if flags:
        red = flags.get("red", [])
        strength = flags.get("strength", [])
        flag_text = ""
        if red:
            flag_text += f"Red flags: {', '.join(red)}\n"
        if strength:
            flag_text += f"Strength flags: {', '.join(strength)}\n"
        if flag_text:
            sections.append((f"{ticker} Flags", flag_text.strip()))

    # Trend data summary
    trends = row.get("trend_data_json", {})
    if trends and isinstance(trends, dict):
        trend_lines = []
        for metric, values in trends.items():
            if isinstance(values, list):
                vals_str = " → ".join(str(v) for v in values)
                trend_lines.append(f"{metric}: {vals_str}")
        if trend_lines:
            sections.append((f"{ticker} 3-Period Trends", "\n".join(trend_lines[:15])))

    return sections


def _build_council_sections(opinion: dict) -> list[tuple[str, str]]:
    """Build indexable text from a council agent opinion."""
    agent = opinion.get("agent_id", "?")
    ticker = opinion.get("ticker", "?")
    sections: list[tuple[str, str]] = []

    # Main opinion
    parts = [
        f"Agent: {agent}",
        f"Verdict: {opinion.get('verdict', 'N/A')}",
        f"Confidence: {opinion.get('confidence', 'N/A')}%",
        f"Thesis: {opinion.get('thesis', '')}",
    ]
    sections.append((f"{agent} opinion on {ticker}", "\n".join(parts)))

    # Reasons
    reasons_for = opinion.get("reasons_for", [])
    reasons_against = opinion.get("reasons_against", [])
    if reasons_for or reasons_against:
        reason_text = ""
        if reasons_for:
            reason_text += "Reasons for:\n" + "\n".join(f"- {r}" for r in reasons_for) + "\n"
        if reasons_against:
            reason_text += "Reasons against:\n" + "\n".join(f"- {r}" for r in reasons_against)
        sections.append((f"{agent} reasons for {ticker}", reason_text.strip()))

    return sections


def _build_strategy_sections(run: dict) -> list[tuple[str, str]]:
    """Build indexable text from a strategy run result."""
    strategy = run.get("strategy", "?")
    sections: list[tuple[str, str]] = []

    ranked = run.get("rankedAssets", [])
    if ranked:
        top_10 = ranked[:10]
        lines = [f"Strategy: {strategy}", f"Total ranked: {len(ranked)}", "Top 10:"]
        for i, asset in enumerate(top_10, 1):
            ticker = asset.get("ticker", "?")
            ey = asset.get("earnings_yield")
            roc = asset.get("return_on_capital")
            lines.append(f"{i}. {ticker} (EY={ey}, ROC={roc})")
        sections.append(("Ranking Summary", "\n".join(lines)))

    return sections


def index_refiner_results(session: Session, strategy_run_id: str) -> int:
    """Index all refinement results for a strategy run."""
    if not settings.openai_api_key:
        logger.warning("Skipping RAG indexing: no OpenAI API key")
        return 0

    rows = session.execute(
        text("""
            SELECT ticker, base_rank, earnings_quality_score, safety_score,
                   operating_consistency_score, capital_discipline_score,
                   refinement_score, adjusted_rank, flags_json, trend_data_json,
                   score_reliability, issuer_classification
            FROM refinement_results
            WHERE strategy_run_id = :run_id
        """),
        {"run_id": strategy_run_id},
    ).fetchall()

    if not rows:
        return 0

    embedder = Embedder(settings)
    indexer = Indexer(embedder)
    total = 0

    for row in rows:
        row_dict = {
            "ticker": row[0], "base_rank": row[1],
            "earnings_quality_score": row[2], "safety_score": row[3],
            "operating_consistency_score": row[4], "capital_discipline_score": row[5],
            "refinement_score": row[6], "adjusted_rank": row[7],
            "flags_json": row[8], "trend_data_json": row[9],
            "score_reliability": row[10], "issuer_classification": row[11],
        }
        sections = _build_refiner_sections(row_dict)
        if sections:
            count = indexer.index_structured(
                session,
                entity_type="refiner_result",
                entity_id=f"{strategy_run_id}:{row_dict['ticker']}",
                sections=sections,
            )
            total += count

    logger.info("Indexed %d refiner chunks for run %s", total, strategy_run_id)
    return total


def index_council_opinions(session: Session, council_session_id: str) -> int:
    """Index council opinions from a council session."""
    if not settings.openai_api_key:
        logger.warning("Skipping RAG indexing: no OpenAI API key")
        return 0

    rows = session.execute(
        text("""
            SELECT agent_id, verdict, confidence, opinion_json
            FROM council_opinions
            WHERE council_session_id = :session_id
        """),
        {"session_id": council_session_id},
    ).fetchall()

    if not rows:
        return 0

    embedder = Embedder(settings)
    indexer = Indexer(embedder)
    total = 0

    for row in rows:
        opinion_data = row[3] or {}
        opinion_data["agent_id"] = row[0]
        opinion_data["verdict"] = row[1]
        opinion_data["confidence"] = row[2]

        sections = _build_council_sections(opinion_data)
        if sections:
            count = indexer.index_structured(
                session,
                entity_type="council_opinion",
                entity_id=f"{council_session_id}:{row[0]}",
                sections=sections,
            )
            total += count

    logger.info("Indexed %d council chunks for session %s", total, council_session_id)
    return total


def index_strategy_run(session: Session, run_id: str) -> int:
    """Index a strategy run's ranking results."""
    if not settings.openai_api_key:
        logger.warning("Skipping RAG indexing: no OpenAI API key")
        return 0

    from q3_shared_models.entities import StrategyRun

    run = session.execute(
        select(StrategyRun).where(StrategyRun.id == run_id)
    ).scalar_one_or_none()

    if not run or not run.result_json:
        return 0

    result = run.result_json if isinstance(run.result_json, dict) else json.loads(run.result_json)
    sections = _build_strategy_sections(result)

    if not sections:
        return 0

    embedder = Embedder(settings)
    indexer = Indexer(embedder)
    count = indexer.index_structured(
        session,
        entity_type="strategy_run",
        entity_id=str(run_id),
        sections=sections,
    )
    logger.info("Indexed %d strategy chunks for run %s", count, run_id)
    return count
