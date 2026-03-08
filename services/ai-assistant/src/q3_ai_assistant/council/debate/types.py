"""Debate-specific types.

DebateRound is canonical in council.types — re-exported here for convenience.
Additional debate-specific types live here.
"""

from __future__ import annotations

from dataclasses import dataclass

from q3_ai_assistant.council.types import DebateRound

__all__ = ["Contestation", "DebateRound", "Reply"]


@dataclass(frozen=True)
class Contestation:
    """A contestation from one agent targeting another's point."""
    from_agent: str
    target_agent: str
    point: str
    counter_argument: str


@dataclass(frozen=True)
class Reply:
    """An agent's reply to a contestation received."""
    from_agent: str
    to_agent: str
    response: str
    conceded: bool = False
