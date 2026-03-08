from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from q3_ai_assistant.db.base import Base


class AIModule(str, enum.Enum):
    ranking_explainer = "ranking_explainer"
    backtest_narrator = "backtest_narrator"
    metric_explainer = "metric_explainer"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class ConfidenceLevel(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ExplanationType(str, enum.Enum):
    position = "position"
    sector = "sector"
    outlier = "outlier"
    metric = "metric"


class NoteType(str, enum.Enum):
    summary = "summary"
    concern = "concern"
    highlight = "highlight"
    recommendation = "recommendation"


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "module", "trigger_entity_id", "input_hash", "prompt_version",
            name="uq_ai_suggestions_dedup",
        ),
        Index("idx_ai_suggestions_tenant_module", "tenant_id", "module"),
        Index("idx_ai_suggestions_trigger", "trigger_entity_id"),
        Index("idx_ai_suggestions_review", "review_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
    )
    module: Mapped[AIModule] = mapped_column(
        Enum(AIModule, name="ai_module"), nullable=False,
    )
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_output: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel, name="confidence_level"), nullable=False,
    )
    model_used: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens_used: Mapped[int] = mapped_column(nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(nullable=False)
    completion_tokens: Mapped[int] = mapped_column(nullable=False)
    cost_usd: Mapped[float] = mapped_column(nullable=False, default=0.0)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), nullable=False, default=ReviewStatus.pending,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    explanations: Mapped[list[AIExplanation]] = relationship(
        back_populates="suggestion", cascade="all, delete-orphan",
    )
    research_notes: Mapped[list[AIResearchNote]] = relationship(
        back_populates="suggestion", cascade="all, delete-orphan",
    )


class AIExplanation(Base):
    __tablename__ = "ai_explanations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_suggestions.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation_type: Mapped[ExplanationType] = mapped_column(
        Enum(ExplanationType, name="explanation_type"), nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    suggestion: Mapped[AISuggestion] = relationship(back_populates="explanations")


class AIResearchNote(Base):
    __tablename__ = "ai_research_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_suggestions.id", ondelete="CASCADE"),
        nullable=False,
    )
    note_type: Mapped[NoteType] = mapped_column(
        Enum(NoteType, name="note_type"), nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    suggestion: Mapped[AISuggestion] = relationship(back_populates="research_notes")
