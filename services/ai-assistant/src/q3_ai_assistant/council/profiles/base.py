"""Base StrategyProfile dataclass for all agent profiles."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HardRejectRule:
    """Deterministic rule that forces verdict='avoid' when triggered."""
    code: str
    description: str
    condition: str  # Human-readable condition


@dataclass(frozen=True)
class SoftPreference:
    """Soft preference that influences reasoning but doesn't auto-reject."""
    code: str
    description: str
    weight: str  # 'strong' | 'moderate' | 'weak'


@dataclass(frozen=True)
class StrategyProfile:
    """Versioned configuration for a council agent's investment philosophy.

    Changes to this profile bump profile_version. All opinions reference
    which profile_version was used for reproducibility.
    """
    agent_id: str
    display_name: str
    philosophy: str
    profile_version: int
    core_metrics: list[str]
    hard_rejects: list[HardRejectRule]
    soft_preferences: list[SoftPreference]
    classification_aware: bool = True
    sector_exceptions: list[str] = field(default_factory=list)
