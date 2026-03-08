"""Test fixtures — in-memory SQLite session for unit tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from q3_ai_assistant.db.base import Base
from q3_ai_assistant.models.entities import (
    AIExplanation,
    AIModule,
    AIResearchNote,
    AISuggestion,
    ConfidenceLevel,
    ExplanationType,
    NoteType,
)

JSONB._default_dialect_inspections = set()  # type: ignore[attr-defined]


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    sess = factory()
    yield sess
    sess.close()


def make_suggestion(
    session: Session,
    *,
    module: AIModule = AIModule.ranking_explainer,
    tenant_id: uuid.UUID | None = None,
    trigger_entity_id: uuid.UUID | None = None,
    input_hash: str = "abc123",
    output_text: str = "test output",
    structured_output: dict | None = None,
    confidence: ConfidenceLevel = ConfidenceLevel.high,
    quality_score: float = 0.8,
) -> AISuggestion:
    suggestion = AISuggestion(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        module=module,
        trigger_event="test_event",
        trigger_entity_id=trigger_entity_id or uuid.uuid4(),
        input_hash=input_hash,
        prompt_version="v1",
        output_schema_version="v1",
        input_snapshot={"test": True},
        output_text=output_text,
        structured_output=structured_output or {"quality_score": quality_score},
        confidence=confidence,
        model_used="mock-v1",
        model_version="mock-v1.0",
        tokens_used=150,
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.0,
    )
    session.add(suggestion)
    session.flush()
    return suggestion


def make_explanation(
    session: Session,
    suggestion: AISuggestion,
    *,
    entity_type: str = "security",
    entity_id: str = "TEST3",
    explanation_type: ExplanationType = ExplanationType.position,
    content: str = "Test explanation",
) -> AIExplanation:
    explanation = AIExplanation(
        id=uuid.uuid4(),
        suggestion_id=suggestion.id,
        entity_type=entity_type,
        entity_id=entity_id,
        explanation_type=explanation_type,
        content=content,
    )
    session.add(explanation)
    session.flush()
    return explanation


def make_research_note(
    session: Session,
    suggestion: AISuggestion,
    *,
    note_type: NoteType = NoteType.summary,
    content: str = "Test note",
) -> AIResearchNote:
    note = AIResearchNote(
        id=uuid.uuid4(),
        suggestion_id=suggestion.id,
        note_type=note_type,
        content=content,
    )
    session.add(note)
    session.flush()
    return note


SAMPLE_RANKED_ASSETS = [
    {"rank": 1, "ticker": "PETR4", "name": "Petrobras", "sector": "Energia", "earningsYield": 0.15, "returnOnCapital": 0.25},
    {"rank": 2, "ticker": "VALE3", "name": "Vale", "sector": "Mineracao", "earningsYield": 0.12, "returnOnCapital": 0.30},
    {"rank": 3, "ticker": "ITUB4", "name": "Itau Unibanco", "sector": "Financeiro", "earningsYield": 0.10, "returnOnCapital": 0.20},
    {"rank": 4, "ticker": "BBDC4", "name": "Bradesco", "sector": "Financeiro", "earningsYield": 0.09, "returnOnCapital": 0.18},
    {"rank": 5, "ticker": "WEGE3", "name": "WEG", "sector": "Industria", "earningsYield": 0.08, "returnOnCapital": 0.35},
    {"rank": 6, "ticker": "RENT3", "name": "Localiza", "sector": "Consumo", "earningsYield": 0.07, "returnOnCapital": 0.22},
    {"rank": 7, "ticker": "SUZB3", "name": "Suzano", "sector": "Materiais", "earningsYield": 0.11, "returnOnCapital": 0.15},
    {"rank": 8, "ticker": "JBSS3", "name": "JBS", "sector": "Consumo", "earningsYield": 0.13, "returnOnCapital": 0.19},
    {"rank": 9, "ticker": "BBAS3", "name": "Banco do Brasil", "sector": "Financeiro", "earningsYield": 0.11, "returnOnCapital": 0.17},
    {"rank": 10, "ticker": "MGLU3", "name": "Magazine Luiza", "sector": "Varejo", "earningsYield": 0.06, "returnOnCapital": 0.12},
]

SAMPLE_BACKTEST_METRICS = {
    "cagr": 0.185,
    "sharpe": 1.2,
    "sharpe_ratio": 1.2,
    "sortino": 1.8,
    "max_drawdown": -0.223,
    "hit_rate": 0.55,
    "turnover": 1.5,
    "total_return": 2.35,
    "annual_volatility": 0.18,
}

SAMPLE_BACKTEST_CONFIG = {
    "strategyType": "magic_formula_brazil",
    "startDate": "2020-01-01",
    "endDate": "2025-12-31",
    "rebalanceFreq": "quarterly",
    "topN": 20,
    "equalWeight": True,
    "initialCapital": 1000000,
}
