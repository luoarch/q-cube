"""Council data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID


class AgentVerdict(str, Enum):
    buy = "buy"
    watch = "watch"
    avoid = "avoid"
    insufficient_data = "insufficient_data"


class CouncilMode(str, Enum):
    solo = "solo"
    roundtable = "roundtable"
    debate = "debate"
    comparison = "comparison"


@dataclass
class AgentOpinion:
    agent_id: str
    profile_version: int
    prompt_version: int
    verdict: AgentVerdict
    confidence: int  # 0-100
    data_reliability: str
    thesis: str
    reasons_for: list[str]
    reasons_against: list[str]
    key_metrics_used: list[str]
    hard_rejects_triggered: list[str]
    unknowns: list[str]
    what_would_change_my_mind: list[str]
    investor_fit: list[str]
    # Audit
    provider_used: str = ""
    model_used: str = ""
    fallback_level: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0


@dataclass
class CouncilScoreboard:
    entries: list[dict[str, object]]
    consensus: AgentVerdict | None
    consensus_strength: float | None


@dataclass
class ConflictEntry:
    agent1: str
    agent2: str
    topic: str
    agent1_position: str
    agent2_position: str


@dataclass
class ModeratorSynthesis:
    convergences: list[str]
    divergences: list[str]
    biggest_risk: str
    entry_conditions: list[str]
    exit_conditions: list[str]
    overall_assessment: str


@dataclass
class DebateRound:
    round_number: int
    agent_id: str
    content: str
    target_agent_id: str | None
    timestamp: str


@dataclass
class AuditTrail:
    input_hash: str
    prompt_versions: dict[str, int]
    profile_versions: dict[str, int]
    models_used: dict[str, str]
    providers_used: dict[str, str]
    fallback_levels: dict[str, int]
    total_tokens: int
    total_cost_usd: float
    total_latency_ms: float


@dataclass
class CouncilResult:
    session_id: str
    mode: CouncilMode
    asset_ids: list[str]
    opinions: list[AgentOpinion]
    scoreboard: CouncilScoreboard
    conflict_matrix: list[ConflictEntry]
    moderator_synthesis: ModeratorSynthesis
    debate_log: list[DebateRound] | None
    disclaimer: str
    audit_trail: AuditTrail
